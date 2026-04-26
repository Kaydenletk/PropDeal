import json
import os
import time
import boto3
from openai import OpenAI, RateLimitError, APIError

from shared.log import log
from shared.secrets import get_secret

S3 = boto3.client("s3")
CLEAN_BUCKET = os.environ["CLEAN_BUCKET"]
SECRET_NAME = os.environ["OPENAI_SECRET_NAME"]
MAX_RETRIES = 3
BACKOFF_SECONDS = 2

# Module-scoped client (one per warm container)
_CLIENT: OpenAI | None = None


def _client() -> OpenAI:
    global _CLIENT
    if _CLIENT is None:
        api_key = get_secret(SECRET_NAME)["OPENAI_API_KEY"]
        _CLIENT = OpenAI(api_key=api_key)
    return _CLIENT


PROMPT_VERSION = "v3"
PROMPT = """You are scoring real-estate listings for distress signals.
Return JSON: {"score": float 0-1, "keywords": [strings]}
0 = no distress, 1 = highly distressed (foreclosure / motivated / as-is / fixer / probate / cash only).
Listing description:
"""


def score_one(description: str) -> tuple[float | None, list[str]]:
    for attempt in range(MAX_RETRIES):
        try:
            resp = _client().chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": PROMPT + description}],
                temperature=0,
                response_format={"type": "json_object"},
            )
            payload = json.loads(resp.choices[0].message.content)
            return float(payload["score"]), list(payload.get("keywords", []))
        except RateLimitError:
            if attempt == MAX_RETRIES - 1:
                log("warning", "openai rate limit exhausted, score=NULL")
                return None, []
            time.sleep(BACKOFF_SECONDS * (2 ** attempt))
        except (APIError, json.JSONDecodeError, KeyError, ValueError) as e:
            log("error", "openai score failed", error=str(e))
            return None, []
    return None, []


def handler(event, _ctx):
    key = event["clean_key"]
    enriched_key = key.replace("/clean/", "/enriched/")

    # Idempotency: skip if already enriched
    try:
        S3.head_object(Bucket=CLEAN_BUCKET, Key=enriched_key)
        log("info", "skip enrich, already exists", key=enriched_key)
        return {"enriched_key": enriched_key, "skipped": True}
    except S3.exceptions.ClientError:
        pass

    obj = S3.get_object(Bucket=CLEAN_BUCKET, Key=key)
    listings = json.loads(obj["Body"].read())

    for rec in listings:
        score, keywords = score_one(rec.get("description", "") or "")
        rec["distress_score"] = score  # may be None on failure -> SQL NULL downstream
        rec["distress_keywords"] = keywords
        rec["prompt_version"] = PROMPT_VERSION

    S3.put_object(Bucket=CLEAN_BUCKET, Key=enriched_key, Body=json.dumps(listings).encode())
    log("info", "enriched", count=len(listings), key=enriched_key)
    return {"enriched_key": enriched_key, "count": len(listings), "skipped": False}
