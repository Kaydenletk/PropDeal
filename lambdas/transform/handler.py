import json
import os
import re
import boto3

from shared.log import log

S3 = boto3.client("s3")
RAW_BUCKET = os.environ["RAW_BUCKET"]
CLEAN_BUCKET = os.environ["CLEAN_BUCKET"]

PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def redact(text: str | None) -> str | None:
    if not text:
        return text
    text = PHONE_RE.sub("[PHONE_REDACTED]", text)
    text = EMAIL_RE.sub("[EMAIL_REDACTED]", text)
    return text


def handler(event, _ctx):
    raw_key = event["raw_key"]
    obj = S3.get_object(Bucket=RAW_BUCKET, Key=raw_key)
    listings = json.loads(obj["Body"].read())

    cleaned = []
    for rec in listings:
        rec["description"] = redact(rec.get("description"))
        cleaned.append(rec)

    clean_key = raw_key.replace("raw/", "clean/")
    S3.put_object(Bucket=CLEAN_BUCKET, Key=clean_key, Body=json.dumps(cleaned).encode())
    log("info", "transformed", count=len(cleaned), key=clean_key)
    return {"clean_key": clean_key, "count": len(cleaned)}
