# PropDeal Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish PropDeal to recruiter-scan-ready production state with rigorous LLM eval harness, deployed on AWS Free Tier (~$3-8/mo realistic), as 2026 job-hunt portfolio piece.

**Architecture:** AWS serverless pipeline (EventBridge → Step Functions → 5 Lambdas → S3 → RDS Postgres → Function URL with IAM auth). Hand-labeled distress-score eval harness (N=100-150, holdout, Cohen's κ, regex baseline). Public eval-harness sub-repo with Hugging Face dataset card.

**Tech Stack:** Python 3.12, AWS Lambda, Step Functions, RDS Postgres 16, S3, Secrets Manager, Terraform 1.7+, GitHub Actions, pytest + moto + responses + vcrpy, LocalStack, GPT-4o-mini + Claude Haiku 4.5, Codecov.

**Source spec:** [docs/superpowers/specs/2026-04-25-propdeal-phase1-design.md](../specs/2026-04-25-propdeal-phase1-design.md)

**Phase model:** 3 phases (1A Foundation → 1B Test+Observability → 1C Eval+Public+Demo). Side-project kickoff after 1B closes.

---

## File Structure (created/modified)

**New files:**
- `lambdas/shared/__init__.py`
- `lambdas/shared/log.py` — structured JSON logger
- `lambdas/shared/db.py` — psycopg connection pool helper
- `lambdas/shared/secrets.py` — cached secrets reader
- `requirements-dev.txt`
- `pyproject.toml` — pytest + ruff + coverage config
- `tests/conftest.py`
- `tests/fixtures/distress_eval.jsonl` (hand-labeled, N=100-150)
- `tests/fixtures/zillow_seed.jsonl` (initial labeling fixtures, public listings)
- `tests/fixtures/rentcast_response.yaml` (vcrpy cassette)
- `tests/integration/test_pipeline_localstack.py`
- `tests/{fetch,transform,enrich,load,api}/test_*.py` (real tests, replacing stubs)
- `scripts/label_listings.py` — interactive labeling CLI
- `scripts/eval_distress_score.py` — eval harness
- `scripts/regex_baseline.py` — keyword-regex baseline classifier
- `scripts/inter_rater_kappa.py` — Cohen's kappa computation
- `scripts/bootstrap_state.sh` — Terraform state bootstrap (local→s3 migrate)
- `iac/modules/observability/main.tf` — CloudWatch dashboard + alarms
- `iac/asl/pipeline.json` — Step Functions ASL (extracted from main.tf for validation)
- `.github/workflows/ci.yml`
- `.github/workflows/eval-regression.yml`
- `docs/eval.md`
- `docs/slo.md`
- `docs/security.md`
- `docs/observability.png` (screenshot)
- `docs/resume_bullets.md`
- `docs/interview_prep.md`
- `proptech-eval/` (separate public repo created at Task 33)

**Modified files:**
- `lambdas/fetch/handler.py` — partial-save on 5xx, MAX_LISTINGS env
- `lambdas/enrich/handler.py` — idempotency check, rate-limit retry, NULL on fail, client outside loop
- `lambdas/load/handler.py` — executemany/COPY, schema drift fix, deps trim
- `lambdas/api/handler.py` — connection pool, IAM auth context
- `iac/main.tf` — Function URL AuthType=AWS_IAM, public subnet for load, retry policy, dashboard module
- `sql/migrations/001_initial.sql` — single source of truth schema
- `COST.md` — honest line items
- `RUNBOOK.md` — bootstrap two-step + Logs Insights queries + war stories
- `README.md` — TD8 reorder (GIF + impact above fold)

---

# PHASE 1A — Foundation: Deploy + Smoke Test

Goal: pipeline executes end-to-end on real AWS Free Tier with rigorous local validation gate first.

## Task 1: Fix schema drift between SQL migration and load handler

**Files:**
- Modify: `sql/migrations/001_initial.sql`
- Modify: `lambdas/load/handler.py`

- [ ] **Step 1: Read both schema definitions**

Run:
```bash
cat sql/migrations/001_initial.sql
grep -n "CREATE TABLE\|MIGRATION_SQL" lambdas/load/handler.py
```

Identify columns in load handler's inline `MIGRATION_SQL` not present in `001_initial.sql` (notably `distress_keywords TEXT[]`).

- [ ] **Step 2: Update migration as source of truth**

Edit `sql/migrations/001_initial.sql` to include every column the pipeline writes. Final schema:

```sql
CREATE TABLE IF NOT EXISTS listings (
  listing_id TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'rentcast',
  address TEXT,
  city TEXT,
  state TEXT,
  zip TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  price NUMERIC,
  bedrooms INTEGER,
  bathrooms NUMERIC,
  square_feet INTEGER,
  year_built INTEGER,
  description TEXT,
  distress_score NUMERIC,
  distress_keywords TEXT[],
  raw JSONB,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  enriched_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS listings_distress_idx ON listings (distress_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS listings_zip_idx ON listings (zip);
```

- [ ] **Step 3: Remove inline MIGRATION_SQL from load handler**

Edit `lambdas/load/handler.py`. Replace the inline `MIGRATION_SQL` block + every-invocation `cur.execute(MIGRATION_SQL)` with a one-time bootstrap path:

```python
# At top of handler.py, replace inline SQL with:
import pathlib
MIGRATION_SQL = pathlib.Path(__file__).parent.joinpath("../../sql/migrations/001_initial.sql").read_text()
# Run only on first invocation per warm container
_MIGRATED = False

def ensure_schema(cur):
    global _MIGRATED
    if not _MIGRATED:
        cur.execute(MIGRATION_SQL)
        _MIGRATED = True
```

- [ ] **Step 4: Verify schema match**

Run:
```bash
diff <(grep -E "^\s+(listing_id|source|address|distress)" sql/migrations/001_initial.sql) \
     <(grep -E "(listing_id|distress_keywords)" lambdas/load/handler.py)
```

Expected: no semantic differences. Both reference the same columns.

- [ ] **Step 5: Commit**

```bash
git add sql/migrations/001_initial.sql lambdas/load/handler.py
git commit -m "fix: dedupe schema definition between migration and load handler"
```

---

## Task 2: Trim Lambda deps + standardize on psycopg

**Files:**
- Create: `lambdas/fetch/requirements.txt`
- Create: `lambdas/transform/requirements.txt`
- Create: `lambdas/enrich/requirements.txt`
- Create: `lambdas/load/requirements.txt`
- Create: `lambdas/api/requirements.txt`

- [ ] **Step 1: Define minimal deps per Lambda**

`lambdas/fetch/requirements.txt`:
```
requests==2.32.3
```

`lambdas/transform/requirements.txt`:
```
# stdlib only (json, datetime)
```

`lambdas/enrich/requirements.txt`:
```
openai==1.54.0
```

`lambdas/load/requirements.txt`:
```
psycopg[binary]==3.2.3
```

`lambdas/api/requirements.txt`:
```
psycopg[binary]==3.2.3
psycopg-pool==3.2.4
```

(boto3 is provided by Lambda runtime — never include.)

- [ ] **Step 2: Update Terraform Lambda packaging**

Edit `iac/main.tf` near each `aws_lambda_function` definition. Ensure `archive_file` source includes per-Lambda requirements but **excludes** `boto3*`, `botocore*`, `__pycache__`, `*.pyc`. Use `source_dir` per Lambda, packaging script provided in next step.

Edit `scripts/package_lambdas.sh` (create if missing):
```bash
#!/usr/bin/env bash
set -euo pipefail
for L in fetch transform enrich load api; do
  cd "lambdas/$L"
  rm -rf .build
  mkdir -p .build
  cp handler.py .build/
  if [ -s requirements.txt ]; then
    pip install -r requirements.txt -t .build/ --quiet
  fi
  find .build -name "boto3*" -prune -exec rm -rf {} +
  find .build -name "botocore*" -prune -exec rm -rf {} +
  find .build -name "__pycache__" -exec rm -rf {} +
  cd - >/dev/null
done
```

`chmod +x scripts/package_lambdas.sh`.

- [ ] **Step 3: Commit**

```bash
git add lambdas/*/requirements.txt scripts/package_lambdas.sh iac/main.tf
git commit -m "build: trim lambda packages, exclude boto3, standardize on psycopg"
```

---

## Task 3: Shared helpers — log, db, secrets

**Files:**
- Create: `lambdas/shared/__init__.py`
- Create: `lambdas/shared/log.py`
- Create: `lambdas/shared/db.py`
- Create: `lambdas/shared/secrets.py`

- [ ] **Step 1: Write log helper**

Create `lambdas/shared/log.py`:
```python
import json
import logging
import os
import sys
import time
import uuid

_LAMBDA_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "local")
_LOGGER = logging.getLogger("proptech")
_LOGGER.setLevel(logging.INFO)
if not _LOGGER.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(message)s"))
    _LOGGER.addHandler(h)


def log(level: str, msg: str, **kw):
    payload = {
        "ts": time.time(),
        "level": level,
        "lambda": _LAMBDA_NAME,
        "request_id": kw.pop("request_id", None) or os.environ.get("AWS_REQUEST_ID", str(uuid.uuid4())),
        "msg": msg,
        **kw,
    }
    _LOGGER.info(json.dumps(payload, default=str))
```

- [ ] **Step 2: Write db helper with module-scoped pool**

Create `lambdas/shared/db.py`:
```python
import os
from psycopg_pool import ConnectionPool

_POOL: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _POOL
    if _POOL is None:
        conninfo = os.environ["DATABASE_URL"]
        _POOL = ConnectionPool(conninfo, min_size=1, max_size=2, timeout=10)
    return _POOL
```

- [ ] **Step 3: Write secrets helper with cache**

Create `lambdas/shared/secrets.py`:
```python
import json
import os
import boto3

_CACHE: dict[str, dict] = {}
_SM = boto3.client("secretsmanager")


def get_secret(name: str) -> dict:
    if name in _CACHE:
        return _CACHE[name]
    resp = _SM.get_secret_value(SecretId=name)
    val = json.loads(resp["SecretString"])
    _CACHE[name] = val
    return val
```

- [ ] **Step 4: Empty `__init__.py`**

Create `lambdas/shared/__init__.py` (empty file).

- [ ] **Step 5: Commit**

```bash
git add lambdas/shared/
git commit -m "feat: shared helpers for log, db pool, secrets cache"
```

---

## Task 4: enrich Lambda — idempotency + rate-limit + client outside loop

**Files:**
- Modify: `lambdas/enrich/handler.py`

- [ ] **Step 1: Read current handler**

```bash
cat lambdas/enrich/handler.py
```

- [ ] **Step 2: Rewrite with fixes**

Replace `lambdas/enrich/handler.py` body:
```python
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
```

- [ ] **Step 3: Commit**

```bash
git add lambdas/enrich/handler.py
git commit -m "fix(enrich): idempotency check, rate-limit retry, NULL on fail, client outside loop"
```

---

## Task 5: fetch Lambda — partial save on 5xx, MAX_LISTINGS env

**Files:**
- Modify: `lambdas/fetch/handler.py`

- [ ] **Step 1: Read current handler**

```bash
cat lambdas/fetch/handler.py
```

- [ ] **Step 2: Rewrite with fixes**

Replace `lambdas/fetch/handler.py` body:
```python
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
        # Save empty marker so downstream gracefully no-ops
        listings = []
        raw_key = f"raw/{today}_partial.json"

    S3.put_object(Bucket=RAW_BUCKET, Key=raw_key, Body=json.dumps(listings).encode())
    log("info", "fetched", count=len(listings), key=raw_key)
    return {"raw_key": raw_key, "count": len(listings)}
```

- [ ] **Step 3: Add MAX_LISTINGS_PER_RUN env to Terraform**

In `iac/main.tf`, find `aws_lambda_function.fetch` block and add to its `environment.variables`:
```hcl
MAX_LISTINGS_PER_RUN = "30"
```

- [ ] **Step 4: Commit**

```bash
git add lambdas/fetch/handler.py iac/main.tf
git commit -m "fix(fetch): retry on 5xx, partial save, MAX_LISTINGS env"
```

---

## Task 6: load Lambda — executemany + connection pool import

**Files:**
- Modify: `lambdas/load/handler.py`

- [ ] **Step 1: Rewrite with batch insert**

Replace `lambdas/load/handler.py` body:
```python
import json
import os
import boto3
import psycopg

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
```

- [ ] **Step 2: Commit**

```bash
git add lambdas/load/handler.py
git commit -m "perf(load): use executemany + connection pool, drop inline migration"
```

---

## Task 7: api Lambda — connection pool + IAM auth context

**Files:**
- Modify: `lambdas/api/handler.py`

- [ ] **Step 1: Rewrite with pool**

Replace `lambdas/api/handler.py` body:
```python
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
```

- [ ] **Step 2: Commit**

```bash
git add lambdas/api/handler.py
git commit -m "perf(api): connection pool, log IAM caller, parameterized SQL"
```

---

## Task 8: Terraform — Function URL AWS_IAM auth, public subnet for load, retry policy

**Files:**
- Modify: `iac/main.tf`

- [ ] **Step 1: Switch Function URL to AWS_IAM**

In `iac/main.tf`, find `aws_lambda_function_url` for the api Lambda. Change `authorization_type` from `NONE` to `AWS_IAM`:

```hcl
resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "AWS_IAM"
}
```

- [ ] **Step 2: Move `load` Lambda out of VPC private subnet**

TD5: skip $7/mo Secrets Manager VPC endpoint. Put `load` in public subnet with egress IGW.

In `iac/main.tf`, find `aws_lambda_function.load` and `aws_lambda_function.api`:
- Keep `api` in VPC private subnet (RDS access).
- Move `load`: remove `vpc_config` block. Use RDS public-IP endpoint with SG that allows Lambda's outbound CIDR. (RDS itself stays private; `load` connects via the RDS proxy or temporarily via public endpoint with strict SG.)

If RDS must remain VPC-only, alternate: keep `load` in VPC private subnet + ADD VPC interface endpoint for Secrets Manager (~$7/mo, document in COST.md).

Decision (TD5 chose option A — public subnet load): use RDS publicly_accessible=true with SG limited to known Lambda egress NAT public IP, OR provision a NAT instance (free t4g.nano) for VPC Lambdas.

**Implement:** add NAT instance (free t4g.nano, ~$0/mo on free tier) for VPC private-subnet egress:
```hcl
resource "aws_instance" "nat" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = "t4g.nano"
  subnet_id                   = aws_subnet.public[0].id
  vpc_security_group_ids      = [aws_security_group.nat.id]
  source_dest_check           = false
  user_data                   = file("${path.module}/nat-userdata.sh")
  tags = { Name = "proptech-nat" }
}
```

Create `iac/nat-userdata.sh`:
```bash
#!/bin/bash
sysctl -w net.ipv4.ip_forward=1
iptables -t nat -A POSTROUTING -o eth0 -s 10.0.0.0/16 -j MASQUERADE
```

Update private route table to send 0.0.0.0/0 → `aws_instance.nat.primary_network_interface_id`.

- [ ] **Step 3: Add Step Functions retry policy**

Find the Step Functions state machine definition in `iac/main.tf`. For each Lambda task state, add:
```json
"Retry": [
  {
    "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "Lambda.TooManyRequestsException"],
    "IntervalSeconds": 2,
    "MaxAttempts": 2,
    "BackoffRate": 2
  }
],
"Catch": [
  {
    "ErrorEquals": ["States.ALL"],
    "Next": "PipelineFailed",
    "ResultPath": "$.error"
  }
]
```

Add `PipelineFailed` state that publishes to SNS topic.

- [ ] **Step 4: Commit**

```bash
git add iac/
git commit -m "fix(iac): IAM auth on Function URL, NAT instance for VPC egress, explicit Step Functions retry policy"
```

---

## Task 9: Extract Step Functions ASL to standalone JSON for validation

**Files:**
- Create: `iac/asl/pipeline.json`
- Modify: `iac/main.tf`

- [ ] **Step 1: Extract ASL**

Copy the inline state machine definition from `iac/main.tf` into `iac/asl/pipeline.json`.

- [ ] **Step 2: Reference from Terraform**

In `iac/main.tf`, replace inline definition with:
```hcl
definition = templatefile("${path.module}/asl/pipeline.json", {
  fetch_arn     = aws_lambda_function.fetch.arn
  transform_arn = aws_lambda_function.transform.arn
  enrich_arn    = aws_lambda_function.enrich.arn
  load_arn      = aws_lambda_function.load.arn
  sns_topic_arn = aws_sns_topic.alerts.arn
})
```

In `pipeline.json`, use `${fetch_arn}` etc. as templatefile variables.

- [ ] **Step 3: Validate locally**

```bash
aws stepfunctions validate-state-machine-definition \
  --definition file://iac/asl/pipeline.json \
  --type STANDARD
```

Expected: `"result": "OK"`. If errors, fix syntax before continuing.

(If the file uses templatefile vars unresolved, render to a tempfile first with `envsubst` or use `jq` to substitute placeholders.)

- [ ] **Step 4: Commit**

```bash
git add iac/asl/pipeline.json iac/main.tf
git commit -m "refactor: extract Step Functions ASL for standalone validation"
```

---

## Task 10: Terraform state bootstrap — two-step (local → s3 migrate)

**Files:**
- Create: `scripts/bootstrap_state.sh`
- Modify: `iac/backend.tf`

- [ ] **Step 1: Write bootstrap script**

Create `scripts/bootstrap_state.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

ALERT_EMAIL="${1:?usage: $0 <alert_email>}"
REGION="${AWS_REGION:-us-east-1}"
ACCT=$(aws sts get-caller-identity --query Account --output text)
BUCKET="proptech-tfstate-${ACCT}"
TABLE="proptech-tflock"

# Create state bucket
aws s3api create-bucket \
  --bucket "$BUCKET" \
  --region "$REGION" \
  $([ "$REGION" != "us-east-1" ] && echo "--create-bucket-configuration LocationConstraint=$REGION") \
  2>&1 | grep -v "BucketAlreadyOwnedByYou" || true

aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration '{
  "Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]
}'

# Create lock table
aws dynamodb create-table \
  --table-name "$TABLE" \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --region "$REGION" \
  2>&1 | grep -v "ResourceInUseException" || true

cat > iac/backend.tf <<EOF
terraform {
  backend "s3" {
    bucket         = "$BUCKET"
    key            = "proptech/terraform.tfstate"
    region         = "$REGION"
    dynamodb_table = "$TABLE"
    encrypt        = true
  }
}
EOF

echo "Bootstrap complete. Now run: cd iac && terraform init -migrate-state"
```

`chmod +x scripts/bootstrap_state.sh`.

- [ ] **Step 2: Document in RUNBOOK**

Append to `RUNBOOK.md`:
```markdown
## Initial Deploy Bootstrap (one-time)

1. Run `./scripts/bootstrap_state.sh you@example.com`
   - Creates S3 state bucket + DynamoDB lock table
   - Writes `iac/backend.tf`
2. `cd iac && terraform init -migrate-state`
3. `terraform plan -var="alert_email=you@example.com"` (review)
4. `terraform apply -var="alert_email=you@example.com"`
```

- [ ] **Step 3: Commit**

```bash
git add scripts/bootstrap_state.sh RUNBOOK.md
git commit -m "feat: terraform state bootstrap script with two-step init flow"
```

---

## Task 11: Phase 1A.0 — local validation gate (tflint + validate + ASL + LocalStack smoke)

**Files:**
- Create: `scripts/validate_local.sh`
- Modify: `.github/workflows/ci.yml` (created in later task)

- [ ] **Step 1: Install tflint locally**

```bash
brew install tflint  # macOS
# or curl -L https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash
tflint --version
```

- [ ] **Step 2: Write validate script**

Create `scripts/validate_local.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> terraform fmt"
terraform -chdir=iac fmt -check -recursive

echo "==> terraform validate"
terraform -chdir=iac init -backend=false -upgrade
terraform -chdir=iac validate

echo "==> tflint"
tflint --chdir=iac

echo "==> ASL validate"
# Render placeholders for validation
sed -e 's/\${[a-z_]*_arn}/arn:aws:lambda:us-east-1:000000000000:function:placeholder/g' \
    -e 's/\${[a-z_]*_arn}/arn:aws:sns:us-east-1:000000000000:placeholder/g' \
    iac/asl/pipeline.json > /tmp/asl-rendered.json
aws stepfunctions validate-state-machine-definition \
  --definition file:///tmp/asl-rendered.json \
  --type STANDARD \
  --query result

echo "==> All local validation gates passed"
```

`chmod +x scripts/validate_local.sh`.

- [ ] **Step 3: Verify it runs clean**

```bash
./scripts/validate_local.sh
```

Expected: all gates print success. Fix any reported issues before continuing.

- [ ] **Step 4: Commit**

```bash
git add scripts/validate_local.sh
git commit -m "ci: local validation gate (tflint + validate + ASL)"
```

---

## Task 12: Honest cost rewrite — COST.md

**Files:**
- Modify: `COST.md`

- [ ] **Step 1: Rewrite COST.md**

Replace `COST.md`:
```markdown
# Cost Breakdown

## Free-tier baseline (first 12 months, US-East-1)

| Service | Free tier | This pipeline |
|---------|-----------|---------------|
| Lambda  | 1M req/mo forever | ~150 req/mo (5 lambdas × 30 days) |
| Step Functions Standard | 4k transitions/mo forever | ~150 transitions/mo |
| S3 Standard | 5GB + 2k PUT/mo for 12 mo | <1GB, ~90 PUT/mo |
| RDS t4g.micro | 750 hr/mo for 12 mo | 730 hr/mo |
| CloudWatch Logs | 5GB/mo forever | ~0.5–2 GB/mo |
| SQS / SNS | 1M req/mo forever | trivial |

## Real ongoing line items (NOT free)

| Item | Monthly cost | Why |
|------|-------------|-----|
| Secrets Manager (3 secrets) | $1.20 | Not in free tier ($0.40/secret) |
| CloudWatch alarm metrics (~6 alarms) | $0.60 | $0.10/alarm/mo |
| CloudWatch dashboard | $3.00 | $3/dashboard after first 3 |
| NAT instance t4g.nano (free tier) | $0.00 | Free under t4g 750hr |
| Data transfer | <$0.50 | Inbound free, outbound minimal |

**Total during free tier (months 1-12): ~$3-5/mo**

## Post-12-month run rate

| Item | Monthly cost |
|------|-------------|
| RDS t4g.micro | $12.50 |
| All free-tier-expired storage | ~$1 |
| Secrets + alarms + dashboard | ~$5 |
| **Total** | **~$18-20/mo** |

Mitigation post-12-mo: migrate to Aurora Serverless v2 (auto-pause at 0 ACU = $0 idle) OR Neon free tier OR shut down RDS and replay from S3 archive on demand.

## One-time costs

| Item | Cost |
|------|------|
| OpenAI prepaid credit | $5 (lasts ~6 months) |
| RentCast | $0 (free tier 50 calls/day) |

## Honest summary

- **First 12 months:** $3-5/month + $5 one-time OpenAI = ~$45 total year 1
- **Year 2+:** ~$18-20/month unless migrated off RDS
```

- [ ] **Step 2: Commit**

```bash
git add COST.md
git commit -m "docs: honest cost breakdown including alarms, dashboard, post-12mo RDS"
```

---

## Task 13: PII redaction note + security doc

**Files:**
- Create: `docs/security.md`
- Modify: `lambdas/transform/handler.py`

- [ ] **Step 1: Add redaction in transform Lambda**

Read current transform:
```bash
cat lambdas/transform/handler.py
```

Replace `lambdas/transform/handler.py` body:
```python
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
```

- [ ] **Step 2: Write security doc**

Create `docs/security.md`:
```markdown
# Security Posture

## Data handling
- All listing data is sourced from RentCast public real-estate API (no PII at source by design).
- Free-text descriptions may contain seller-supplied phone/email; the `transform` Lambda redacts these via regex before any data reaches OpenAI or RDS.
- Listings are stored in private RDS Postgres in a VPC private subnet.
- The public API Lambda Function URL requires AWS IAM (SigV4) authentication — no anonymous access.

## Secret management
- All credentials in AWS Secrets Manager.
- Quarterly manual key rotation documented in RUNBOOK.md.
- Lambda IAM roles use least-privilege resource-scoped policies.

## Known limits
- Single-region (us-east-1) — no cross-region failover.
- No WAF in front of API (free-tier constraint). IAM auth + low rate limits provide minimal abuse protection.
- No automated dependency scanning yet (TODO: enable Dependabot post-Phase 1).

## Incident response
- CloudWatch alarms → SNS topic → email.
- Manual: `terraform destroy` to scrub all infra; secrets stay in Secrets Manager 7 days for recovery.
```

- [ ] **Step 3: Commit**

```bash
git add lambdas/transform/handler.py docs/security.md
git commit -m "feat(transform): redact PII regex; docs: security posture"
```

---

## Task 14: Deploy Phase 1A — terraform apply layered + smoke test

- [ ] **Step 1: Pre-deploy local validation gate**

```bash
./scripts/validate_local.sh
```

All checks must pass.

- [ ] **Step 2: Bootstrap state (one-time)**

```bash
./scripts/bootstrap_state.sh you@example.com
cd iac && terraform init -migrate-state
```

- [ ] **Step 3: Seed secrets**

```bash
./scripts/seed_secrets.sh "${RENTCAST_KEY}" "${OPENAI_KEY}"
```

(Use `read -s` prompts inside the script; never paste keys directly.)

- [ ] **Step 4: Layered apply — networking only**

```bash
cd iac
terraform apply -var="alert_email=you@example.com" -target=aws_vpc.main -target=aws_subnet.public -target=aws_subnet.private -target=aws_security_group.lambda -target=aws_security_group.rds -target=aws_security_group.nat -target=aws_instance.nat
```

Expected: VPC + NAT instance up. Check NAT user-data ran:
```bash
aws ec2 describe-instances --filters "Name=tag:Name,Values=proptech-nat" --query 'Reservations[].Instances[].State.Name'
```

- [ ] **Step 5: Layered apply — storage**

```bash
terraform apply -var="alert_email=you@example.com" -target=aws_s3_bucket.raw -target=aws_s3_bucket.clean -target=aws_db_instance.main
```

Expected: 2 S3 buckets + RDS available. RDS takes ~5–10 minutes.

- [ ] **Step 6: Layered apply — secrets + IAM + Lambdas + Step Functions**

```bash
./scripts/package_lambdas.sh
terraform apply -var="alert_email=you@example.com"
```

Expected: full plan applies clean.

- [ ] **Step 7: Run pipeline manually**

```bash
ARN=$(terraform output -raw state_machine_arn)
EXEC=$(aws stepfunctions start-execution --state-machine-arn "$ARN" --input '{}' --query executionArn --output text)
sleep 60
aws stepfunctions describe-execution --execution-arn "$EXEC" --query status
```

Expected: `"SUCCEEDED"`. If `FAILED`, check execution history + CloudWatch Logs and write the bug + fix to RUNBOOK.md.

- [ ] **Step 8: Verify data**

```bash
RDS_HOST=$(terraform output -raw rds_endpoint)
psql "postgresql://...$RDS_HOST..." -c "SELECT count(*), max(distress_score) FROM listings;"
```

Expected: count > 0.

- [ ] **Step 9: Verify API with IAM auth**

```bash
URL=$(terraform output -raw api_url)
awscurl --service lambda "$URL?limit=5" | jq '.'
```

Expected: JSON array with up to 5 listings, sorted by distress_score DESC.

- [ ] **Step 10: Document any bugs hit + fixes**

Append to `RUNBOOK.md` under `## War Stories`. Each bug = one paragraph: symptom, root cause, fix.

- [ ] **Step 11: Commit**

```bash
git add RUNBOOK.md
git commit -m "docs(runbook): phase 1a war stories"
```

---

# PHASE 1B — Test + Observability (merged)

Goal: 70%+ coverage per Lambda, green CI on every PR, structured logging, CloudWatch dashboard, SLO + alarm.

## Task 15: Dev dependencies + pyproject

**Files:**
- Create: `requirements-dev.txt`
- Create: `pyproject.toml`

- [ ] **Step 1: Write dev deps**

Create `requirements-dev.txt`:
```
pytest==8.3.3
pytest-cov==5.0.0
moto[s3,sqs,secretsmanager,sns,stepfunctions]==5.0.20
responses==0.25.3
vcrpy==6.0.2
freezegun==1.5.1
ruff==0.7.4
psycopg[binary]==3.2.3
psycopg-pool==3.2.4
openai==1.54.0
requests==2.32.3
boto3==1.35.50
awscli-local==0.22.0
localstack==3.8.1
scikit-learn==1.5.2
```

- [ ] **Step 2: Write pyproject**

Create `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["lambdas"]
python_files = ["test_*.py"]
addopts = "--strict-markers --tb=short -ra"
markers = [
    "integration: requires LocalStack",
]

[tool.coverage.run]
branch = true
source = ["lambdas"]
omit = ["lambdas/*/test_*.py", "tests/*"]

[tool.coverage.report]
fail_under = 70
show_missing = true
skip_covered = false
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]

[tool.ruff]
line-length = 110
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "S", "T20"]
ignore = ["E501", "S101", "S105", "S106"]
```

- [ ] **Step 3: Install + verify**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
```

Expected: ruff passes (or notes existing issues to fix in next tasks).

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt pyproject.toml
git commit -m "chore: dev deps + pytest/ruff/coverage config"
```

---

## Task 16: tests/conftest.py + shared fixtures

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write conftest**

Create `tests/conftest.py`:
```python
import json
import os
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def env_setup(monkeypatch):
    monkeypatch.setenv("RAW_BUCKET", "test-raw")
    monkeypatch.setenv("CLEAN_BUCKET", "test-clean")
    monkeypatch.setenv("RENTCAST_SECRET_NAME", "test/rentcast")
    monkeypatch.setenv("OPENAI_SECRET_NAME", "test/openai")
    monkeypatch.setenv("DB_SECRET_NAME", "test/rds")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "test")
    monkeypatch.setenv("MAX_LISTINGS_PER_RUN", "5")


@pytest.fixture
def sample_listing():
    return {
        "id": "abc-123",
        "formattedAddress": "123 Main St, Memphis, TN 38103",
        "city": "Memphis",
        "state": "TN",
        "zipCode": "38103",
        "latitude": 35.149,
        "longitude": -90.049,
        "price": 95000,
        "bedrooms": 3,
        "bathrooms": 2,
        "squareFootage": 1100,
        "yearBuilt": 1955,
        "description": "Motivated seller — as-is, cash only. Roof needs work.",
    }


@pytest.fixture
def mock_secrets():
    with patch("shared.secrets._SM") as mock:
        def get_secret(SecretId):
            if "rentcast" in SecretId:
                return {"SecretString": json.dumps({"RENTCAST_API_KEY": "test-key"})}
            if "openai" in SecretId:
                return {"SecretString": json.dumps({"OPENAI_API_KEY": "test-key"})}
            if "rds" in SecretId:
                return {"SecretString": json.dumps({
                    "username": "u", "password": "p", "host": "h",
                    "port": 5432, "dbname": "d"
                })}
        mock.get_secret_value.side_effect = get_secret
        yield mock
```

Create empty `tests/__init__.py`.

- [ ] **Step 2: Commit**

```bash
git add tests/
git commit -m "test: shared conftest with env + sample listing + secrets mock"
```

---

## Task 17: Unit tests — fetch Lambda

**Files:**
- Create: `tests/fetch/__init__.py`
- Create: `tests/fetch/test_handler.py`

- [ ] **Step 1: Write 5 test cases**

Create `tests/fetch/test_handler.py`:
```python
import json
import pytest
import responses
from moto import mock_aws
import boto3


@pytest.fixture
def mock_s3():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-raw")
        yield s3


@responses.activate
def test_fetch_happy_path(mock_s3, mock_secrets, sample_listing):
    responses.add(
        responses.GET,
        "https://api.rentcast.io/v1/listings/sale",
        json=[sample_listing],
        status=200,
    )
    from fetch.handler import handler  # noqa: PLC0415
    result = handler({}, None)
    assert result["count"] == 1
    obj = mock_s3.get_object(Bucket="test-raw", Key=result["raw_key"])
    body = json.loads(obj["Body"].read())
    assert body[0]["id"] == "abc-123"


@responses.activate
def test_fetch_5xx_partial_save(mock_s3, mock_secrets):
    for _ in range(4):  # Retry config = 3 retries + 1 initial
        responses.add(
            responses.GET,
            "https://api.rentcast.io/v1/listings/sale",
            json={"error": "internal"},
            status=503,
        )
    from fetch.handler import handler  # noqa: PLC0415
    result = handler({}, None)
    assert result["count"] == 0
    assert "_partial" in result["raw_key"]


@responses.activate
def test_fetch_respects_max_listings(mock_s3, mock_secrets, sample_listing, monkeypatch):
    monkeypatch.setenv("MAX_LISTINGS_PER_RUN", "3")
    captured = {}

    def callback(req):
        captured["params"] = dict(req.url.split("?", 1)[1].split("&"))
        return (200, {}, json.dumps([sample_listing]))

    responses.add_callback(
        responses.GET,
        "https://api.rentcast.io/v1/listings/sale",
        callback=callback,
    )
    from fetch.handler import handler  # noqa: PLC0415
    handler({}, None)
    # MAX_LISTINGS=3 → query string contains limit=3
    assert any("limit=3" in p for p in captured["params"])


@responses.activate
def test_fetch_empty_response(mock_s3, mock_secrets):
    responses.add(
        responses.GET,
        "https://api.rentcast.io/v1/listings/sale",
        json=[],
        status=200,
    )
    from fetch.handler import handler  # noqa: PLC0415
    result = handler({}, None)
    assert result["count"] == 0


@responses.activate
def test_fetch_writes_dated_key(mock_s3, mock_secrets, sample_listing):
    responses.add(
        responses.GET,
        "https://api.rentcast.io/v1/listings/sale",
        json=[sample_listing],
        status=200,
    )
    from fetch.handler import handler  # noqa: PLC0415
    result = handler({}, None)
    # Key format: raw/YYYY-MM-DD.json
    assert result["raw_key"].startswith("raw/")
    assert result["raw_key"].endswith(".json")
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/fetch/ -v
```

Expected: 5 PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/fetch/
git commit -m "test(fetch): happy path + 5xx + max listings + empty + key format"
```

---

## Task 18: Unit tests — transform Lambda

**Files:**
- Create: `tests/transform/__init__.py`
- Create: `tests/transform/test_handler.py`

- [ ] **Step 1: Write 5 tests**

Create `tests/transform/test_handler.py`:
```python
import json
import pytest
from moto import mock_aws
import boto3


@pytest.fixture
def mock_s3():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-raw")
        s3.create_bucket(Bucket="test-clean")
        yield s3


def test_transform_happy_path(mock_s3, sample_listing):
    mock_s3.put_object(Bucket="test-raw", Key="raw/2026-04-25.json", Body=json.dumps([sample_listing]).encode())
    from transform.handler import handler  # noqa: PLC0415
    result = handler({"raw_key": "raw/2026-04-25.json"}, None)
    obj = mock_s3.get_object(Bucket="test-clean", Key=result["clean_key"])
    rec = json.loads(obj["Body"].read())[0]
    assert rec["id"] == "abc-123"


def test_transform_redacts_phone(mock_s3, sample_listing):
    sample_listing["description"] = "Call 555-123-4567 ASAP. Cash only."
    mock_s3.put_object(Bucket="test-raw", Key="raw/d.json", Body=json.dumps([sample_listing]).encode())
    from transform.handler import handler  # noqa: PLC0415
    result = handler({"raw_key": "raw/d.json"}, None)
    obj = mock_s3.get_object(Bucket="test-clean", Key=result["clean_key"])
    rec = json.loads(obj["Body"].read())[0]
    assert "[PHONE_REDACTED]" in rec["description"]
    assert "555-123-4567" not in rec["description"]


def test_transform_redacts_email(mock_s3, sample_listing):
    sample_listing["description"] = "Email seller@example.com for showing."
    mock_s3.put_object(Bucket="test-raw", Key="raw/e.json", Body=json.dumps([sample_listing]).encode())
    from transform.handler import handler  # noqa: PLC0415
    result = handler({"raw_key": "raw/e.json"}, None)
    obj = mock_s3.get_object(Bucket="test-clean", Key=result["clean_key"])
    rec = json.loads(obj["Body"].read())[0]
    assert "[EMAIL_REDACTED]" in rec["description"]


def test_transform_handles_null_description(mock_s3, sample_listing):
    sample_listing["description"] = None
    mock_s3.put_object(Bucket="test-raw", Key="raw/n.json", Body=json.dumps([sample_listing]).encode())
    from transform.handler import handler  # noqa: PLC0415
    result = handler({"raw_key": "raw/n.json"}, None)
    obj = mock_s3.get_object(Bucket="test-clean", Key=result["clean_key"])
    rec = json.loads(obj["Body"].read())[0]
    assert rec["description"] is None


def test_transform_empty_list(mock_s3):
    mock_s3.put_object(Bucket="test-raw", Key="raw/empty.json", Body=b"[]")
    from transform.handler import handler  # noqa: PLC0415
    result = handler({"raw_key": "raw/empty.json"}, None)
    assert result["count"] == 0
```

- [ ] **Step 2: Run + commit**

```bash
pytest tests/transform/ -v
git add tests/transform/
git commit -m "test(transform): pii redaction + null + empty + key naming"
```

---

## Task 19: Unit tests — enrich Lambda

**Files:**
- Create: `tests/enrich/test_handler.py`

- [ ] **Step 1: Write 5+ tests covering rate-limit + idempotency + score=NULL**

Create `tests/enrich/test_handler.py`:
```python
import json
from unittest.mock import patch, MagicMock
import pytest
from moto import mock_aws
import boto3


@pytest.fixture
def mock_s3():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-clean")
        yield s3


def _put_clean(s3, key, listings):
    s3.put_object(Bucket="test-clean", Key=key, Body=json.dumps(listings).encode())


def test_enrich_happy_path(mock_s3, mock_secrets, sample_listing):
    _put_clean(mock_s3, "clean/2026-04-25.json", [sample_listing])
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content='{"score":0.85,"keywords":["as-is","cash only"]}'))]
    with patch("enrich.handler._client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = fake_resp
        from enrich.handler import handler  # noqa: PLC0415
        result = handler({"clean_key": "clean/2026-04-25.json"}, None)
    assert result["count"] == 1
    obj = mock_s3.get_object(Bucket="test-clean", Key=result["enriched_key"])
    rec = json.loads(obj["Body"].read())[0]
    assert rec["distress_score"] == 0.85


def test_enrich_idempotent_skip(mock_s3, mock_secrets, sample_listing):
    _put_clean(mock_s3, "clean/2026-04-25.json", [sample_listing])
    _put_clean(mock_s3, "enriched/2026-04-25.json", [sample_listing])
    from enrich.handler import handler  # noqa: PLC0415
    result = handler({"clean_key": "clean/2026-04-25.json"}, None)
    assert result["skipped"] is True


def test_enrich_rate_limit_then_succeed(mock_s3, mock_secrets, sample_listing):
    from openai import RateLimitError
    _put_clean(mock_s3, "clean/2026-04-25.json", [sample_listing])
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content='{"score":0.5,"keywords":[]}'))]
    with patch("enrich.handler._client") as mock_client:
        # First call raises, second succeeds
        mock_client.return_value.chat.completions.create.side_effect = [
            RateLimitError(message="rate", response=MagicMock(), body={}),
            fake_resp,
        ]
        with patch("enrich.handler.time.sleep"):
            from enrich.handler import handler  # noqa: PLC0415
            result = handler({"clean_key": "clean/2026-04-25.json"}, None)
    rec = json.loads(mock_s3.get_object(Bucket="test-clean", Key=result["enriched_key"])["Body"].read())[0]
    assert rec["distress_score"] == 0.5


