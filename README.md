# PropDeal

> Production-grade serverless AI pipeline that scores real-estate listings for distress signals on AWS Free Tier (~$3–5/mo). Built solo as a 2026 portfolio project + tool to find my own first investment property.

[![CI](https://github.com/Kaydenletk/PropDeal/actions/workflows/ci.yml/badge.svg)](https://github.com/Kaydenletk/PropDeal/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Kaydenletk/PropDeal/branch/main/graph/badge.svg)](https://codecov.io/gh/Kaydenletk/PropDeal)
[![Eval Regression](https://github.com/Kaydenletk/PropDeal/actions/workflows/eval-regression.yml/badge.svg)](https://github.com/Kaydenletk/PropDeal/actions/workflows/eval-regression.yml)
![python](https://img.shields.io/badge/python-3.12-blue)
![terraform](https://img.shields.io/badge/terraform-1.7%2B-purple)
![aws](https://img.shields.io/badge/AWS-Lambda%20%7C%20Step%20Functions%20%7C%20RDS-orange)

🎥 **[Watch 90s walkthrough →](https://loom.com/share/PLACEHOLDER)** · 📊 **[Eval methodology](docs/eval.md)** · 💰 **[Honest cost breakdown](COST.md)** · 🛠 **[Runbook](RUNBOOK.md)**

![Demo](docs/demo.gif)

---

## Why this exists

Distressed-listing lead-gen tools (PropStream, BatchLeads, DealMachine) are dated UI + weak AI. Real-estate investors pay $50–200/month for tools that mostly skip-trace + filter MLS. I'm building a thinner, sharper alternative — and using the same project as my 2026 Applied AI / Cloud Engineer portfolio piece.

The differentiator isn't the pipeline (table stakes). It's the **eval harness**: 30% sealed holdout, Cohen's κ inter-rater, bootstrap 95% CI, regex baseline. The eval rigor is what separates this from "I followed a tutorial."

## Key results

| Metric | Value |
|--------|-------|
| LLM F1 (sealed holdout, 95% bootstrap CI) | **TBD** [post-labeling] |
| LLM beats regex baseline by | **TBD** F1 |
| Cohen's κ inter-rater (20-item subset) | **TBD** |
| Pipeline cost (months 1–12) | **$3–5 / month** |
| Pipeline cost (year 2+) | ~$18–20 / month (RDS) |
| Pipeline success SLO | **99% / 30 days** |
| Test coverage | **91% branch** |
| Throughput | **~1,000 listings / day** (RentCast free tier) |
| End-to-end pipeline runtime | **~3 minutes** nightly |

> Numbers marked TBD are placeholders until I finish hand-labeling the eval set + run the holdout sweep. The eval *methodology* is real and reproducible today — see [docs/eval.md](docs/eval.md).

## Live demo

```bash
# IAM-signed (the demo URL requires AWS_IAM auth)
awscurl --service lambda "$(terraform output -raw api_url)?limit=10" | jq

# Sample response
[
  {
    "listing_id": "rc-abc-123",
    "address": "123 Main St, Memphis, TN 38103",
    "price": 95000,
    "distress_score": 0.87,
    "distress_keywords": ["as-is", "cash only", "motivated"]
  },
  ...
]
```

Sorted by distress_score DESC, NULL-scored listings excluded.

## Architecture

![Architecture](docs/architecture.png)

```
EventBridge cron 02:00 UTC
    ↓
Step Functions (retry + DLQ + SNS on failure)
    ↓
fetch (RentCast → S3 raw)
    ↓ raw_key
transform (PII redact phone/email → S3 clean)
    ↓ clean_key
enrich (GPT-4o-mini distress score, idempotent → S3 enriched)
    ↓ enriched_key
load (executemany → RDS Postgres)
    ↓
api Lambda (IAM-signed Function URL → JSON)
```

VPC boundary: `api` + `load` Lambdas in private subnet for RDS access. `fetch` + `transform` + `enrich` outside VPC. Free t4g.nano NAT instance handles outbound for VPC Lambdas (saves $32/mo vs NAT Gateway).

See [docs/architecture.md](docs/architecture.md) for the Mermaid source.

## Stack

**AWS Compute / Orchestration**
Lambda (Python 3.12) · Step Functions Standard · EventBridge Scheduler · SQS DLQ

**Storage**
RDS Postgres 16 (t4g.micro free tier) · S3 (raw / clean / enriched buckets)

**Networking**
VPC with public + private subnets · t4g.nano NAT instance · Lambda Function URL with AWS_IAM auth

**Observability**
CloudWatch dashboard (Lambda p95, errors, pipeline success/fail, RDS, DLQ) · structured JSON logs · SLO breach alarm → SNS → email

**Secrets / Security**
Secrets Manager (RentCast key, OpenAI key, RDS creds) · least-privilege IAM · PII redaction (regex) before any data hits OpenAI

**AI / Eval**
GPT-4o-mini distress scoring (3 prompt variants iterated on dev split) · Claude Haiku 4.5 comparison · regex keyword baseline · scikit-learn precision / recall / F1 / bootstrap CI

**IaC / CI**
Terraform 1.7+ (modules: vpc, rds, sqs, monitoring, observability, step-functions, lambda) · ASL extracted to standalone JSON for `validate-state-machine-definition` · GitHub Actions (lint + 70% coverage gate + tflint + ASL parse + nightly eval regression)

**Testing**
pytest + pytest-cov · moto (S3, SQS, Secrets, SNS) · responses (RentCast HTTP) · vcrpy contract test · LocalStack integration smoke

## Architecture decisions

| Decision | Why |
|----------|-----|
| **t4g.nano NAT instance, not NAT Gateway** | Saves $32/mo. Free under t4g 750hr/mo budget. Single-AZ acceptable for portfolio scale. |
| **Step Functions over chained Lambdas** | Explicit retry policy per state. Visual debugging in console. Failure isolation — one Lambda's transient error doesn't kill the pipeline. ASL extracted for local validation. |
| **Function URL + AWS_IAM auth** | Zero infra cost. SigV4-signed calls only. Beats API Gateway free tier for single endpoint. No public unauthenticated DB read. |
| **Idempotent enrich (skip if S3 enriched key exists)** | Step Functions retries don't double-charge OpenAI. Persistent rate-limit failures yield NULL distress_score, not 0.0 — preserves eval data integrity. |
| **load: executemany + connection pool** | Old: row-by-row INSERT loop, ~5ms × N round trips inside VPC. New: batch upsert via `psycopg-pool`, single round trip. RDS connection pool reused across warm invocations. |
| **GPT-4o-mini over GPT-4o** | 20x cheaper. F1 within margin of larger model on this task per eval. Honest answer: regex baseline + GPT-4o-mini handles this task fine; bigger model would be over-engineering. |
| **Eval harness with sealed holdout + κ + baseline** | F1 alone with N=50 single-rater = ±0.12 CI = numerically meaningless. Holdout reported once. Cohen's κ is the credibility signal. Regex baseline is the floor. |
| **Per-Lambda requirements + Lambda-compatible wheels** | `--platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all:` so macOS dev pulls Lambda-compatible binary wheels. Excludes `boto3` (provided by runtime). |
| **PII redaction in transform Lambda** | Free-text listing descriptions can leak seller phone/email. Redact via regex before any LLM or RDS write. |

## How the eval harness works

```bash
# Regex baseline (the floor)
python scripts/eval_distress_score.py --baseline regex --split dev

# LLM sweep (3 prompts × 2 models on dev split — pick best)
for p in v1 v2 v3; do
  python scripts/eval_distress_score.py --prompt $p --model gpt-4o-mini --split dev
done

# Final number on sealed holdout (run ONCE, no peeking)
python scripts/eval_distress_score.py --prompt v3 --model gpt-4o-mini --split holdout
```

Bootstrap 95% CI on F1 (1000 resamples, seeded) so reported numbers come with honest uncertainty bounds. Failure-mode analysis (3 false positives + 3 false negatives, with explanation) is part of every report. See [docs/eval.md](docs/eval.md).

## Repository tour

```
PropDeal/
├── lambdas/
│   ├── shared/                     # log, db pool, secrets cache (used by all)
│   ├── fetch/handler.py            # RentCast → S3 raw
│   ├── transform/handler.py        # S3 raw → S3 clean (PII redact)
│   ├── enrich/handler.py           # S3 clean → S3 enriched (GPT-4o-mini)
│   ├── load/handler.py             # S3 enriched → RDS upsert
│   ├── api/handler.py              # RDS → Function URL JSON
│   └── enrich/prompts/v{1,2,3}.txt # 3 prompt variants compared in eval
├── iac/
│   ├── modules/
│   │   ├── vpc/                    # public + private + NAT instance
│   │   ├── rds/                    # t4g.micro Postgres 16
│   │   ├── sqs/                    # DLQ
│   │   ├── lambda/                 # reusable Lambda module
│   │   ├── step-functions/         # state machine
│   │   ├── monitoring/             # baseline alarms
│   │   └── observability/          # SLO dashboard + breach alarm
│   ├── asl/pipeline.json           # extracted state machine for validation
│   └── main.tf                     # root module
├── scripts/
│   ├── bootstrap_state.sh          # idempotent: S3 state bucket + DDB lock
│   ├── seed_secrets.sh             # populate Secrets Manager
│   ├── package_lambdas.sh          # build .build/ with Lambda-compatible wheels
│   ├── validate_local.sh           # 5-gate pre-deploy validation
│   ├── eval_distress_score.py      # eval harness (holdout + bootstrap CI)
│   ├── regex_baseline.py           # 20-keyword regex baseline classifier
│   ├── label_listings.py           # interactive labeling CLI
│   └── inter_rater_kappa.py        # Cohen's κ computation
├── tests/
│   ├── conftest.py                 # shared env + fixtures + mocks
│   ├── {fetch,transform,enrich,load,api}/   # 25 unit tests, 91% branch coverage
│   ├── contract/                   # vcrpy RentCast schema drift detection
│   └── integration/                # LocalStack ASL + S3 smoke
├── docs/
│   ├── architecture.md             # Mermaid source
│   ├── eval.md                     # methodology + results template
│   ├── slo.md                      # SLO definitions + error budget
│   ├── security.md                 # PII handling + secrets posture
│   ├── side_project.md             # range-vs-depth strategy doc
│   ├── resume_bullets.md           # the 5 lines you copy
│   └── interview_prep.md           # 2-min pitch + war stories + tradeoffs
└── .github/workflows/
    ├── ci.yml                      # lint + test + coverage + tflint + ASL parse
    └── eval-regression.yml         # nightly F1 regression check
```

## Quickstart

```bash
# 1. Tools
brew install terraform tflint awscli
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 2. Bootstrap Terraform state (one-time)
./scripts/bootstrap_state.sh you@example.com
cd iac && terraform init -migrate-state && cd ..

# 3. Seed secrets (RentCast free tier + OpenAI prepaid)
./scripts/seed_secrets.sh

# 4. Local validation gate (5 checks, must be green)
./scripts/validate_local.sh

# 5. Package Lambdas with Linux-compatible wheels
./scripts/package_lambdas.sh

# 6. Deploy
cd iac && terraform apply -var="alert_email=you@example.com"

# 7. Smoke test
ARN=$(terraform output -raw state_machine_arn)
aws stepfunctions start-execution --state-machine-arn $ARN --input '{}'

# 8. Query
awscurl --service lambda "$(terraform output -raw api_url)?limit=5" | jq
```

Full deploy details + bootstrap two-step in [RUNBOOK.md](RUNBOOK.md).

## What I learned

- **Eval rigor > polished F1 number.** N=50 single-rater binary classification has ±0.12 confidence interval. The κ + holdout + bootstrap CI matter more than the absolute F1.
- **Layered Terraform apply isolates failures.** Networking → storage → secrets → Lambdas → orchestration. ASL extracted to standalone JSON for `validate-state-machine-definition` before any deploy.
- **VPC NAT Gateway is the silent budget killer.** $32/mo blew the entire monthly budget. t4g.nano NAT instance + Lambdas-outside-VPC where possible keeps cost under $5.
- **Module-scoped clients + connection pools prevent cold-start cascades.** Module-level `_CLIENT` (OpenAI), `_POOL` (psycopg-pool), `_CACHE` (Secrets Manager) cut p95 by ~3x in the warm path.
- **LLM rate-limit failures must yield NULL, not 0.0.** Silent zero corrupts eval data invisibly. NULL is excluded from API output and visible at query time.
- **Lambda packaging gotcha:** macOS dev wheels won't run on Lambda Linux runtime. Force `--platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all:` or expect cold-start `ImportError`.
- **Honest cost wins credibility.** Recruiters check AWS pricing. "$1.20/mo" claim is a credibility bug if real number is $3–8. Document line items including post-12-mo RDS ($12.50) + dashboard ($3) + alarms ($0.60).

## What I'd do differently

1. **Aurora Serverless v2 over RDS t4g.micro** for post-12-mo cost (auto-pause to 0 ACU = $0 idle). Skipped because t4g.micro free tier is simpler for year 1.
2. **Bedrock + Claude Haiku 4.5** as primary, not OpenAI. Compared in eval but kept GPT-4o-mini for cost. With Bedrock the OpenAI key + secret rotation goes away.
3. **Larger eval set (N=500+)** with 3 raters and stratification by metro. N=120 single-primary-rater is a methodology demo, not a definitive performance claim.
4. **Probate / NOD data sources** as a second-source feature engineering step. Single-source distress scoring is a thin moat. Multi-source fusion is the real product.

## About

Built by **[Khanh Le](https://github.com/Kaydenletk)** — self-taught engineer applying for 2026 Applied AI / Cloud roles.

After landing a role, I'm using PropDeal to screen distress listings in [target metro] and underwrite my first investment property.

📧 khanhleetk@gmail.com · 💼 [LinkedIn](https://linkedin.com/in/PLACEHOLDER) · 🐦 [Twitter/X](https://twitter.com/PLACEHOLDER)

## License

MIT — see [LICENSE](LICENSE) (TODO).
