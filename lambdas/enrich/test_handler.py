import json
from unittest.mock import patch, MagicMock
from handler import score_distress, lambda_handler


@patch("handler.call_openai")
def test_score_distress_returns_float(mock_openai):
    mock_openai.return_value = '{"score": 0.85, "keywords": ["motivated seller"]}'
    result = score_distress("Motivated seller, needs TLC")
    assert result["score"] == 0.85
    assert "motivated seller" in result["keywords"]


@patch("handler.call_openai")
def test_score_distress_handles_malformed_response(mock_openai):
    mock_openai.return_value = "not json"
    result = score_distress("some description")
    assert result["score"] == 0.0
    assert result["keywords"] == []


@patch("handler.get_openai_key", return_value="fake")
@patch("handler.call_openai")
@patch("handler.boto3.client")
def test_lambda_handler_enriches_records(mock_boto, mock_openai, mock_key):
    mock_openai.return_value = '{"score": 0.5, "keywords": []}'
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps([
            {"listing_id": "A", "description": "nice home"}
        ]).encode())
    }
    mock_boto.return_value = mock_s3

    event = {"clean_bucket": "clean", "clean_key": "clean-listings/x.json"}
    result = lambda_handler(event, None)
    assert result["statusCode"] == 200
    assert result["enriched"] == 1
