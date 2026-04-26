import json
import os
import boto3

from shared.log import log
from shared.db import get_pool
from shared.secrets import get_secret

S3 = boto3.client("s3")
CLEAN_BUCKET = os.environ["CLEAN_BUCKET"]
DB_SECRET = os.environ["DB_SECRET_NAME"]


def _ensure_pool_inited():
    if "DATABASE_URL" not in os.environ:
        creds = get_secret(DB_SECRET)
        os.environ["DATABASE_URL"] = (
            f"postgresql://{creds['username']}:{creds['password']}"
            f"@{creds['host']}:{creds['port']}/{creds['dbname']}"
        )


UPSERT_SQL = """
INSERT INTO listings (
  listing_id, source, address, city, state, zip,
  latitude, longitude, price, bedrooms, bathrooms,
  square_feet, year_built, description,
  distress_score, distress_keywords, raw, enriched_at
) VALUES (
  %(listing_id)s, %(source)s, %(address)s, %(city)s, %(state)s, %(zip)s,
  %(latitude)s, %(longitude)s, %(price)s, %(bedrooms)s, %(bathrooms)s,
  %(square_feet)s, %(year_built)s, %(description)s,
  %(distress_score)s, %(distress_keywords)s, %(raw)s, now()
)
ON CONFLICT (listing_id) DO UPDATE SET
  distress_score = EXCLUDED.distress_score,
  distress_keywords = EXCLUDED.distress_keywords,
  enriched_at = now();
"""


def handler(event, _ctx):
    _ensure_pool_inited()
    key = event["enriched_key"]
    obj = S3.get_object(Bucket=CLEAN_BUCKET, Key=key)
    listings = json.loads(obj["Body"].read())

    rows = [
        {
            "listing_id": rec.get("id") or rec.get("listing_id"),
            "source": "rentcast",
            "address": rec.get("formattedAddress") or rec.get("address"),
            "city": rec.get("city"),
            "state": rec.get("state"),
            "zip": rec.get("zipCode") or rec.get("zip"),
            "latitude": rec.get("latitude"),
            "longitude": rec.get("longitude"),
            "price": rec.get("price"),
            "bedrooms": rec.get("bedrooms"),
            "bathrooms": rec.get("bathrooms"),
            "square_feet": rec.get("squareFootage") or rec.get("square_feet"),
            "year_built": rec.get("yearBuilt") or rec.get("year_built"),
            "description": rec.get("description"),
            "distress_score": rec.get("distress_score"),
            "distress_keywords": rec.get("distress_keywords") or [],
            "raw": json.dumps(rec),
        }
        for rec in listings
    ]

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, rows)
        conn.commit()

    log("info", "loaded", count=len(rows))
    return {"loaded": len(rows)}
