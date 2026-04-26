import json
import os
from datetime import datetime
import boto3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from shared.log import log
from shared.secrets import get_secret

S3 = boto3.client("s3")
RAW_BUCKET = os.environ["RAW_BUCKET"]
SECRET_NAME = os.environ["RENTCAST_SECRET_NAME"]
MAX_LISTINGS = int(os.environ.get("MAX_LISTINGS_PER_RUN", "30"))


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        status_forcelist=[500, 502, 503, 504],
        backoff_factor=2,
        allowed_methods=["GET"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def fetch_listings(api_key: str, limit: int) -> list[dict]:
    sess = _session()
    headers = {"X-Api-Key": api_key}
    url = "https://api.rentcast.io/v1/listings/sale"
    params = {"limit": limit}
    resp = sess.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def handler(_event, _ctx):
    api_key = get_secret(SECRET_NAME)["RENTCAST_API_KEY"]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    raw_key = f"raw/{today}.json"

    try:
        listings = fetch_listings(api_key, MAX_LISTINGS)
    except requests.HTTPError as e:
        log("error", "rentcast fetch failed", status=e.response.status_code)
        listings = []
        raw_key = f"raw/{today}_partial.json"

    S3.put_object(Bucket=RAW_BUCKET, Key=raw_key, Body=json.dumps(listings).encode())
    log("info", "fetched", count=len(listings), key=raw_key)
    return {"raw_key": raw_key, "count": len(listings)}