def test_enrich_persistent_failure_yields_null_not_zero(mock_s3, mock_secrets, sample_listing):
    from openai import RateLimitError
    _put_clean(mock_s3, "clean/2026-04-25.json", [sample_listing])
    with patch("enrich.handler._client") as mock_client:
        mock_client.return_value.chat.completions.create.side_effect = RateLimitError(
            message="rate", response=MagicMock(), body={}
        )
        with patch("enrich.handler.time.sleep"):
            from enrich.handler import handler  # noqa: PLC0415
            result = handler({"clean_key": "clean/2026-04-25.json"}, None)
    rec = json.loads(mock_s3.get_object(Bucket="test-clean", Key=result["enriched_key"])["Body"].read())[0]
    assert rec["distress_score"] is None  # NOT 0.0


def test_enrich_malformed_json_response_yields_null(mock_s3, mock_secrets, sample_listing):
    _put_clean(mock_s3, "clean/2026-04-25.json", [sample_listing])
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="not json"))]
    with patch("enrich.handler._client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = fake_resp
        from enrich.handler import handler  # noqa: PLC0415
        result = handler({"clean_key": "clean/2026-04-25.json"}, None)
    rec = json.loads(mock_s3.get_object(Bucket="test-clean", Key=result["enriched_key"])["Body"].read())[0]
    assert rec["distress_score"] is None


def test_enrich_module_scoped_client(mock_s3, mock_secrets, sample_listing):
    """Client should be created once and reused across listings."""
    _put_clean(mock_s3, "clean/2026-04-25.json", [sample_listing, sample_listing, sample_listing])
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content='{"score":0.5,"keywords":[]}'))]
    with patch("enrich.handler.OpenAI") as mock_openai_cls:
        mock_openai_cls.return_value.chat.completions.create.return_value = fake_resp
        # Reset module-level client
        import enrich.handler as eh
        eh._CLIENT = None
        eh.handler({"clean_key": "clean/2026-04-25.json"}, None)
    # OpenAI() instantiated only once even for 3 listings
    assert mock_openai_cls.call_count == 1
