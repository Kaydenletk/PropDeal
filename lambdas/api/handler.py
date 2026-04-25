import json
import logging
from contextlib import contextmanager

import boto3
import psycopg

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def parse_limit(event: dict) -> int:
    qs = event.get("queryStringParameters") or {}
    try:
        limit = int(qs.get("limit", 10))
    except (ValueError, TypeError):
        limit = 10
    return min(max(limit, 1), 100)


def get_db_creds() -> dict:
    secrets = boto3.client("secretsmanager")
    secret = secrets.get_secret_value(SecretId="proptech/rds/credentials")
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
    finally:
        conn.close()


def lambda_handler(event, context):
    limit = parse_limit(event)

    sql = """
        SELECT listing_id, city, state, address, price, distress_score
        FROM listings
        WHERE distress_score IS NOT NULL
        ORDER BY distress_score DESC NULLS LAST, price ASC
        LIMIT %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"deals": rows}, default=str),
    }
