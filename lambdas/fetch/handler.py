import json
import os
import logging
from datetime import datetime, timezone

import boto3
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

RENTCAST_API_URL = "https://api.rentcast.io/v1/listings/sale"
RAW_BUCKET = os.environ.get("RAW_BUCKET", "")


def fetch_listings(city: str, state: str, api_key: str) -> list[dict]:
    params = {"city": city, "state": state, "limit": 500}
    headers = {"X-Api-Key": api_key}
    response = requests.get(RENTCAST_API_URL, params=params, headers=headers, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"RentCast API error {response.status_code}: {response.text}")
    return response.json()


def get_api_key() -> str:
    secrets = boto3.client("secretsmanager")
    secret = secrets.get_secret_value(SecretId="proptech/rentcast/api-key")
    return json.loads(secret["SecretString"])["api_key"]


def lambda_handler(event, context):
    city = event.get("city", "San Antonio")
    state = event.get("state", "TX")
    api_key = get_api_key()

    listings = fetch_listings(city, state, api_key)

    s3 = boto3.client("s3")
    key = f"listings/{city.lower().replace(' ', '-')}/{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    s3.put_object(
        Bucket=RAW_BUCKET,
        Key=key,
        Body=json.dumps(listings).encode("utf-8"),
        ContentType="application/json",
    )

    logger.info(f"Wrote {len(listings)} listings to s3://{RAW_BUCKET}/{key}")
    return {"statusCode": 200, "records": len(listings), "s3_key": key}