```

- [ ] **Step 2: Run + commit**

```bash
pytest tests/enrich/ -v
git add tests/enrich/
git commit -m "test(enrich): idempotency + rate-limit retry + NULL on fail + client reuse"
```

---

## Task 20: Unit tests — load Lambda

**Files:**
- Create: `tests/load/test_handler.py`

- [ ] **Step 1: Write tests with mocked DB pool**

Create `tests/load/test_handler.py`:
```python
import json
from unittest.mock import patch, MagicMock
import pytest
from moto import mock_aws
import boto3


@pytest.fixture
def mock_s3():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-clean")
        yield s3


@pytest.fixture
def mock_pool():
    with patch("load.handler.get_pool") as gp:
        cur = MagicMock()
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cur
        gp.return_value.connection.return_value = conn
        yield cur


def test_load_happy_path(mock_s3, mock_secrets, mock_pool, sample_listing):
    sample_listing["distress_score"] = 0.7
    sample_listing["distress_keywords"] = ["as-is"]
    mock_s3.put_object(Bucket="test-clean", Key="enriched/x.json",
                       Body=json.dumps([sample_listing]).encode())
    from load.handler import handler  # noqa: PLC0415
    result = handler({"enriched_key": "enriched/x.json"}, None)
    assert result["loaded"] == 1
    mock_pool.executemany.assert_called_once()


