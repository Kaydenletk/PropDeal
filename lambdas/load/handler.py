import json
import logging
import os
from contextlib import contextmanager

import boto3
import psycopg

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DB_SECRET_NAME = "proptech/rds/credentials"

MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS listings (
    listing_id          TEXT PRIMARY KEY,
    city                TEXT NOT NULL,
    state               TEXT NOT NULL,
    address             TEXT NOT NULL,
    price               INTEGER NOT NULL,
    bedrooms            SMALLINT,
    bathrooms           NUMERIC(3, 1),
    sqft                INTEGER,
    year_built          SMALLINT,
    description         TEXT,
    latitude            NUMERIC(10, 7),
    longitude           NUMERIC(10, 7),
    distress_score      NUMERIC(3, 2),
    distress_keywords   TEXT[],
    discount_percent    NUMERIC(5, 2),
    estimated_rent      INTEGER,
    cap_rate            NUMERIC(5, 2),
    final_score         NUMERIC(5, 2),
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_listings_city    ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_score   ON listings(final_score DESC);
"""


def build_upsert_sql() -> str:
    return """
    INSERT INTO listings (
        listing_id, city, state, address, price, bedrooms, bathrooms,
        sqft, year_built, description, latitude, longitude,
        distress_score, distress_keywords
    ) VALUES (
        %(listing_id)s, %(city)s, %(state)s, %(address)s, %(price)s,
        %(bedrooms)s, %(bathrooms)s, %(sqft)s, %(year_built)s,
        %(description)s, %(latitude)s, %(longitude)s,
        %(distress_score)s, %(distress_keywords)s
    )
    ON CONFLICT (listing_id) DO UPDATE SET
        price            = EXCLUDED.price,
        description      = EXCLUDED.description,
        distress_score   = EXCLUDED.distress_score,
        distress_keywords = EXCLUDED.distress_keywords,
        updated_at       = NOW();
    """


def get_db_creds() -> dict:
    secrets = boto3.client("secretsmanager")
    secret = secrets.get_secret_value(SecretId=DB_SECRET_NAME)
    return json.loads(secret["SecretString"])


@contextmanager
def get_db_connection():
    creds = get_db_creds()
    conn = psycopg.connect(
        host=creds["host"],
        port=creds["port"],
        dbname=creds["dbname"],
        user=creds["username"],
        password=creds["password"],
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lambda_handler(event, context):
    clean_bucket = event["clean_bucket"]
    enriched_key = event["enriched_key"]

    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=clean_bucket, Key=enriched_key)
    records = json.loads(obj["Body"].read())

    sql = build_upsert_sql()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(MIGRATION_SQL)
            for rec in records:
                rec.setdefault("distress_keywords", [])
                cur.execute(sql, rec)

    logger.info(f"Loaded {len(records)} records into RDS")
    return {"statusCode": 200, "loaded": len(records)}
