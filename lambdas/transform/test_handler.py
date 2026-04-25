import json
from unittest.mock import patch, MagicMock
from handler import transform_record, lambda_handler


def test_transform_record_normalizes_fields():
    raw = {
        "id": "ABC123",
        "formattedAddress": "123 Main St, San Antonio, TX 78201",
        "city": "San Antonio",
        "state": "TX",
        "price": 275000,
        "bedrooms": 3,
        "bathrooms": 2.0,
        "squareFootage": 1800,
        "yearBuilt": 1985,
        "description": "Motivated seller, needs TLC",
        "latitude": 29.4241,
        "longitude": -98.4936,
    }
    result = transform_record(raw)
    assert result["listing_id"] == "ABC123"
    assert result["sqft"] == 1800
    assert result["description"] == "Motivated seller, needs TLC"
    assert result["price"] == 275000


def test_transform_record_handles_missing_optional_fields():
    raw = {"id": "X", "formattedAddress": "1 St", "city": "SA", "state": "TX", "price": 100000}
    result = transform_record(raw)
    assert result["sqft"] is None
    assert result["description"] is None


@patch("handler.boto3.client")
def test_lambda_handler_reads_raw_writes_clean(mock_boto):
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps([
            {"id": "A", "formattedAddress": "1 St", "city": "SA", "state": "TX", "price": 100000}
        ]).encode())
    }
    mock_boto.return_value = mock_s3

    event = {"raw_bucket": "raw", "raw_key": "listings/san-antonio/2026-04-24.json", "clean_bucket": "clean"}
    result = lambda_handler(event, None)
    assert result["statusCode"] == 200
    assert result["records"] == 1
    mock_s3.put_object.assert_called_once()