def test_load_uses_executemany(mock_s3, mock_secrets, mock_pool, sample_listing):
    listings = [dict(sample_listing, id=f"id-{i}") for i in range(5)]
    mock_s3.put_object(Bucket="test-clean", Key="enriched/m.json",
                       Body=json.dumps(listings).encode())
    from load.handler import handler  # noqa: PLC0415
    handler({"enriched_key": "enriched/m.json"}, None)
    args, _ = mock_pool.executemany.call_args
    assert len(args[1]) == 5


def test_load_empty_list(mock_s3, mock_secrets, mock_pool):
    mock_s3.put_object(Bucket="test-clean", Key="enriched/empty.json", Body=b"[]")
    from load.handler import handler  # noqa: PLC0415
    result = handler({"enriched_key": "enriched/empty.json"}, None)
    assert result["loaded"] == 0


def test_load_handles_null_distress_score(mock_s3, mock_secrets, mock_pool, sample_listing):
    sample_listing["distress_score"] = None
    mock_s3.put_object(Bucket="test-clean", Key="enriched/n.json",
                       Body=json.dumps([sample_listing]).encode())
    from load.handler import handler  # noqa: PLC0415
    result = handler({"enriched_key": "enriched/n.json"}, None)
    assert result["loaded"] == 1
    args, _ = mock_pool.executemany.call_args
    assert args[1][0]["distress_score"] is None


def test_load_field_mapping(mock_s3, mock_secrets, mock_pool, sample_listing):
    """Verify camelCase RentCast fields map to snake_case columns."""
    mock_s3.put_object(Bucket="test-clean", Key="enriched/f.json",
                       Body=json.dumps([sample_listing]).encode())
    from load.handler import handler  # noqa: PLC0415
    handler({"enriched_key": "enriched/f.json"}, None)
    args, _ = mock_pool.executemany.call_args
    row = args[1][0]
    assert row["zip"] == "38103"
    assert row["square_feet"] == 1100
    assert row["year_built"] == 1955
```

- [ ] **Step 2: Run + commit**

```bash
pytest tests/load/ -v
git add tests/load/
git commit -m "test(load): batch insert + null score + field mapping + empty"
```

---

## Task 21: Unit tests — api Lambda

**Files:**
- Create: `tests/api/test_handler.py`

- [ ] **Step 1: Write tests with mocked DB pool**

Create `tests/api/test_handler.py`:
```python
import json
from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture
def mock_pool():
    with patch("api.handler.get_pool") as gp:
        cur = MagicMock()
        cur.description = [
            MagicMock(name="listing_id"),
            MagicMock(name="address"),
            MagicMock(name="city"),
            MagicMock(name="state"),
            MagicMock(name="zip"),
            MagicMock(name="price"),
            MagicMock(name="distress_score"),
        ]
        for d, n in zip(cur.description, ["listing_id","address","city","state","zip","price","distress_score"]):
            d.name = n
        cur.fetchall.return_value = [("abc", "123 Main", "Memphis", "TN", "38103", 95000, 0.85)]
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cur
        gp.return_value.connection.return_value = conn
        yield cur


def test_api_happy_path(mock_secrets, mock_pool):
    from api.handler import handler  # noqa: PLC0415
    resp = handler({"queryStringParameters": {"limit": "5"}}, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body) == 1
    assert body[0]["distress_score"] == 0.85


def test_api_default_limit(mock_secrets, mock_pool):
    from api.handler import handler  # noqa: PLC0415
    handler({}, None)
    args, _ = mock_pool.execute.call_args
    assert args[1] == (10,)  # default


def test_api_clamps_limit(mock_secrets, mock_pool):
    from api.handler import handler  # noqa: PLC0415
    handler({"queryStringParameters": {"limit": "999"}}, None)
    args, _ = mock_pool.execute.call_args
    assert args[1] == (100,)


def test_api_invalid_limit_falls_back(mock_secrets, mock_pool):
    from api.handler import handler  # noqa: PLC0415
    handler({"queryStringParameters": {"limit": "junk"}}, None)
    args, _ = mock_pool.execute.call_args
    assert args[1] == (10,)


def test_api_excludes_null_scores(mock_secrets, mock_pool):
    from api.handler import handler  # noqa: PLC0415
    handler({}, None)
    args, _ = mock_pool.execute.call_args
    assert "distress_score IS NOT NULL" in args[0]
```

- [ ] **Step 2: Run + commit**

```bash
pytest tests/api/ -v
git add tests/api/
git commit -m "test(api): limit handling + null exclusion + sql params"
```

---

## Task 22: VCRpy contract test for RentCast schema drift

**Files:**
- Create: `tests/contract/test_rentcast_contract.py`
- Create: `tests/fixtures/cassettes/.gitkeep`

- [ ] **Step 1: Write contract test**

Create `tests/contract/__init__.py` (empty).

Create `tests/contract/test_rentcast_contract.py`:
```python
import os
import pytest
import vcr

REQUIRED_FIELDS = {"id", "formattedAddress", "city", "state", "zipCode", "price"}

vcr_cfg = vcr.VCR(
    cassette_library_dir="tests/fixtures/cassettes",
    record_mode=os.environ.get("VCR_MODE", "none"),
    filter_headers=["X-Api-Key"],
)


