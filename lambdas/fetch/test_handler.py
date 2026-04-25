import json
from unittest.mock import patch, MagicMock
import pytest
from handler import lambda_handler, fetch_listings


@patch("handler.get_api_key", return_value="fake-key")
@patch("handler.boto3.client")
@patch("handler.requests.get")
def test_fetch_listings_calls_rentcast_and_uploads_to_s3(mock_get, mock_boto, mock_key):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = [
        {"id": "abc123", "price": 275000, "city": "San Antonio"}
    ]
    mock_s3 = MagicMock()
    mock_boto.return_value = mock_s3

    event = {"city": "San Antonio", "state": "TX"}
    result = lambda_handler(event, None)

    assert result["statusCode"] == 200
    assert result["records"] == 1
    mock_s3.put_object.assert_called_once()


@patch("handler.requests.get")
def test_fetch_listings_raises_on_api_error(mock_get):
    mock_get.return_value.status_code = 500
    mock_get.return_value.text = "Server error"

    with pytest.raises(RuntimeError, match="RentCast API error"):
        fetch_listings("San Antonio", "TX", api_key="fake")
