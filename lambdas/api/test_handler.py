import json
from unittest.mock import patch, MagicMock
from handler import lambda_handler, parse_limit


def test_parse_limit_default():
    assert parse_limit({}) == 10

def test_parse_limit_custom():
    assert parse_limit({"queryStringParameters": {"limit": "25"}}) == 25

def test_parse_limit_caps_at_100():
    assert parse_limit({"queryStringParameters": {"limit": "500"}}) == 100


@patch("handler.get_db_connection")
def test_lambda_handler_returns_top_deals(mock_conn):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("A", "San Antonio", "TX", "1 Main", 250000, 0.85)
    ]
    mock_cursor.description = [
        ("listing_id",), ("city",), ("state",), ("address",), ("price",), ("distress_score",)
    ]
    mock_connection = MagicMock()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.return_value.__enter__.return_value = mock_connection

    event = {"queryStringParameters": {"limit": "10"}}
    result = lambda_handler(event, None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body["deals"]) == 1
    assert body["deals"][0]["listing_id"] == "A"