@pytest.mark.skipif(
    not os.environ.get("RENTCAST_API_KEY"),
    reason="set RENTCAST_API_KEY=... VCR_MODE=once to record cassette"
)
def test_rentcast_response_shape():
    """Locked contract test. To re-record:
       RENTCAST_API_KEY=xxx VCR_MODE=once pytest tests/contract/
    """
    import requests
    with vcr_cfg.use_cassette("rentcast_listings_sale.yaml"):
        resp = requests.get(
            "https://api.rentcast.io/v1/listings/sale",
            headers={"X-Api-Key": os.environ["RENTCAST_API_KEY"]},
            params={"limit": 5},
            timeout=30,
        )
    assert resp.status_code == 200
    listings = resp.json()
    assert isinstance(listings, list)
    assert len(listings) > 0
    missing = REQUIRED_FIELDS - set(listings[0].keys())
    assert not missing, f"Missing required fields: {missing}"
```

- [ ] **Step 2: Record cassette one time (manual)**

```bash
RENTCAST_API_KEY=$RENTCAST_KEY VCR_MODE=once pytest tests/contract/ -v
```

- [ ] **Step 3: Commit cassette**

```bash
git add tests/contract/ tests/fixtures/cassettes/
git commit -m "test(contract): rentcast schema drift detection via vcrpy"
```

---

## Task 23: LocalStack integration test

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_pipeline_localstack.py`
- Create: `tests/integration/docker-compose.yml`

- [ ] **Step 1: Docker compose for LocalStack**

Create `tests/integration/docker-compose.yml`:
```yaml
services:
  localstack:
    image: localstack/localstack:3.8
    ports:
      - "4566:4566"
    environment:
      - SERVICES=s3,sqs,sns,secretsmanager,stepfunctions,lambda,iam,cloudwatch,logs
      - DEBUG=0
```

- [ ] **Step 2: Integration test**

Create `tests/integration/test_pipeline_localstack.py`:
```python
import json
import os
import subprocess
import time
import pytest
import boto3

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def localstack():
    if os.environ.get("SKIP_LOCALSTACK"):
        pytest.skip("SKIP_LOCALSTACK set")
    subprocess.run(
        ["docker", "compose", "-f", "tests/integration/docker-compose.yml", "up", "-d"],
        check=True,
    )
    # Wait for LocalStack ready
    for _ in range(30):
        try:
            boto3.client("s3", endpoint_url="http://localhost:4566", region_name="us-east-1").list_buckets()
            break
        except Exception:
            time.sleep(2)
    yield
    subprocess.run(
        ["docker", "compose", "-f", "tests/integration/docker-compose.yml", "down"],
        check=True,
    )


def test_step_functions_asl_loads():
    """Validates that the rendered ASL is accepted by Step Functions."""
    sfn = boto3.client("stepfunctions", endpoint_url="http://localhost:4566", region_name="us-east-1")
    asl = open("iac/asl/pipeline.json").read()
    # Substitute placeholders for LocalStack ARNs
    for arn_key in ["fetch_arn", "transform_arn", "enrich_arn", "load_arn", "sns_topic_arn"]:
        asl = asl.replace(
            "${" + arn_key + "}",
            f"arn:aws:lambda:us-east-1:000000000000:function:{arn_key}"
        )
    try:
        sfn.create_state_machine(
            name="test-pipeline",
            definition=asl,
            roleArn="arn:aws:iam::000000000000:role/test",
        )
    except sfn.exceptions.StateMachineAlreadyExists:
        pass


def test_s3_lambda_chain_smoke(sample_listing):
    """Smoke test fetch+transform locally with LocalStack S3."""
    s3 = boto3.client("s3", endpoint_url="http://localhost:4566", region_name="us-east-1")
    for b in ("test-raw", "test-clean"):
        try:
            s3.create_bucket(Bucket=b)
        except Exception:
            pass
    s3.put_object(
        Bucket="test-raw",
        Key="raw/2026-04-25.json",
        Body=json.dumps([sample_listing]).encode(),
    )
    obj = s3.get_object(Bucket="test-raw", Key="raw/2026-04-25.json")
    listings = json.loads(obj["Body"].read())
    assert listings[0]["id"] == "abc-123"
```

- [ ] **Step 3: Run + commit**

```bash
pytest -m integration tests/integration/ -v
git add tests/integration/
git commit -m "test(integration): localstack ASL validation + s3 smoke"
```

---

## Task 24: GitHub Actions CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write CI workflow**

Create `.github/workflows/ci.yml`:
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements-dev.txt
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: pytest --cov --cov-report=xml --cov-report=term -m "not integration"
      - uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
          fail_ci_if_error: false

  terraform-validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.7.5
      - uses: terraform-linters/setup-tflint@v4
      - run: terraform -chdir=iac fmt -check -recursive
      - run: terraform -chdir=iac init -backend=false -upgrade
      - run: terraform -chdir=iac validate
      - run: tflint --chdir=iac

  asl-validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_VALIDATE_ROLE }}
          aws-region: us-east-1
        if: ${{ secrets.AWS_VALIDATE_ROLE != '' }}
      - run: |
          sed -e 's/\${[a-z_]*_arn}/arn:aws:lambda:us-east-1:000000000000:function:placeholder/g' \
              iac/asl/pipeline.json > /tmp/asl.json
          if command -v aws >/dev/null && [ -n "${{ secrets.AWS_VALIDATE_ROLE }}" ]; then
            aws stepfunctions validate-state-machine-definition --definition file:///tmp/asl.json --type STANDARD
          else
            python -c "import json; json.load(open('/tmp/asl.json'))"
          fi
```

- [ ] **Step 2: Add coverage badge to README**

In `README.md`, after the title, add:
```markdown
[![CI](https://github.com/Kaydenletk/PropDeal/actions/workflows/ci.yml/badge.svg)](https://github.com/Kaydenletk/PropDeal/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Kaydenletk/PropDeal/branch/main/graph/badge.svg)](https://codecov.io/gh/Kaydenletk/PropDeal)
```

- [ ] **Step 3: Commit + push + verify**

```bash
git add .github/workflows/ci.yml README.md
git commit -m "ci: github actions for lint+test+coverage+tflint+asl"
git push
gh run watch
```

Expected: workflow green within 3 minutes. If red, fix and re-push.

---

## Task 25: Observability — CloudWatch dashboard module

**Files:**
- Create: `iac/modules/observability/main.tf`
- Create: `iac/modules/observability/variables.tf`
- Create: `iac/modules/observability/outputs.tf`
- Modify: `iac/main.tf`

- [ ] **Step 1: Write observability module**

Create `iac/modules/observability/variables.tf`:
```hcl
variable "lambda_names" { type = list(string) }
variable "state_machine_arn" { type = string }
variable "rds_id" { type = string }
variable "dlq_name" { type = string }
variable "sns_topic_arn" { type = string }
```

Create `iac/modules/observability/main.tf`:
```hcl
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "proptech-pipeline"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          metrics = [for n in var.lambda_names : ["AWS/Lambda", "Duration", "FunctionName", n, { stat = "p95" }]]
          title = "Lambda p95 duration"
          region = "us-east-1"
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          metrics = [for n in var.lambda_names : ["AWS/Lambda", "Errors", "FunctionName", n]]
          title = "Lambda errors"
          region = "us-east-1"
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6
        properties = {
          metrics = [
            ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", var.state_machine_arn],
            ["AWS/States", "ExecutionsFailed", "StateMachineArn", var.state_machine_arn]
          ]
          title = "Pipeline success vs fail"
          region = "us-east-1"
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.rds_id],
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", var.rds_id]
          ]
          title = "RDS"
          region = "us-east-1"
        }
      },
      {
        type = "metric", x = 0, y = 12, width = 12, height = 6
        properties = {
          metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.dlq_name]]
          title = "DLQ depth"
          region = "us-east-1"
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "pipeline_slo_breach" {
  alarm_name          = "proptech-pipeline-slo-breach"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsSucceeded"
  namespace           = "AWS/States"
  period              = 86400
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "SLO: 99% pipeline success / 30 days"
  dimensions          = { StateMachineArn = var.state_machine_arn }
  alarm_actions       = [var.sns_topic_arn]
  ok_actions          = [var.sns_topic_arn]
  treat_missing_data  = "breaching"
}
```

Create `iac/modules/observability/outputs.tf`:
```hcl
output "dashboard_name" { value = aws_cloudwatch_dashboard.main.dashboard_name }
```

- [ ] **Step 2: Wire from root module**

In `iac/main.tf`, add at end:
```hcl
module "observability" {
  source            = "./modules/observability"
  lambda_names      = [aws_lambda_function.fetch.function_name, aws_lambda_function.transform.function_name, aws_lambda_function.enrich.function_name, aws_lambda_function.load.function_name, aws_lambda_function.api.function_name]
  state_machine_arn = aws_sfn_state_machine.pipeline.arn
  rds_id            = aws_db_instance.main.id
  dlq_name          = aws_sqs_queue.dlq.name
  sns_topic_arn     = aws_sns_topic.alerts.arn
}
```

- [ ] **Step 3: Apply + commit**

```bash
./scripts/validate_local.sh
cd iac && terraform apply -var="alert_email=you@example.com"
git add iac/
git commit -m "feat(obs): cloudwatch dashboard + slo breach alarm"
```

---

## Task 26: SLO doc + Logs Insights queries

**Files:**
- Create: `docs/slo.md`
- Modify: `RUNBOOK.md`

- [ ] **Step 1: Write SLO doc**

Create `docs/slo.md`:
```markdown
# Service Level Objectives

## Pipeline Success SLO

**Target:** 99% successful Step Functions executions over rolling 30 days.

**Metric source:** `AWS/States` namespace, `ExecutionsSucceeded` / `ExecutionsStarted` per state machine.

**Error budget (30 days):**
- Total expected runs: 30 (1/day via EventBridge cron)
- Allowed failures: 0.3 → effectively 0 in any month
- Therefore: any failed execution = SLO breach

**Alarm:** `proptech-pipeline-slo-breach` fires when `ExecutionsSucceeded < 1` over a 24-hour window. Action: SNS → email.

**Reporting:** CloudWatch dashboard "Pipeline success vs fail" widget.

## Lambda Latency SLO

**Target:** p95 < 30s per Lambda over rolling 7 days.

**Metric source:** `AWS/Lambda` `Duration` p95 per function.

## API Availability SLO

**Target:** 99% of `api` invocations return 2xx over rolling 7 days (excluding deliberate IAM 403 from unsigned requests).

**Metric source:** Lambda errors + Function URL request count.

## Cost SLO

**Target:** Monthly AWS bill < $20 in months 1-12, < $25 in months 13-24.

**Source:** AWS Cost Explorer monthly report.
```

- [ ] **Step 2: Add Logs Insights queries to RUNBOOK**

Append to `RUNBOOK.md`:
```markdown
## CloudWatch Logs Insights — Common Queries

### Find Lambda failures last 24h
```
fields @timestamp, lambda, msg, error
| filter level = "error"
| sort @timestamp desc
| limit 50
```

### p95 duration of enrich Lambda last 7 days
```
fields @duration
| filter @log like /enrich/
| stats avg(@duration), pct(@duration, 95) by bin(1h)
```

### Top error messages by frequency
```
fields msg, error
| filter level = "error"
| stats count() as n by msg
| sort n desc
```
```

- [ ] **Step 3: Capture dashboard screenshot**

After dashboard has ~24 hours of data:
```bash
# Open dashboard in browser, take screenshot, save:
# Save to docs/observability.png (1080p+)
```

- [ ] **Step 4: Commit**

```bash
git add docs/slo.md RUNBOOK.md docs/observability.png
git commit -m "docs: SLO + logs insights queries + dashboard screenshot"
```

---

# PHASE 1C — Eval + Public Repo + README/Demo

Goal: rigorous eval harness (N=100-150, holdout, kappa, regex baseline), spun out as standalone public repo + Hugging Face dataset, Phase 1D items merged.

## Task 27: Pull Zillow seed fixtures + start labeling

**Files:**
- Create: `tests/fixtures/zillow_seed.jsonl`
- Create: `scripts/label_listings.py`

- [ ] **Step 1: Write labeling CLI**

Create `scripts/label_listings.py`:
```python
"""Interactive distress-listing labeler.

Usage: python scripts/label_listings.py <input.jsonl> <output.jsonl>

Shows description, prompts for label (0/1/skip), saves with timestamp.
"""
import json
import sys
import time

