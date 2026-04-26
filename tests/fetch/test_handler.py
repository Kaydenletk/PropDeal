import json

import boto3
import pytest
import responses
from moto import mock_aws


@pytest.fixture
def mock_s3():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-raw")
        yield s3


@responses.activate
def test_fetch_happy_path(mock_s3, mock_secrets, sample_listing):
    responses.add(
        responses.GET,
        "https://api.rentcast.io/v1/listings/sale",
        json=[sample_listing],
        status=200,
    )
    from fetch.handler import handler  # noqa: PLC0415
    result = handler({}, None)
    assert result["count"] == 1
    obj = mock_s3.get_object(Bucket="test-raw", Key=result["raw_key"])
    body = json.loads(obj["Body"].read())
    assert body[0]["id"] == "abc-123"


@responses.activate
def test_fetch_5xx_partial_save(mock_s3, mock_secrets):
    for _ in range(4):  # 1 initial + 3 retries
        responses.add(
            responses.GET,
            "https://api.rentcast.io/v1/listings/sale",
            json={"error": "internal"},
            status=503,
        )
    from fetch.handler import handler  # noqa: PLC0415
    result = handler({}, None)
    assert result["count"] == 0
    assert "_partial" in result["raw_key"]


@responses.activate
def test_fetch_respects_max_listings(mock_s3, mock_secrets, sample_listing, monkeypatch):
    monkeypatch.setenv("MAX_LISTINGS_PER_RUN", "3")
    captured = {}

    def callback(req):
        captured["url"] = req.url
        return (200, {}, json.dumps([sample_listing]))

    responses.add_callback(
        responses.GET,
        "https://api.rentcast.io/v1/listings/sale",
        callback=callback,
    )
    # Reload handler to pick up new env var
    import importlib

    import fetch.handler
    importlib.reload(fetch.handler)
    fetch.handler.handler({}, None)
    assert "limit=3" in captured["url"]


@responses.activate
def test_fetch_empty_response(mock_s3, mock_secrets):
    responses.add(
        responses.GET,
        "https://api.rentcast.io/v1/listings/sale",
        json=[],
        status=200,
    )
    from fetch.handler import handler  # noqa: PLC0415
    result = handler({}, None)
    assert result["count"] == 0


@responses.activate
def test_fetch_writes_dated_key(mock_s3, mock_secrets, sample_listing):
    responses.add(
        responses.GET,
        "https://api.rentcast.io/v1/listings/sale",
        json=[sample_listing],
        status=200,
    )
    from fetch.handler import handler  # noqa: PLC0415
    result = handler({}, None)
    assert result["raw_key"].startswith("raw/")
    assert result["raw_key"].endswith(".json")
