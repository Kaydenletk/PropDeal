import json
import os
from shared.db import get_pool
from shared.log import log
from shared.secrets import get_secret

DB_SECRET = os.environ["DB_SECRET_NAME"]


def _ensure_pool_inited():
    if "DATABASE_URL" not in os.environ:
        creds = get_secret(DB_SECRET)
        os.environ["DATABASE_URL"] = (
            f"postgresql://{creds['username']}:{creds['password']}"
            f"@{creds['host']}:{creds['port']}/{creds['dbname']}"
        )


def handler(event, _ctx):
    _ensure_pool_inited()
    qs = event.get("queryStringParameters") or {}
    try:
        limit = max(1, min(100, int(qs.get("limit", 10))))
    except ValueError:
        limit = 10

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT listing_id, address, city, state, zip, price, distress_score "
                "FROM listings WHERE distress_score IS NOT NULL "
                "ORDER BY distress_score DESC NULLS LAST LIMIT %s",
                (limit,),
            )
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    log("info", "api hit", count=len(rows), caller=event.get("requestContext", {}).get("identity", {}).get("userArn"))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(rows, default=str),
    }