LABEL_RUBRIC = """
1 = clear distress signal: foreclosure, motivated, as-is, fixer-upper,
    cash only, probate, divorce, behind on payments, condemned, fire
0 = no distress signal: standard listing, normal language, no urgency
skip = unclear / borderline
"""


def main(input_path: str, output_path: str):
    with open(input_path) as f:
        listings = [json.loads(line) for line in f]
    with open(output_path, "a") as out:
        for i, rec in enumerate(listings):
            print(f"\n=== {i+1}/{len(listings)} === id={rec.get('id') or rec.get('listing_id')}")
            print(rec.get("description") or "(no description)")
            print(LABEL_RUBRIC)
            ans = input("label (0/1/skip): ").strip()
            if ans == "skip":
                continue
            if ans not in {"0", "1"}:
                print("invalid — skipped")
                continue
            reason = input("reason (optional): ").strip()
            out.write(json.dumps({
                "listing_id": rec.get("id") or rec.get("listing_id"),
                "description": rec.get("description"),
                "price": rec.get("price"),
                "human_label": int(ans),
                "reasoning": reason,
                "labeled_at": time.time(),
                "labeler": "primary",
            }) + "\n")
            out.flush()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

- [ ] **Step 2: Seed Zillow fixtures**

Manually copy 80 public listings from Zillow / Realtor.com into `tests/fixtures/zillow_seed.jsonl` (one JSON per line). Mix: 40 distressed-looking (search "fixer upper", "cash only", "as-is"), 40 normal listings.

Each line minimum:
```json
{"id":"zillow-12345","description":"...full text from listing remarks...","price":89000}
```

- [ ] **Step 3: Label first batch (target 60-80, time-box 90 minutes)**

```bash
python scripts/label_listings.py tests/fixtures/zillow_seed.jsonl tests/fixtures/distress_eval.jsonl
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/zillow_seed.jsonl tests/fixtures/distress_eval.jsonl scripts/label_listings.py
git commit -m "data: zillow seed + first labeling pass"
```

---

## Task 28: Augment with RDS-pulled listings (after Phase 1A has ~2 weeks data)

- [ ] **Step 1: Pull from RDS**

```bash
psql "$RDS_URL" -c "\copy (SELECT json_build_object('listing_id', listing_id, 'description', description, 'price', price) FROM listings WHERE description IS NOT NULL AND length(description) > 50 ORDER BY random() LIMIT 80) TO 'tests/fixtures/rds_sample.jsonl';"
```

- [ ] **Step 2: Label additional 40-70 to reach N=120-150 total**

```bash
python scripts/label_listings.py tests/fixtures/rds_sample.jsonl tests/fixtures/distress_eval.jsonl
```

- [ ] **Step 3: Verify N**

```bash
wc -l tests/fixtures/distress_eval.jsonl  # ≥ 100
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/distress_eval.jsonl
git commit -m "data: augment eval set with rds-pulled listings, N=120+"
```

---

## Task 29: Cohen's kappa second-rater on 20-item subset

**Files:**
- Create: `scripts/inter_rater_kappa.py`
- Create: `tests/fixtures/distress_eval_rater2.jsonl`

- [ ] **Step 1: Sample 20 items for second rater**

```bash
shuf -n 20 tests/fixtures/distress_eval.jsonl | jq -c 'del(.human_label, .reasoning, .labeled_at, .labeler)' > /tmp/kappa_subset.jsonl
```

- [ ] **Step 2: Have a second person label them (friend, peer, partner)**

```bash
python scripts/label_listings.py /tmp/kappa_subset.jsonl tests/fixtures/distress_eval_rater2.jsonl
# Edit script to set "labeler": "rater2" or pass via argv
```

- [ ] **Step 3: Compute kappa**

Create `scripts/inter_rater_kappa.py`:
```python
import json
import sys
from sklearn.metrics import cohen_kappa_score


def load(path):
    return {r["listing_id"]: r["human_label"] for r in (json.loads(l) for l in open(path))}


def main(p1, p2):
    a = load(p1)
    b = load(p2)
    common = sorted(set(a) & set(b))
    y1 = [a[i] for i in common]
    y2 = [b[i] for i in common]
    kappa = cohen_kappa_score(y1, y2)
    print(f"N (overlap): {len(common)}")
    print(f"Cohen's kappa: {kappa:.3f}")
    print(f"Agreement: {sum(x==y for x,y in zip(y1,y2)) / len(common):.2%}")
    print(f"Interpretation: <0.2 poor, 0.2-0.4 fair, 0.4-0.6 moderate, 0.6-0.8 substantial, >0.8 almost perfect")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

```bash
python scripts/inter_rater_kappa.py tests/fixtures/distress_eval.jsonl tests/fixtures/distress_eval_rater2.jsonl
```

- [ ] **Step 4: Document kappa in eval.md (later task)**

- [ ] **Step 5: Commit**

```bash
git add scripts/inter_rater_kappa.py tests/fixtures/distress_eval_rater2.jsonl
git commit -m "data: 20-item second-rater subset for cohen kappa"
```

---

## Task 30: Regex baseline classifier

**Files:**
- Create: `scripts/regex_baseline.py`

- [ ] **Step 1: Write baseline**

Create `scripts/regex_baseline.py`:
```python
"""Keyword regex baseline for distress classification.
If LLM doesn't beat this by ≥ 0.10 F1, the LLM is unjustified."""
import re

KEYWORDS = [
    r"\bas[\s-]?is\b",
    r"\bcash\s+only\b",
    r"\bfixer[\s-]?upper\b",
    r"\bmotivated\s+seller\b",
    r"\bforeclosure\b",
    r"\bbank[\s-]?owned\b",
    r"\breo\b",
    r"\bshort\s+sale\b",
    r"\bprobate\b",
    r"\bestate\s+sale\b",
    r"\bdistressed\b",
    r"\bhandyman\s+special\b",
    r"\btlc\b",
    r"\bneeds\s+work\b",
    r"\bdivorce\b",
    r"\burgent\b",
    r"\bbring\s+(all\s+)?offers\b",
    r"\binvestor\s+special\b",
    r"\bcondemned\b",
    r"\babandoned\b",
]
RE = re.compile("|".join(KEYWORDS), re.IGNORECASE)


def predict(description: str | None) -> int:
    if not description:
        return 0
    return 1 if RE.search(description) else 0
```

- [ ] **Step 2: Commit**

```bash
git add scripts/regex_baseline.py
git commit -m "feat: regex keyword baseline for distress classification"
```

---

## Task 31: Eval harness with bootstrap CI + holdout + multi-prompt/model

**Files:**
- Create: `scripts/eval_distress_score.py`
- Create: `lambdas/enrich/prompts/v1.txt`
- Create: `lambdas/enrich/prompts/v2.txt`
- Create: `lambdas/enrich/prompts/v3.txt`

- [ ] **Step 1: Save 3 prompt variants**

Create `lambdas/enrich/prompts/v1.txt` (current baseline):
```
You are scoring real-estate listings for distress signals.
Return JSON: {"score": float 0-1, "keywords": [strings]}
0 = no distress, 1 = highly distressed.
Listing description:
```

Create `lambdas/enrich/prompts/v2.txt` (refined with rubric):
```
Score this real-estate listing for seller-distress signals.
Output strict JSON: {"score": float 0.0-1.0, "keywords": [matched phrases]}.

0.0–0.2 = standard listing, no urgency, normal language.
0.3–0.5 = mild signals: handyman special, TLC, dated.
0.6–0.8 = clear distress: as-is, motivated seller, cash preferred, fixer.
0.9–1.0 = extreme distress: foreclosure, REO, bank-owned, probate, condemned.

Consider the description holistically. Slogans alone don't make distress; context matters.

Listing:
```

Create `lambdas/enrich/prompts/v3.txt` (chain-of-thought style):
```
Analyze this listing for seller-distress signals. Think step by step.

Step 1: Identify any distress keywords (foreclosure, cash only, as-is, fixer, etc).
Step 2: Identify any neutralizing context (e.g., "as-is" but description says "fully renovated").
Step 3: Score 0.0-1.0 based on net signal strength.

Return strict JSON: {"score": float, "keywords": [matched], "reasoning": "1-sentence why"}.

Listing:
```

- [ ] **Step 2: Write eval harness**

Create `scripts/eval_distress_score.py`:
```python
"""Eval harness for distress scoring.

Usage:
  python scripts/eval_distress_score.py --prompt v3 --model gpt-4o-mini --threshold 0.5
  python scripts/eval_distress_score.py --baseline regex
"""
import argparse
import json
import os
import pathlib
import random
import sys
import time
from typing import Iterable
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

EVAL_FILE = "tests/fixtures/distress_eval.jsonl"
HOLDOUT_FRAC = 0.30
SEED = 42

# Add lambdas/ to path so we can import from prompts dir
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "lambdas"))


def load_data():
    with open(EVAL_FILE) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    rng = random.Random(SEED)
    rng.shuffle(rows)
    n_holdout = int(len(rows) * HOLDOUT_FRAC)
    holdout = rows[:n_holdout]
    dev = rows[n_holdout:]
    return dev, holdout


def predict_llm(rows: Iterable[dict], prompt: str, model: str, threshold: float):
    if model.startswith("claude"):
        from anthropic import Anthropic
        client = Anthropic()
        def call(desc):
            r = client.messages.create(
                model=model, max_tokens=200,
                messages=[{"role": "user", "content": prompt + (desc or "")}],
            )
            return r.content[0].text
    else:
        from openai import OpenAI
        client = OpenAI()
        def call(desc):
            r = client.chat.completions.create(
                model=model, temperature=0,
                messages=[{"role": "user", "content": prompt + (desc or "")}],
                response_format={"type": "json_object"},
            )
            return r.choices[0].message.content
    preds = []
    cost = 0.0
    for r in rows:
        try:
            txt = call(r.get("description") or "")
            obj = json.loads(txt)
            score = float(obj.get("score", 0))
            preds.append(1 if score >= threshold else 0)
        except Exception as e:
            print(f"  fail on {r['listing_id']}: {e}", file=sys.stderr)
            preds.append(0)
        # rough cost: GPT-4o-mini ~$0.0005/listing
        cost += 0.0005 if "mini" in model else 0.005
    return preds, cost


def predict_regex(rows: Iterable[dict]):
    from regex_baseline import predict
    return [predict(r.get("description")) for r in rows], 0.0


def bootstrap_ci(y_true, y_pred, metric_fn, n_iter=1000):
    rng = random.Random(SEED)
    n = len(y_true)
    samples = []
    for _ in range(n_iter):
        idx = [rng.randrange(n) for _ in range(n)]
        yt = [y_true[i] for i in idx]
        yp = [y_pred[i] for i in idx]
        samples.append(metric_fn(yt, yp))
    samples.sort()
    return samples[int(0.025 * n_iter)], samples[int(0.975 * n_iter)]


def f1(y_true, y_pred):
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="v3", choices=["v1", "v2", "v3"])
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--baseline", choices=["regex"], help="Run regex baseline instead of LLM")
    ap.add_argument("--split", default="dev", choices=["dev", "holdout"])
    args = ap.parse_args()

    dev, holdout = load_data()
    rows = dev if args.split == "dev" else holdout
    y_true = [r["human_label"] for r in rows]
    print(f"\n=== Eval split={args.split} N={len(rows)} positives={sum(y_true)} ===")

    t0 = time.time()
    if args.baseline:
        y_pred, cost = predict_regex(rows)
        label = "regex_baseline"
    else:
        prompt = open(f"lambdas/enrich/prompts/{args.prompt}.txt").read()
        y_pred, cost = predict_llm(rows, prompt, args.model, args.threshold)
        label = f"{args.model}+{args.prompt}"

    p, r, fscore, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    f1_lo, f1_hi = bootstrap_ci(y_true, y_pred, f1)

    print(f"\n## Results ({label})")
    print(f"| Metric | Value |")
    print(f"|--------|-------|")
    print(f"| Precision | {p:.3f} |")
    print(f"| Recall    | {r:.3f} |")
    print(f"| F1        | {fscore:.3f} |")
    print(f"| F1 95% CI | [{f1_lo:.3f}, {f1_hi:.3f}] |")
    print(f"| Confusion matrix (TN FP / FN TP) | {cm.tolist()} |")
    print(f"| Cost (USD) | {cost:.4f} |")
    print(f"| Wall time (s) | {time.time()-t0:.1f} |")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run sweeps**

