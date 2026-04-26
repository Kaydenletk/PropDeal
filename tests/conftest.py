import json
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def env_setup(monkeypatch):
    monkeypatch.setenv("RAW_BUCKET", "test-raw")
    monkeypatch.setenv("CLEAN_BUCKET", "test-clean")
    monkeypatch.setenv("RENTCAST_SECRET_NAME", "test/rentcast")
    monkeypatch.setenv("OPENAI_SECRET_NAME", "test/openai")
    monkeypatch.setenv("DB_SECRET_NAME", "test/rds")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "test")
    monkeypatch.setenv("MAX_LISTINGS_PER_RUN", "5")


@pytest.fixture
def sample_listing():
    return {
        "id": "abc-123",
        "formattedAddress": "123 Main St, Memphis, TN 38103",
        "city": "Memphis",
        "state": "TN",
        "zipCode": "38103",
        "latitude": 35.149,
        "longitude": -90.049,
        "price": 95000,
        "bedrooms": 3,
        "bathrooms": 2,
        "squareFootage": 1100,
        "yearBuilt": 1955,
        "description": "Motivated seller — as-is, cash only. Roof needs work.",
    }


@pytest.fixture
def mock_secrets():
    with patch("shared.secrets._SM") as mock:
        def get_secret(SecretId):
            if "rentcast" in SecretId:
                return {"SecretString": json.dumps({"RENTCAST_API_KEY": "test-key"})}
            if "openai" in SecretId:
                return {"SecretString": json.dumps({"OPENAI_API_KEY": "test-key"})}
            if "rds" in SecretId:
                return {"SecretString": json.dumps({
                    "username": "u", "password": "p", "host": "h",
                    "port": 5432, "dbname": "d",
                })}
        mock.get_secret_value.side_effect = get_secret
        yield mock
