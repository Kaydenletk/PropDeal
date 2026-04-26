import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_pool():
    with patch("api.handler.get_pool") as gp:
        cur = MagicMock()
        # Mock cursor.description with named columns
        cols = ["listing_id", "address", "city", "state", "zip", "price", "distress_score"]
        descriptors = []
        for c in cols:
            d = MagicMock()
            d.name = c
            descriptors.append(d)
        cur.description = descriptors
        cur.fetchall.return_value = [("abc", "123 Main", "Memphis", "TN", "38103", 95000, 0.85)]
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cur
        gp.return_value.connection.return_value = conn
        yield cur


def test_api_happy_path(mock_secrets, mock_pool):
    from api.handler import handler  # noqa: PLC0415
    resp = handler({"queryStringParameters": {"limit": "5"}}, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body) == 1
    assert body[0]["distress_score"] == 0.85


def test_api_default_limit(mock_secrets, mock_pool):
    from api.handler import handler  # noqa: PLC0415
    handler({}, None)
    args, _ = mock_pool.execute.call_args
    assert args[1] == (10,)


def test_api_clamps_limit(mock_secrets, mock_pool):
    from api.handler import handler  # noqa: PLC0415
    handler({"queryStringParameters": {"limit": "999"}}, None)
    args, _ = mock_pool.execute.call_args
    assert args[1] == (100,)


def test_api_invalid_limit_falls_back(mock_secrets, mock_pool):
    from api.handler import handler  # noqa: PLC0415
    handler({"queryStringParameters": {"limit": "junk"}}, None)
    args, _ = mock_pool.execute.call_args
    assert args[1] == (10,)


def test_api_excludes_null_scores(mock_secrets, mock_pool):
    from api.handler import handler  # noqa: PLC0415
    handler({}, None)
    args, _ = mock_pool.execute.call_args
    assert "distress_score IS NOT NULL" in args[0]
