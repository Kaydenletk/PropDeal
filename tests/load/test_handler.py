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


@pytest.fixture
def mock_pool():
    with patch("load.handler.get_pool") as gp:
        cur = MagicMock()
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cur
        gp.return_value.connection.return_value = conn
        yield cur


def test_load_happy_path(mock_s3, mock_secrets, mock_pool, sample_listing):
    sample_listing["distress_score"] = 0.7
    sample_listing["distress_keywords"] = ["as-is"]
    mock_s3.put_object(
        Bucket="test-clean",
        Key="enriched/x.json",
        Body=json.dumps([sample_listing]).encode(),
    )
    from load.handler import handler  # noqa: PLC0415
    result = handler({"enriched_key": "enriched/x.json"}, None)
    assert result["loaded"] == 1
    mock_pool.executemany.assert_called_once()


def test_load_uses_executemany(mock_s3, mock_secrets, mock_pool, sample_listing):
    listings = [dict(sample_listing, id=f"id-{i}") for i in range(5)]
    mock_s3.put_object(
        Bucket="test-clean",
        Key="enriched/m.json",
        Body=json.dumps(listings).encode(),
    )
    from load.handler import handler  # noqa: PLC0415
    handler({"enriched_key": "enriched/m.json"}, None)
    args, _ = mock_pool.executemany.call_args
    assert len(args[1]) == 5


def test_load_empty_list(mock_s3, mock_secrets, mock_pool):
    mock_s3.put_object(Bucket="test-clean", Key="enriched/empty.json", Body=b"[]")
    from load.handler import handler  # noqa: PLC0415
    result = handler({"enriched_key": "enriched/empty.json"}, None)
    assert result["loaded"] == 0


def test_load_handles_null_distress_score(mock_s3, mock_secrets, mock_pool, sample_listing):
    sample_listing["distress_score"] = None
    mock_s3.put_object(
        Bucket="test-clean",
        Key="enriched/n.json",
        Body=json.dumps([sample_listing]).encode(),
    )
    from load.handler import handler  # noqa: PLC0415
    result = handler({"enriched_key": "enriched/n.json"}, None)
    assert result["loaded"] == 1
    args, _ = mock_pool.executemany.call_args
    assert args[1][0]["distress_score"] is None


def test_load_field_mapping(mock_s3, mock_secrets, mock_pool, sample_listing):
    mock_s3.put_object(
        Bucket="test-clean",
        Key="enriched/f.json",
        Body=json.dumps([sample_listing]).encode(),
    )
    from load.handler import handler  # noqa: PLC0415
    handler({"enriched_key": "enriched/f.json"}, None)
    args, _ = mock_pool.executemany.call_args
    row = args[1][0]
    assert row["zip"] == "38103"
    assert row["square_feet"] == 1100
    assert row["year_built"] == 1955
