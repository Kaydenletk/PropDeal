import json

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def mock_s3():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-raw")
        s3.create_bucket(Bucket="test-clean")
        yield s3


def test_transform_happy_path(mock_s3, sample_listing):
    mock_s3.put_object(
        Bucket="test-raw",
        Key="raw/2026-04-25.json",
        Body=json.dumps([sample_listing]).encode(),
    )
    from transform.handler import handler  # noqa: PLC0415
    result = handler({"raw_key": "raw/2026-04-25.json"}, None)
    obj = mock_s3.get_object(Bucket="test-clean", Key=result["clean_key"])
    rec = json.loads(obj["Body"].read())[0]
    assert rec["id"] == "abc-123"


def test_transform_redacts_phone(mock_s3, sample_listing):
    sample_listing["description"] = "Call 555-123-4567 ASAP. Cash only."
    mock_s3.put_object(
        Bucket="test-raw",
        Key="raw/d.json",
        Body=json.dumps([sample_listing]).encode(),
    )
    from transform.handler import handler  # noqa: PLC0415
    result = handler({"raw_key": "raw/d.json"}, None)
    obj = mock_s3.get_object(Bucket="test-clean", Key=result["clean_key"])
    rec = json.loads(obj["Body"].read())[0]
    assert "[PHONE_REDACTED]" in rec["description"]
    assert "555-123-4567" not in rec["description"]


def test_transform_redacts_email(mock_s3, sample_listing):
    sample_listing["description"] = "Email seller@example.com for showing."
    mock_s3.put_object(
        Bucket="test-raw",
        Key="raw/e.json",
        Body=json.dumps([sample_listing]).encode(),
    )
    from transform.handler import handler  # noqa: PLC0415
    result = handler({"raw_key": "raw/e.json"}, None)
    obj = mock_s3.get_object(Bucket="test-clean", Key=result["clean_key"])
    rec = json.loads(obj["Body"].read())[0]
    assert "[EMAIL_REDACTED]" in rec["description"]


def test_transform_handles_null_description(mock_s3, sample_listing):
    sample_listing["description"] = None
    mock_s3.put_object(
        Bucket="test-raw",
        Key="raw/n.json",
        Body=json.dumps([sample_listing]).encode(),
    )
    from transform.handler import handler  # noqa: PLC0415
    result = handler({"raw_key": "raw/n.json"}, None)
    obj = mock_s3.get_object(Bucket="test-clean", Key=result["clean_key"])
    rec = json.loads(obj["Body"].read())[0]
    assert rec["description"] is None


def test_transform_empty_list(mock_s3):
    mock_s3.put_object(Bucket="test-raw", Key="raw/empty.json", Body=b"[]")
    from transform.handler import handler  # noqa: PLC0415
    result = handler({"raw_key": "raw/empty.json"}, None)
    assert result["count"] == 0
