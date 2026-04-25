import json
import logging
import os
import pathlib
from contextlib import contextmanager

import boto3
import psycopg

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DB_SECRET_NAME = "proptech/rds/credentials"

_HERE = pathlib.Path(__file__).parent
# Try Lambda-packaged path first, fall back to source-repo path.
# Packaging script bundles sql/migrations/ alongside handler.py inside the zip;
# in the source repo the migrations live at <repo>/sql/migrations/ (../../ from handler).
_MIGRATION_PATHS = [
    _HERE / "sql" / "migrations" / "001_initial.sql",          # packaged
    _HERE / ".." / ".." / "sql" / "migrations" / "001_initial.sql",  # source repo
]
for _p in _MIGRATION_PATHS:
    if _p.exists():
        MIGRATION_SQL = _p.read_text()
        break
else:
    raise FileNotFoundError(
        f"sql/migrations/001_initial.sql not found in any of {_MIGRATION_PATHS}"
    )

_MIGRATED = False


def ensure_schema(cur: "psycopg.Cursor") -> None:
    """Apply migration once per warm container."""
    global _MIGRATED
    if not _MIGRATED:
        cur.execute(MIGRATION_SQL)
        _MIGRATED = True


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
            ensure_schema(cur)
            for rec in records:
                rec.setdefault("distress_keywords", [])
                cur.execute(sql, rec)

    logger.info(f"Loaded {len(records)} records into RDS")
    return {"statusCode": 200, "loaded": len(records)}
