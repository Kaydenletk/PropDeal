import json
import logging
import os

import boto3
from openai import OpenAI

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PROMPT = """You are a real estate distress signal detector.
Given a listing description, score 0.0–1.0 how likely the seller is MOTIVATED or DISTRESSED.
Distress signals: "motivated seller", "as-is", "fixer-upper", "TLC", "short sale",
"estate sale", "probate", "must sell", "cash only", "below market", "needs work".

Return ONLY valid JSON: {"score": <float>, "keywords": [<matched strings>]}

Description:
"""


def get_openai_key() -> str:
    secrets = boto3.client("secretsmanager")
    secret = secrets.get_secret_value(SecretId="proptech/openai/api-key")
    return json.loads(secret["SecretString"])["api_key"]


def call_openai(description: str, api_key: str) -> str:
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": PROMPT + description}],
        temperature=0,
        max_tokens=150,
    )
    return resp.choices[0].message.content


def score_distress(description: str, api_key: str = "") -> dict:
    if not description:
        return {"score": 0.0, "keywords": []}
    try:
        raw = call_openai(description, api_key)
        parsed = json.loads(raw)
        return {
            "score": float(parsed.get("score", 0.0)),
            "keywords": parsed.get("keywords", []),
        }
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning(f"Malformed OpenAI response: {e}")
        return {"score": 0.0, "keywords": []}


def lambda_handler(event, context):
    clean_bucket = event["clean_bucket"]
    clean_key = event["clean_key"]

    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=clean_bucket, Key=clean_key)
    records = json.loads(obj["Body"].read())

    api_key = get_openai_key()

    enriched = []
    for rec in records:
        distress = score_distress(rec.get("description", ""), api_key)
        rec["distress_score"] = distress["score"]
        rec["distress_keywords"] = distress["keywords"]
        enriched.append(rec)

    enriched_key = clean_key.replace("clean-listings/", "enriched-listings/")
    s3.put_object(
        Bucket=clean_bucket,
        Key=enriched_key,
        Body=json.dumps(enriched).encode("utf-8"),
        ContentType="application/json",
    )

    return {
        "statusCode": 200,
        "enriched": len(enriched),
        "clean_bucket": clean_bucket,
        "enriched_key": enriched_key,
    }