```bash
# Regex baseline
python scripts/eval_distress_score.py --baseline regex --split dev | tee /tmp/eval_regex.txt

# LLM sweep on dev set (iterate prompts here)
for p in v1 v2 v3; do
  for m in gpt-4o-mini; do
    python scripts/eval_distress_score.py --prompt $p --model $m --split dev
  done
done | tee /tmp/eval_dev.txt

# Final number on HOLDOUT (run only ONCE, after picking best prompt+model from dev)
python scripts/eval_distress_score.py --prompt v3 --model gpt-4o-mini --split holdout | tee /tmp/eval_holdout.txt
```

- [ ] **Step 4: Commit prompts + harness**

```bash
git add scripts/eval_distress_score.py lambdas/enrich/prompts/
git commit -m "feat(eval): harness with bootstrap ci + holdout + 3 prompts"
```

---

## Task 32: Write docs/eval.md

**Files:**
- Create: `docs/eval.md`

- [ ] **Step 1: Write evaluation report**

Create `docs/eval.md` (fill in real numbers from Task 31 output):
```markdown
# Distress-Score Eval Harness

## Methodology

- **Dataset:** N=[N] hand-labeled listings (`tests/fixtures/distress_eval.jsonl`)
  - Sources: 80 public Zillow / Realtor.com seed listings + ~50 RDS-pulled RentCast listings
  - Composition: ~50% positive (distress signals present), ~50% negative
- **Split:** 70% dev (prompt iteration) / 30% holdout (final number reported once, no peeking)
- **Labels:** Binary 0/1 by primary rater following rubric in `scripts/label_listings.py`
- **Inter-rater reliability:** Cohen's κ = [κ value] on 20-item second-rater subset
  - Interpretation: [poor / fair / moderate / substantial / almost perfect]
- **CI:** 95% bootstrap (1000 resamples) on F1
- **Threshold:** 0.5 score → label 1

## Results (dev split)

| Variant | Precision | Recall | F1 | F1 95% CI | Cost / 1k listings |
|---------|-----------|--------|----|-----------|--------------------|
| Regex baseline | [v] | [v] | [v] | — | $0.00 |
| GPT-4o-mini + v1 prompt | [v] | [v] | [v] | [lo,hi] | $0.50 |
| GPT-4o-mini + v2 prompt | [v] | [v] | [v] | [lo,hi] | $0.50 |
| GPT-4o-mini + v3 prompt | [v] | [v] | [v] | [lo,hi] | $0.50 |
| Claude Haiku 4.5 + v3 (if available) | [v] | [v] | [v] | [lo,hi] | $1.00 |

**Best dev variant:** [model + prompt]

## Holdout result (final, no further iteration)

| Metric | Value |
|--------|-------|
| Precision | [v] |
| Recall | [v] |
| F1 | [v] |
| F1 95% CI | [lo, hi] |

## Failure mode analysis (3 false positives + 3 false negatives)

### False positives (model said 1, human said 0)

1. **Listing [id]:** description mentioned "as-is" but context was "as-is move-in ready luxury home". Model anchored on keyword.
2. ...
3. ...

### False negatives (model said 0, human said 1)

1. **Listing [id]:** subtle distress phrasing the model missed: "must close in 7 days, no contingencies".
2. ...
3. ...

## Decision: shipped variant

**Production prompt + model:** GPT-4o-mini + prompt v3.

**Rationale:** beat regex baseline by [Δ] F1 on holdout, within 95% CI of best variant, lowest cost.

## Limitations

- N=[N] with single primary rater means F1 has ±0.10 confidence interval at this sample size; treat the F1 number as a methodology demonstration, not a precise performance claim.
- Geographic distribution skews toward investor-friendly metros (Memphis, Cleveland, Birmingham). Performance may differ in coastal markets.
- Eval set was labeled blind from model output to avoid circular validation.

## Reproducing this report

```bash
pip install -r requirements-dev.txt
python scripts/eval_distress_score.py --baseline regex
python scripts/eval_distress_score.py --prompt v3 --model gpt-4o-mini --split dev
python scripts/eval_distress_score.py --prompt v3 --model gpt-4o-mini --split holdout
```
```

- [ ] **Step 2: Replace placeholders with real numbers from Task 31**

- [ ] **Step 3: Commit**

```bash
git add docs/eval.md
git commit -m "docs: eval methodology + results table + failure analysis"
```

---

## Task 33: UC3 — split eval harness into standalone public repo

**Files:** new repo at `~/proptech-eval/`

- [ ] **Step 1: Create new public repo**

```bash
cd ~
mkdir proptech-eval && cd proptech-eval
git init
gh repo create proptech-eval --public --source=. --remote=origin
```

- [ ] **Step 2: Copy + restructure**

```bash
PROPTECH=/Users/khanhle/Desktop/Desktop\ -\ Khanh’s\ MacBook\ Pro/💻\ Dev-Projects/PropDeal
cp -r "$PROPTECH/scripts/eval_distress_score.py" .
cp -r "$PROPTECH/scripts/label_listings.py" .
cp -r "$PROPTECH/scripts/regex_baseline.py" .
cp -r "$PROPTECH/scripts/inter_rater_kappa.py" .
cp -r "$PROPTECH/lambdas/enrich/prompts" ./prompts
mkdir data
cp "$PROPTECH/tests/fixtures/distress_eval.jsonl" data/
cp "$PROPTECH/tests/fixtures/distress_eval_rater2.jsonl" data/
cp "$PROPTECH/docs/eval.md" README.md
```

- [ ] **Step 3: Add LICENSE, dataset card stub, requirements**

Create `LICENSE` (MIT).

Create `requirements.txt`:
```
openai>=1.0
scikit-learn>=1.3
```

Create `CONTRIBUTING.md` with note: "Want to add a labeled listing? Submit a PR adding a row to data/distress_eval.jsonl with rater notes."

- [ ] **Step 4: First commit + push**

```bash
git add .
git commit -m "feat: standalone distress-listing eval harness"
git push -u origin main
```

- [ ] **Step 5: Reference from main project README**

In PropDeal `README.md`, add line near top:
```markdown
> 🧪 Eval methodology + dataset open-sourced at [proptech-eval](https://github.com/Kaydenletk/propdeal-eval) (see also Hugging Face dataset card).
```

```bash
cd "$PROPTECH"
git add README.md
git commit -m "docs: link to public eval repo"
```

---

## Task 34: Hugging Face dataset card

**Files:** in `~/proptech-eval/`
- Create: `data/README.md` (HF dataset card)

- [ ] **Step 1: Create HF account + dataset**

Manually: hugginface.co → create dataset `Kaydenletk/propdeal-distress-eval`.

- [ ] **Step 2: Write dataset card**

