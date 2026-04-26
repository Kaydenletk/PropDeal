import json
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def mock_s3():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-clean")
        yield s3


def _put_clean(s3, key, listings):
    s3.put_object(Bucket="test-clean", Key=key, Body=json.dumps(listings).encode())


def test_enrich_happy_path(mock_s3, mock_secrets, sample_listing):
    _put_clean(mock_s3, "clean/2026-04-25.json", [sample_listing])
    fake_resp = MagicMock()
    fake_resp.choices = [
        MagicMock(message=MagicMock(content='{"score":0.85,"keywords":["as-is","cash only"]}'))
    ]
    with patch("enrich.handler._client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = fake_resp
        from enrich.handler import handler  # noqa: PLC0415
        result = handler({"clean_key": "clean/2026-04-25.json"}, None)
    assert result["count"] == 1
    obj = mock_s3.get_object(Bucket="test-clean", Key=result["enriched_key"])
    rec = json.loads(obj["Body"].read())[0]
    assert rec["distress_score"] == 0.85


def test_enrich_idempotent_skip(mock_s3, mock_secrets, sample_listing):
    _put_clean(mock_s3, "clean/2026-04-25.json", [sample_listing])
    _put_clean(mock_s3, "enriched/2026-04-25.json", [sample_listing])
    from enrich.handler import handler  # noqa: PLC0415
    result = handler({"clean_key": "clean/2026-04-25.json"}, None)
    assert result["skipped"] is True


def test_enrich_rate_limit_then_succeed(mock_s3, mock_secrets, sample_listing):
    from openai import RateLimitError
    _put_clean(mock_s3, "clean/2026-04-25.json", [sample_listing])
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content='{"score":0.5,"keywords":[]}'))]
    with patch("enrich.handler._client") as mock_client:
        mock_client.return_value.chat.completions.create.side_effect = [
            RateLimitError(message="rate", response=MagicMock(), body={}),
            fake_resp,
        ]
        with patch("enrich.handler.time.sleep"):
            from enrich.handler import handler  # noqa: PLC0415
            result = handler({"clean_key": "clean/2026-04-25.json"}, None)
    rec = json.loads(
        mock_s3.get_object(Bucket="test-clean", Key=result["enriched_key"])["Body"].read()
    )[0]
    assert rec["distress_score"] == 0.5


def test_enrich_persistent_failure_yields_null_not_zero(mock_s3, mock_secrets, sample_listing):
    from openai import RateLimitError
    _put_clean(mock_s3, "clean/2026-04-25.json", [sample_listing])
    with patch("enrich.handler._client") as mock_client:
        mock_client.return_value.chat.completions.create.side_effect = RateLimitError(
            message="rate", response=MagicMock(), body={}
        )
        with patch("enrich.handler.time.sleep"):
            from enrich.handler import handler  # noqa: PLC0415
            result = handler({"clean_key": "clean/2026-04-25.json"}, None)
    rec = json.loads(
        mock_s3.get_object(Bucket="test-clean", Key=result["enriched_key"])["Body"].read()
    )[0]
    assert rec["distress_score"] is None


def test_enrich_malformed_json_response_yields_null(mock_s3, mock_secrets, sample_listing):
    _put_clean(mock_s3, "clean/2026-04-25.json", [sample_listing])
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="not json"))]
    with patch("enrich.handler._client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = fake_resp
        from enrich.handler import handler  # noqa: PLC0415
        result = handler({"clean_key": "clean/2026-04-25.json"}, None)
    rec = json.loads(
        mock_s3.get_object(Bucket="test-clean", Key=result["enriched_key"])["Body"].read()
    )[0]
    assert rec["distress_score"] is None
