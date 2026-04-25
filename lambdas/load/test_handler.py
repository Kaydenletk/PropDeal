import json
from unittest.mock import patch, MagicMock
from handler import build_upsert_sql, lambda_handler


def test_build_upsert_sql_contains_on_conflict():
    sql = build_upsert_sql()
    assert "ON CONFLICT (listing_id)" in sql
    assert "DO UPDATE SET" in sql


@patch("handler.get_db_connection")
@patch("handler.boto3.client")
def test_lambda_handler_inserts_records(mock_boto, mock_conn):
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps([
            {
                "listing_id": "X",
                "city": "SA",
                "state": "TX",
                "address": "1 St",
                "price": 100000,
                "description": "nice",
                "distress_score": 0.3,
            }
        ]).encode())
    }
    mock_boto.return_value = mock_s3

    mock_cursor = MagicMock()
    mock_connection = MagicMock()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.return_value.__enter__.return_value = mock_connection

    event = {"clean_bucket": "clean", "enriched_key": "enriched-listings/x.json"}
    result = lambda_handler(event, None)
    assert result["statusCode"] == 200
    assert result["loaded"] == 1
    mock_cursor.execute.assert_called()