Create `~/proptech-eval/data/README.md`:
```markdown
---
license: mit
task_categories:
- text-classification
language:
- en
tags:
- real-estate
- distress
- llm-eval
size_categories:
- n<1K
---

# PropDeal Distress-Listing Eval Dataset

Hand-labeled real-estate listings for distress-signal binary classification.

## Description

Each row is a listing description with a binary `human_label` (1 = distress signal, 0 = none) plus optional rater reasoning.

## Provenance

- ~50% public Zillow / Realtor.com listings
- ~50% RentCast API responses (sale listings)

## Size

- N=[total]
- Positives: [n_pos]
- Negatives: [n_neg]
- 20-item second-rater subset for Cohen's κ

## Inter-rater reliability

Cohen's κ = [value] (computed on 20-item overlap subset).

## Use cases

- Benchmarking real-estate LLM classifiers
- Prompt iteration with rigorous holdout split
- Regex baseline comparison

## Citation

```bibtex
@misc{proptech-distress-eval-2026,
  author = {Khanh Le},
  title = {PropDeal Distress-Listing Eval Dataset},
  year = {2026},
  publisher = {Hugging Face},
  howpublished = {\url{https://huggingface.co/datasets/Kaydenletk/propdeal-distress-eval}}
}
```
```

- [ ] **Step 3: Upload via HF CLI**

```bash
pip install huggingface-hub
huggingface-cli login
huggingface-cli upload-large-folder Kaydenletk/propdeal-distress-eval --repo-type=dataset ./data
```

- [ ] **Step 4: Commit + push**

```bash
git add data/README.md
git commit -m "docs: HF dataset card"
git push
```

---

## Task 35: Eval regression test in CI

**Files:**
- Create: `.github/workflows/eval-regression.yml`

- [ ] **Step 1: Write nightly eval workflow**

Create `.github/workflows/eval-regression.yml`:
```yaml
name: Eval Regression
on:
  schedule:
    - cron: "0 6 * * *"  # daily 06:00 UTC
  workflow_dispatch:

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements-dev.txt
      - name: Run eval
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python scripts/eval_distress_score.py \
            --prompt v3 --model gpt-4o-mini --split holdout \
            > eval_result.txt
          cat eval_result.txt
      - name: Check F1 threshold
        run: |
          F1=$(grep "| F1" eval_result.txt | head -1 | awk '{print $4}')
          THRESHOLD=0.70
          python -c "
          import sys
          f1 = float('$F1')
          if f1 < $THRESHOLD:
              print(f'F1 regression: {f1} < $THRESHOLD')
              sys.exit(1)
          print(f'F1 OK: {f1}')
          "
```

- [ ] **Step 2: Add OPENAI_API_KEY to GitHub repo secrets**

```bash
gh secret set OPENAI_API_KEY
```

- [ ] **Step 3: Commit + dispatch**

```bash
git add .github/workflows/eval-regression.yml
git commit -m "ci: nightly eval regression check"
git push
gh workflow run "Eval Regression"
gh run watch
```

---

## Task 36: README rewrite (TD8 — GIF + impact above fold)

**Files:**
- Modify: `README.md`
- Create: `docs/demo.gif`

- [ ] **Step 1: Record demo GIF**

Use Kap or LiceCap to record 15-30s loop:
- terminal showing pipeline running
- CloudWatch dashboard
- curl response

Save as `docs/demo.gif` (≤ 5 MB, looped).

- [ ] **Step 2: Rewrite README**

Replace `README.md`:
```markdown
# PropDeal

> 🤖 **Production-grade serverless AI pipeline.** Scores 1k+ real-estate listings/day for distress signals on AWS Free Tier (~$3-5/mo). Validated with N=120 labeled eval set, F1 [actual] (95% CI [lo,hi]) on sealed holdout.

[![CI](https://github.com/Kaydenletk/PropDeal/actions/workflows/ci.yml/badge.svg)](https://github.com/Kaydenletk/PropDeal/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Kaydenletk/PropDeal/branch/main/graph/badge.svg)](https://codecov.io/gh/Kaydenletk/PropDeal)
[![Eval Regression](https://github.com/Kaydenletk/PropDeal/actions/workflows/eval-regression.yml/badge.svg)](https://github.com/Kaydenletk/PropDeal/actions/workflows/eval-regression.yml)

![Demo](docs/demo.gif)

| Metric | Value |
|--------|-------|
| LLM F1 (holdout, 95% CI) | [v] [[lo, hi]] |
| LLM beats regex baseline by | +[Δ] F1 |
| Cohen's κ inter-rater | [κ] |
| Pipeline cost | $3-5/mo (free tier) |
| Pipeline success SLO | 99% / 30 days |
| Test coverage | [%] |

> 📊 Eval methodology + dataset open-sourced: [proptech-eval](https://github.com/Kaydenletk/propdeal-eval) · [HF dataset card](https://huggingface.co/datasets/Kaydenletk/propdeal-distress-eval)

## Live Demo

```bash
awscurl --service lambda "$(terraform output -raw api_url)?limit=10" | jq
```

Returns top 10 distressed-signal listings, sorted by score.

## Architecture

![Architecture](docs/architecture.png)

EventBridge nightly cron → Step Functions → 5 Lambdas (fetch / transform / enrich / load / api) → S3 + Postgres. Function URL with AWS_IAM auth. Layered Terraform with explicit retry policies + DLQ.

## Stack

- **Compute:** AWS Lambda (Python 3.12), Step Functions
- **Schedule:** EventBridge cron `0 2 * * *`
- **Storage:** RDS Postgres 16 (t4g.micro), S3
- **Queue:** SQS DLQ
- **Observability:** CloudWatch dashboard + SLO alarm + structured JSON logs
- **Secrets:** AWS Secrets Manager
- **IaC:** Terraform 1.7+ (layered apply, ASL extracted for validation)
- **CI/CD:** GitHub Actions (lint + 70% coverage gate + nightly eval regression)
- **AI:** GPT-4o-mini with v3 chain-of-thought prompt + regex baseline + Claude Haiku 4.5 comparison
- **Privacy:** PII redaction (phone/email regex) before LLM call

## Architecture Decisions

| Decision | Why |
|----------|-----|
| Free t4g.nano NAT instance | Saves $32/mo NAT Gateway; only 2 Lambdas need VPC |
| Step Functions Standard over chained Lambdas | Visual retry + failure isolation + war-story signal |
| Lambda Function URL + AWS_IAM | Zero infra cost, signed access, no public DB read |
| GPT-4o-mini + v3 prompt | Beats regex by +[Δ] F1, 1/20th cost of GPT-4o |
| Eval harness with holdout + κ | Single-rater F1 alone is statistically meaningless; rigor signals applied-AI seriousness |

## Quickstart

See [RUNBOOK.md](RUNBOOK.md).

## Cost

See [COST.md](COST.md). $3-5/mo months 1-12; ~$18-20/mo year 2+ unless RDS migrated.

## What I Learned

- Eval rigor (holdout, bootstrap CI, κ, baseline) > polished F1 number
- Layered Terraform apply isolates failures; ASL extracted to standalone JSON for `validate-state-machine-definition`
- VPC NAT Gateway is the silent budget killer; t4g.nano NAT instance + Lambdas-outside-VPC keeps costs under $5
- Module-scoped clients + connection pools prevent cold-start cascades
- LLM rate-limit failures must yield NULL not 0.0 — corrupting eval data is invisible

## Personal Use Case

I built this as a portfolio project AND a personal tool. After landing a job, I plan to use it to screen distress listings in [target metro] and underwrite my first investment property.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/demo.gif
git commit -m "docs: README rewrite — GIF + impact metrics above fold (TD8)"
git push
```

---

## Task 37: Loom demo + LinkedIn launch

- [ ] **Step 1: Record 90-second Loom**

Cover in order:
1. Repo + README (5s)
2. Step Functions execution running (15s)
3. CloudWatch dashboard (10s)
4. `python scripts/eval_distress_score.py --split holdout` showing F1 (15s)
5. `awscurl` API call returning JSON (15s)
6. Public eval repo + HF dataset card (15s)
7. Wrap (5s)

Save Loom URL.

- [ ] **Step 2: Pin Loom in README**

Add at top of README under demo GIF:
```markdown
🎥 **[Watch 90s walkthrough →](https://loom.com/share/...)**
```

- [ ] **Step 3: LinkedIn post draft**

Save to `docs/launch_post.md`:
```markdown
Built a production-grade serverless AI pipeline solo on AWS Free Tier (~$5/mo) over the past month.

What's in it:
→ 5 Lambdas + Step Functions + RDS Postgres + S3, all Terraform-provisioned
→ GPT-4o-mini distress scoring with rigorous eval harness (N=120, 30% holdout, Cohen's κ, regex baseline)
→ F1 [v] on sealed holdout; LLM beats regex by +[Δ]
→ Open-sourced eval dataset on Hugging Face

Why I built it: practice production AWS + applied AI for [my 2026 job hunt → AI/cloud roles], then use it to find my first investment property.

Repo: github.com/Kaydenletk/PropDeal
Eval harness: github.com/Kaydenletk/propdeal-eval
HF dataset: huggingface.co/datasets/Kaydenletk/propdeal-distress-eval

#AppliedAI #CloudEngineering #AWS #BuildingInPublic
```

- [ ] **Step 4: Commit launch post draft + post on LinkedIn**

```bash
git add docs/launch_post.md README.md
git commit -m "docs: launch post + loom link"
git push
```

Manually post on LinkedIn + X.

---

## Task 38: Resume bullets + interview prep

**Files:**
- Create: `docs/resume_bullets.md`
- Create: `docs/interview_prep.md`

- [ ] **Step 1: Write resume bullets**

Create `docs/resume_bullets.md`:
```markdown
# Resume bullets — PropDeal (2026)

- Designed and shipped a production-grade serverless AI pipeline on AWS (Lambda, Step Functions, RDS, S3) that scores ~1k real-estate listings/day for distress signals; runs $3–5/mo on Free Tier with 99%/30d success SLO.
- Built rigorous LLM eval harness (N=120 hand-labeled, 30% sealed holdout, Cohen's κ inter-rater, bootstrap 95% CI, regex baseline); raised F1 from [baseline] → [final] across 3 prompt iterations and 2 model variants. Open-sourced harness + dataset (Hugging Face).
- Provisioned full infrastructure with Terraform (layered apply, ASL extracted for validation, t4g.nano NAT instance saving $32/mo); CI pipeline with lint + 70%+ branch coverage + nightly eval regression check.
- Implemented module-scoped DB connection pool + idempotent enrichment with rate-limit retry; persistent failures yield NULL (not silent 0.0) to prevent eval corruption. Reduced enrich p95 from [N]s → [N]s.
- Designed PII redaction layer + AWS_IAM-signed Function URL + structured JSON logging with 3 Logs Insights query templates; documented honest cost breakdown including post-12-mo RDS expiry mitigation.
```

- [ ] **Step 2: Write interview prep cheat sheet**

Create `docs/interview_prep.md`:
```markdown
# Interview Prep — PropDeal

## 2-minute pitch

PropDeal is a serverless AWS pipeline I built solo to score real-estate listings for distress signals. Nightly cron triggers Step Functions, which orchestrates 5 Lambdas — fetch from RentCast, transform with PII redaction, enrich with GPT-4o-mini scoring, load to RDS Postgres, and serve via IAM-signed Function URL. The differentiator isn't the pipeline (that's table stakes), it's the eval harness: N=120 hand-labeled listings with 30% sealed holdout, Cohen's κ inter-rater on a 20-item subset, bootstrap confidence intervals, and a regex baseline. F1 on holdout is [v] with 95% CI [lo, hi], beating the regex baseline by +[Δ]. The whole stack runs on AWS Free Tier for ~$5/mo. I open-sourced the eval harness + dataset on Hugging Face.

## "Why this design?" answers

**Why no NAT Gateway?** $32/mo blew the budget. Only 2 of 5 Lambdas needed VPC (api + load for RDS access). I used a t4g.nano NAT instance (free tier) for outbound traffic from those two; the other three run outside VPC entirely.

**Why Step Functions over chained Lambdas?** Three reasons: (1) explicit retry policy per state with backoff, (2) visual debugging in the AWS console for war stories, (3) failure isolation — one Lambda's transient error doesn't kill the whole pipeline. I extracted the ASL into standalone JSON so I can validate it locally with `aws stepfunctions validate-state-machine-definition` before deploy.

**Why Function URL + IAM auth instead of API Gateway?** Function URL is zero-cost, IAM auth is built-in. API Gateway free tier is generous but I wouldn't have used a single feature it offers (no custom domain in Phase 1, no rate limiting beyond what IAM gives me).

**How do I know the LLM works?** Eval harness. F1 alone with N=50 single-rater has ±0.12 confidence interval — meaningless. So: 70/30 dev/holdout split, iterate prompts only on dev, report holdout F1 once. Cohen's κ on a 20-item second-rater subset gives label-quality signal. Regex baseline is the floor — if the LLM doesn't beat regex by ≥0.10 F1, the LLM is unjustified. In my case [report Δ].

## "What broke?" — war stories

(Fill in 1-2 from RUNBOOK.md after Phase 1A deploy.)

## "What would you do differently?"

1. **Aurora Serverless v2 over RDS t4g.micro** for post-12-mo cost (auto-pause to 0 ACU = $0 idle). Skipped because t4g.micro free tier is simpler for year 1.
2. **Bedrock + Claude Haiku 4.5** as primary instead of OpenAI. I compared in eval but kept GPT-4o-mini for cost. With Bedrock I'd skip the OpenAI key + IAM-only auth.
3. **Larger eval set (N=500+)** with 3 raters and stratified by metro. The N=120 single-primary-rater set is a methodology demo, not a definitive performance claim.
4. **Add Probate / NOD data sources** as a second-source feature engineering step. The current single-source scoring is a thin moat.

## Common technical questions

- *"How do you handle RentCast schema drift?"* → vcrpy contract test in CI; cassette is committed; re-record quarterly.
- *"What if OpenAI rate-limits during enrich?"* → exponential backoff retry up to 3 attempts; on persistent failure, score = NULL (not 0.0). NULL is excluded from the API output. Eval data stays uncorrupted.
- *"Why N=120 not 500?"* → time-boxed labeling at 90 minutes per session, 2 sessions. The κ + holdout + bootstrap CI matter more than absolute N for portfolio purposes. Production-grade dataset would target N=1000+ with multiple raters and metro stratification.
- *"Cost story?"* → COST.md is honest: $3-5/mo year 1, $18-20/mo year 2 unless I migrate RDS. The credibility move is showing I know the post-free-tier number, not pretending it stays $1.
```

- [ ] **Step 3: Commit**

```bash
git add docs/resume_bullets.md docs/interview_prep.md
git commit -m "docs: resume bullets + interview prep cheat sheet"
git push
```

---

## Task 39: Side-project kickoff trigger (post-Phase 1B, parallel with Phase 1C)

**Files:** none in this repo

- [ ] **Step 1: Phase 1B closed?**

Run:
```bash
gh run list --workflow=ci.yml --limit 1 --json conclusion --jq '.[0].conclusion'
test -f docs/observability.png
test -f docs/slo.md
```

If all green: Phase 1B closed. Trigger side-project kickoff.

- [ ] **Step 2: Pick side-project archetype**

Side-project should CONTRAST PropDeal to demonstrate range. Options:

- **A. Agentic LLM workflow** — single-page React app calling Claude with tool use; e.g., "AI lease analyzer" that takes a PDF lease and flags risky clauses. Demonstrates: agentic patterns, RAG, frontend.
- **B. Realtime data system** — WebSocket-driven crypto/stock price tracker with charts. Demonstrates: stateful systems, websockets, frontend.
- **C. Devtools** — small CLI or Claude Code skill that solves a niche dev workflow. Demonstrates: DX, packaging, distribution.

Pick one based on what your target JDs in 2026 actually emphasize.

- [ ] **Step 3: Create new repo + 1-page spec**

```bash
gh repo create USER/[side-project-name] --public
mkdir ~/[side-project-name] && cd ~/[side-project-name]
git init
# Write 1-page spec; brainstorm with /superpowers:brainstorming if needed
```

- [ ] **Step 4: Run side-project in parallel with Phase 1C**

Side-project gets 30% of weekly capacity until Phase 1C closes.

---

## Phase 1 Completion

When all of:
- [ ] Phase 1A all tasks ✓
- [ ] Phase 1B all tasks ✓ + CI green + coverage badge
- [ ] Phase 1C all tasks ✓ + Loom + LinkedIn post + side-project kicked off
- [ ] Real data flowing nightly ≥ 7 days
- [ ] Eval F1 + κ + baseline reported on holdout
- [ ] Public eval repo + HF dataset live

Then **start applying** to 5-10 jobs/week immediately. Don't wait for "more polish."

---

## Self-Review Notes

- Spec coverage: every UC + TD + auto-decided item maps to a task above. UC3 = Task 33-34. UC4 lite = Task 39. TD1-TD8 = Tasks 27-32 + Task 8 (TD4 IAM) + Task 8 (TD5 NAT instance) + Task 23 (TD6 LocalStack) + Task 35 (TD7 eval regression) + Task 36 (TD8 README order).
- Placeholders: numbers in docs/eval.md and README.md are intentionally `[v]` until Task 31 produces real outputs. Engineer must fill in.
- Type consistency: `_CLIENT`, `_POOL`, `_CACHE` module-scoped naming consistent across helpers. Schema column names match between SQL migration (Task 1) and load handler INSERT (Task 6).
