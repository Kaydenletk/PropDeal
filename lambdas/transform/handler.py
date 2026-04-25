import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def transform_record(raw: dict) -> dict:
    return {
        "listing_id": raw.get("id"),
        "address": raw.get("formattedAddress"),
        "city": raw.get("city"),
        "state": raw.get("state"),
        "price": raw.get("price"),
        "bedrooms": raw.get("bedrooms"),
        "bathrooms": raw.get("bathrooms"),
        "sqft": raw.get("squareFootage"),
        "year_built": raw.get("yearBuilt"),
        "description": raw.get("description"),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
    }


def lambda_handler(event, context):
    raw_bucket = event["raw_bucket"]
    raw_key = event["raw_key"]
    clean_bucket = event["clean_bucket"]

    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=raw_bucket, Key=raw_key)
    raw_records = json.loads(obj["Body"].read())

    clean_records = [transform_record(r) for r in raw_records if r.get("id")]

    clean_key = raw_key.replace("listings/", "clean-listings/")
    s3.put_object(
        Bucket=clean_bucket,
        Key=clean_key,
        Body=json.dumps(clean_records).encode("utf-8"),
        ContentType="application/json",
    )

    logger.info(f"Transformed {len(clean_records)} records to s3://{clean_bucket}/{clean_key}")
    return {
        "statusCode": 200,
        "records": len(clean_records),
        "clean_bucket": clean_bucket,
        "clean_key": clean_key,
    }
