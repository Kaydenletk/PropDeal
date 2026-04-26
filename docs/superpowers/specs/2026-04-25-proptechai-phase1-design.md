# PropDeal — Phase 1 Recruiter Polish (Design Spec)

**Date:** 2026-04-25
**Owner:** Khanh Le
**Status:** Draft → pending /autoplan review
**Job target:** Applied AI / Cloud Engineer (full-stack AI-cloud generalist)
**Time model:** Full effort when free (no fixed weekly budget)
**Cost ceiling:** AWS Free Tier (~$2/month)

## Goal

Make the existing PropDeal repo recruiter-scan-ready in 4 self-paced phases (1A → 1D). Project must:

1. Pass a 30-second README scan
2. Show production discipline (deployed, tested, observable, eval'd)
3. Differentiate via LLM eval harness (rare in junior portfolios)
4. Stay within AWS Free Tier
5. Tell a coherent story for full-stack AI-cloud roles

## Approach

**Approach 1 — Deploy First, Polish Iteratively.** Reasoning:

- Eval harness needs real data; deploying first lets data accumulate during later phases
- Real-environment bugs surface earlier (IAM, RDS, Lambda timeout)
- Story "deployed Day 1, iterated to production-grade" is stronger than "tested then deployed"
- Phase boundaries are atomic; user can pause/resume between phases

## Current State

- Code scaffold exists: 5 Lambda handlers (~350 LOC), 5 test stubs (~190 LOC), Terraform IaC (~280 LOC), 1 SQL migration
- Not deployed to AWS
- No production data
- Tests are stubs, not real coverage
- No CI workflow
- README/RUNBOOK/COST/architecture docs exist (committed)

## Out of Scope (Anti-Goals)

These are explicitly deferred to Phase 2 (post-offer):

- Multi-persona platform (investor/buyer/seller)
- Multi-agent orchestration (router + 6 specialists)
- Frontend/web UI
- Stripe/billing/SaaS layer
- Foreclosure scraper / county-record ingestion
- Custom ML model training
- Marketplace
- Public landing page proptech.ai
- Buy box, comp engine, insurance flag, deal report (Phase 2)

These distract recruiter signal and burn 2+ weeks each with zero portfolio value at this stage.

## Architecture Reference

Pipeline: EventBridge → Step Functions → fetch (RentCast → S3 raw) → transform (S3 raw → S3 clean) → enrich (GPT-4o-mini distress score) → load (S3 clean → RDS) → api (RDS → Function URL).

VPC boundary: only `load` and `api` Lambdas in VPC for RDS access. `fetch`, `transform`, `enrich` outside VPC to avoid NAT Gateway cost.

See [docs/architecture.md](../../architecture.md).

---

## Phase 1A — Foundation: Deploy + Smoke Test

### Goal
Pipeline executes successfully end-to-end on real AWS within Free Tier. RDS contains real RentCast data. API URL returns valid JSON.

### Components

1. **Bootstrap verification** — confirm `scripts/bootstrap.sh` creates S3 backend bucket + DynamoDB lock table
2. **Secret seeding** — `scripts/seed_secrets.sh` populates Secrets Manager with:
   - RentCast free-tier API key (50 calls/day)
   - OpenAI prepaid key ($5 credit)
   - RDS master password (auto-generated, stored)
3. **Layered Terraform apply** in this order to isolate failures:
   - Layer 1: networking (VPC, subnets, security groups)
   - Layer 2: storage (S3 raw + clean buckets, RDS t4g.micro)
   - Layer 3: secrets + IAM roles
   - Layer 4: Lambda functions
   - Layer 5: Step Functions + EventBridge schedule + SNS topic
4. **First execution** — manual `aws stepfunctions start-execution`
5. **End-to-end verification** — confirm each stage produced output
6. **Bug log** — capture any deploy/runtime issue + fix into `RUNBOOK.md` as war story

### Acceptance Criteria

- [ ] `terraform apply` completes green with no manual fixes mid-run (single-shot apply after layered first runs)
- [ ] At least 1 Step Functions execution status = `SUCCEEDED`
- [ ] `SELECT count(*) FROM listings` returns ≥ 10 rows
- [ ] `curl $API_URL?limit=5` returns valid JSON array
- [ ] CloudWatch Logs contains entries for all 5 Lambdas
- [ ] AWS Cost Explorer projected monthly spend < $5
- [ ] At least 1 documented bug + fix in RUNBOOK.md

### Verify

```bash
cd iac && terraform output state_machine_arn
aws stepfunctions list-executions --state-machine-arn <arn> --max-items 1
psql "$RDS_URL" -c "SELECT count(*), max(distress_score) FROM listings"
curl "$(terraform output -raw api_url)?limit=5" | jq '. | length'
```

### Dependencies
None. Starts immediately.

### Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| RentCast free tier exhausted on first run | Cap fetch to 30 listings/day in Lambda env var |
| RDS connection timeout from VPC Lambda | Verify SG ingress + subnet route table before apply |
| Secrets Manager not in Free Tier | Document the ~$1.20/mo as known cost; only 3 secrets total |
| Cost spike from accidental loop | EventBridge runs cron `0 2 * * *` only; no infinite trigger |
| terraform apply partial failure | Layered apply lets you `terraform destroy -target` specific module |

---

## Phase 1B — Test Discipline: Coverage + CI

### Goal
70%+ coverage on every Lambda. Green CI on every PR. Public coverage badge on README.

### Components

1. **Dev dependencies** — `requirements-dev.txt` with `pytest`, `pytest-cov`, `moto`, `responses`, `ruff`
2. **Test categories per Lambda** — minimum 5 cases each:
   - Happy path: valid input → expected output
   - External failure: 5xx from RentCast, OpenAI rate limit, S3 unavailable
   - Edge case: empty list, malformed JSON, oversized payload
   - Retry/idempotency where applicable
   - Error propagation to DLQ
3. **Mock strategy:**
   - `moto` for S3, SQS, Secrets Manager, SNS
   - `responses` for RentCast HTTP
   - `unittest.mock.patch` for OpenAI client
   - `pg8000` connection mock for RDS unit tests; optional `pytest-postgresql` for integration
4. **Coverage config** in `pyproject.toml`, `--cov-fail-under=70`
5. **GitHub Actions workflow** `.github/workflows/ci.yml`:
   - Triggers: `push`, `pull_request`
   - Steps: checkout, setup Python 3.12, install deps, `ruff check`, `pytest --cov`, upload coverage report
   - Coverage badge via Codecov free tier or shields.io endpoint
6. **README badges** — CI status + coverage percentage

### Acceptance Criteria

- [ ] `pytest --cov=lambdas` reports ≥ 70% per Lambda module
- [ ] CI workflow green on `main` and at least 1 test PR
- [ ] Coverage badge renders on README
- [ ] Each Lambda has ≥ 5 test cases
- [ ] `ruff check .` passes with zero warnings
- [ ] `requirements-dev.txt` committed and documented in CONTRIBUTING note

### Verify

```bash
pytest --cov=lambdas --cov-report=term-missing --cov-fail-under=70
ruff check .
gh workflow view ci.yml
gh pr create --draft --title "ci-test" --body "test PR for CI" && gh pr checks
```

### Dependencies
Independent of 1A code-wise but Phase 1A should be running so integration test layer (optional) can hit live AWS.

### Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| `moto` version mismatch with boto3 | Pin both versions in requirements-dev.txt |
| Flaky tests from real time / random data | Freeze time with `freezegun`, seed random |
| 70% threshold too aggressive for `load` Lambda | Allow per-module thresholds; aim 70% overall, 60% minimum any single module |
| CI burns GitHub Actions free minutes | Use `setup-python` cache + skip lint on doc-only PRs |

---

## Phase 1C — Production Readiness: Observability + Eval Harness

Two sub-phases. Sub-phase 1C.2 is the single most important deliverable in Phase 1.

### Sub-phase 1C.1 — Observability

#### Components

1. **Structured logging** — `lambdas/shared/log.py` helper emitting JSON logs with request_id, lambda_name, duration, error fields
2. **CloudWatch dashboard** in Terraform with widgets:
   - Pipeline success rate (rolling 30 days)
   - Lambda duration p50/p95/p99 per Lambda
   - DLQ message depth
   - RDS CPU + active connections
   - Estimated daily cost (Cost Explorer integration)
3. **SLO doc** `docs/slo.md` — define `99% pipeline success per 30 days`, error budget formula
4. **SLO breach alarm** — CloudWatch metric alarm → existing SNS topic → email
5. **3 Logs Insights queries** in `RUNBOOK.md`:
   - Failed Lambda invocations last 24h
   - p95 duration of `enrich` Lambda last 7 days
   - Top error messages by frequency
6. **Dashboard screenshot** committed as `docs/observability.png`

#### Acceptance Criteria

- [ ] Dashboard contains ≥ 6 working widgets
- [ ] All Lambdas emit structured JSON logs (verified by Logs Insights filter)
- [ ] `docs/slo.md` defines metric, target, alarm config, error budget
- [ ] 3 Logs Insights queries documented and verified runnable
- [ ] Screenshot committed

#### Verify

```bash
aws cloudwatch get-dashboard --dashboard-name proptech-pipeline | jq '.DashboardBody | fromjson | .widgets | length'
aws logs start-query --log-group-name /aws/lambda/proptech-enrich --query-string "..." --start-time ... --end-time ...
test -f docs/observability.png
```

### Sub-phase 1C.2 — Eval Harness ⭐ DIFFERENTIATOR

#### Components

1. **Hand-labeled dataset** — 50 listings sampled from RDS after ≥ 2 weeks of pipeline runs
   - File: `tests/fixtures/distress_eval.jsonl`
   - Schema: `{listing_id, description, price, raw_features, human_label (0|1), reasoning}`
   - Composition: 25 obvious distress + 25 obvious non-distress, plus capture borderline cases encountered during labeling
2. **Eval script** `scripts/eval_distress_score.py`:
   - Loads JSONL fixture
   - Runs configured prompt+model over each listing
   - Computes precision, recall, F1, confusion matrix
   - Prints Markdown table
   - CLI flags: `--prompt {v1,v2,v3}`, `--model {gpt-4o-mini,haiku-4-5}`
3. **Prompt iteration** — at least 3 prompt variants (v1 baseline, v2 refined, v3 best-of-failures)
4. **Model variant** — compare GPT-4o-mini vs Claude Haiku 4.5 on each prompt
5. **Eval write-up** `docs/eval.md`:
   - Methodology (50-item set, labeling rubric, holdout if any)
   - Results table: 3 prompts × 2 models = 6 rows with precision/recall/F1/cost
   - Cost per 1k listings for each variant
   - Failure mode analysis: 3 false positives + 3 false negatives with explanation
   - Decision: which prompt+model is shipped to production and why
6. **Optional CI integration** — nightly eval run, regression alert if F1 drops > 5%

#### Acceptance Criteria

- [ ] 50 labeled listings in `tests/fixtures/distress_eval.jsonl`
- [ ] Eval script runs in < 5 minutes for full sweep
- [ ] Best variant achieves F1 ≥ 0.75
- [ ] `docs/eval.md` contains 6-row results table + 3+3 failure cases
- [ ] Cost per 1k listings documented for shipped variant
- [ ] Shipped prompt/model committed to `lambdas/enrich/prompts/`

#### Verify

```bash
wc -l tests/fixtures/distress_eval.jsonl  # ≥ 50
python scripts/eval_distress_score.py --prompt v3 --model haiku-4-5
grep -E "F1|precision|recall" docs/eval.md
```

### Dependencies (Phase 1C overall)
- Phase 1A must have run ≥ 2 weeks to give a diverse listing pool for labeling
- Phase 1B not strictly required but helpful — eval script benefits from same test infrastructure

### Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| RentCast free tier yields homogeneous listings (hard to find distress) | Augment with public Zillow distress listings via manual entry; document |
| Hand-labeling 50 items takes hours | Time-box to 2 hours; if undecided after 30s on a listing, mark `borderline` and exclude |
| F1 < 0.75 on best variant | Document honestly; the rigor of the eval matters more than score; expand label set if time permits |
| OpenAI prepaid runs out during eval sweeps | Cap sweep cost; total sweep ≈ 50 × 6 variants × $0.0005 = $0.15 |
| Haiku availability on user's account | Fallback to GPT-4o-mini only and document why |

---

## Phase 1D — Recruiter Polish: README + Demo + Launch

### Goal
30-second README scan = recruiter wins. Project ready to apply jobs the next day.

### Components

1. **README rewrite** with structure:
   1. One-line pitch + architecture PNG
   2. Live demo (real curl command + sample output)
   3. Key results (F1, throughput, cost) — real numbers from 1C
   4. Architecture decision table (already strong)
   5. Stack summary
   6. Quickstart
   7. What I learned + war stories from RUNBOOK
2. **Loom video** ≤ 100 seconds:
   - Step Functions execution running
   - CloudWatch dashboard
   - Eval harness output
   - `curl` to API returning JSON
3. **Architecture PNG** rendered cleanly from Mermaid via excalidraw or draw.io, 1080p+
4. **Asset commits** — screenshots (dashboard, eval table), architecture PNG
5. **LinkedIn post + X thread:**
   - Hook line + 3 outcome bullets + repo link
   - Tag relevant communities (#AppliedAI, #CloudEngineering)
6. **Pin repo** on GitHub profile
7. **LinkedIn featured + headline** updated to "Applied AI / Cloud Engineer"
8. **Resume bullets** — 5-line draft saved to `docs/resume_bullets.md`
9. **Interview cheat sheet** — `docs/interview_prep.md` covering:
   - 2-min pitch
   - Why-this-design questions (NAT Gateway, Step Functions vs chained Lambdas, Function URL)
   - "What broke?" (war stories)
   - "What would you do differently?" (3 items)

### Acceptance Criteria

- [ ] README passes 30-sec scan test (non-technical friend can summarize the project after 30s)
- [ ] Loom < 100s, audio audible, screen readable
- [ ] Architecture PNG ≥ 1080p, no pixelation
- [ ] LinkedIn post live with ≥ 50 views in 48h
- [ ] Repo pinned on GitHub profile
- [ ] Resume bullets file present, 5 lines
- [ ] Interview prep file present with 4 sections

### Verify

- Open README anonymously, 30s timer; able to state project purpose + outcome
- Loom share link opens public, plays end-to-end
- `gh repo view` shows pinned status
- LinkedIn post URL returns 200

### Dependencies
1A, 1B, 1C all complete.

---

## Phase Dependency Graph

```
1A Foundation ────────────────┐
   (deploy + start nightly)   │
                              │
        ↓                     ↓ (data accumulates)
   1B Test+CI                 │
   (independent)              │
        │                     │
        ↓                     ↓
        └──→ 1C Observability + Eval ──→ 1D README + Demo
```

- 1A blocks 1C (need ≥ 2 weeks of data for labeling)
- 1B can run in parallel with 1A's data accumulation
- 1C blocks 1D (README needs eval numbers + dashboard screenshot)

## Cost Budget

| Source | Estimate |
|--------|----------|
| AWS compute/storage (Free Tier) | ~$0/month |
| Secrets Manager (3 secrets, not free) | ~$1.20/month |
| OpenAI prepaid (one-time, lasts ~6 months) | $5 once |
| RentCast free tier | $0 |
| **Total Phase 1 cash outlay** | < $10 |
| **Ongoing monthly run rate** | ~$1.20–$2 |

## Success Definition

End of Phase 1D:
- Repo is publicly pinned, README polished, CI green, coverage badge live
- Live AWS deployment running nightly within Free Tier
- Eval harness with real numbers in docs/eval.md
- Loom demo published
- LinkedIn post + repo pin
- Ready to start applying 5–10 jobs/week immediately

## Story for Recruiter

> "Production-grade serverless AI pipeline I built solo. Deployed on AWS Free Tier (~$2/month). 5 Lambdas orchestrated by Step Functions, Postgres backend. Validated the LLM scoring with a 50-listing eval harness — F1 0.81 on shipped prompt. Plan to use it to find my own first investment property."

This positions: Cloud + Applied AI + production discipline + real-world utility. Differentiates from typical "I followed a tutorial" portfolio.

## Open Questions

None at design time. Implementation may surface tactical questions (specific RentCast endpoint, label edge cases) — handle inline during /autoplan-driven execution.

## Next Step

After spec approval → invoke `/autoplan` to run multi-perspective review (CEO / design / eng / DX) on this design before implementation kickoff.

---

# /autoplan Review Report

**Date:** 2026-04-25
**Phases run:** CEO (subagent only), Eng (subagent only)
**Phases skipped:** Design (no UI), DX (no developer-facing API/SDK)
**Codex status:** [codex-unavailable] — websocket error + model version mismatch on `gpt-5.5`. Both phases ran in [subagent-only] degradation mode.

## Cross-Phase Themes (flagged by both reviewers independently)

1. **Eval rigor weak.** N=50 single-rater binary F1 has ±0.12 confidence interval — "F1 ≥ 0.75" is statistically indistinguishable from 0.63 or 0.87. Single-rater, no holdout, no baseline = numerically meaningless as a credibility claim.
2. **Cost claim inflated.** Spec says ~$1.20–2/month; real ongoing minimum is $3–8/month after accounting for: Secrets Manager VPC endpoint ($7), CloudWatch dashboard alarms ($0.60+), Cost Explorer API calls if hourly refresh ($7+), RDS t4g.micro post-12-month ($12.50). Recruiter pitch credibility risk.
3. **Differentiation problem.** Saturated portfolio archetype in 2026 (LLM + Lambda + Terraform + eval is commodified); proposed differentiators (CI, IaC, eval harness) all commodity. Defensibility requires a unique dataset, outcome, or workflow.

## CEO Findings (Claude subagent, codex unavailable)

| # | Severity | Finding | Recommended fix |
|---|----------|---------|-----------------|
| C1 | HIGH | Saturated archetype | Add 6-month closed-loop outcome dataset OR pivot vertical |
| C2 | HIGH | Unstated premises (recruiters don't scan READMEs first; "Applied AI/Cloud" is 2 roles; N=50 weak) | Pick ONE role title; validate with 5 real 2026 JDs; expand label set or reframe as methodology demo |
| C3 | HIGH | 6-month regret: GPT-4o-mini deprecation, RentCast TOS, "distress score" 2023 framing | Provider abstraction layer; reframe as agentic triage |
| C4 | MEDIUM | Frontend dismissed but tiny demo page beats README | Add 30-second working demo gif/page |
| C5 | CRITICAL | 100s of lookalike portfolios in 2026 | Need unique dataset OR measurable real-world outcome |
| C6 | HIGH | README scan order optimized for candidate, not HM | Animated GIF + impact number above the fold |
| C7 | MEDIUM | 4 phases over-engineered; range > depth for junior | Collapse to 2 phases, build a second contrasting project |

## Eng Findings (Claude subagent, codex unavailable)

| # | Severity | Finding |
|---|----------|---------|
| E1 | CRITICAL | Function URL `AuthType=NONE` = public unauthenticated DB read |
| E2 | HIGH | Secrets Manager VPC endpoint required (~$7/mo) — breaks cost claim |
| E3 | HIGH | VPC Lambda + RDS cold start = 6–10s p99 (kills live demo) |
| E4 | HIGH | No idempotency → enrich double-charge on retry |
| E5 | HIGH | RentCast 5xx mid-batch = total failure, no partial save |
| E6 | HIGH | RDS connection pool exhaustion (no pooling) |
| E7 | HIGH | `load` Lambda one-row INSERT loop — use `COPY` or `executemany` |
| E8 | HIGH | OpenAI rate-limit silently zeros score (corrupts eval data) |
| E9 | HIGH | No contract test for RentCast schema drift |
| E10 | HIGH | No integration test (LocalStack) |
| E11 | HIGH | No eval regression test in CI |
| E12 | HIGH | Real cost $3–8/mo not $1.20 |
| E13 | HIGH | Eval N=50, single rater, no holdout, no baseline |
| E14 | HIGH | Terraform state bootstrap chicken-and-egg undocumented |
| E15 | HIGH | Schema drift: sql/migrations/001 vs load/handler inline |
| E16 | MEDIUM | Lambda deps size (don't ship boto3) |
| E17 | HIGH | "Single-shot apply" Phase 1A acceptance is aspirational |
| E18 | HIGH | 1C eval blocked by 1A 2-week data accumulation; can parallelize with Zillow fixtures |
| E19 | MEDIUM | `pg8000` (spec) vs `psycopg` (code) inconsistency |
| E20 | MEDIUM | RDS 12-month free tier expiry not documented |

## Auto-Decided (15 items — mechanical, P1/P3/P5 principles)

These are correctness/credibility fixes with no taste tradeoff. Folded into spec without gate:

1. Update COST.md with honest line items (Secrets Manager $1.20, VPC endpoint $7 if needed, RDS post-12mo $12.50, dashboard alarms ~$0.60). Reframe ongoing as $3–8/mo. **[P1 completeness, P3 pragmatic — credibility]**
2. Add idempotency check in enrich (skip if S3 enriched key exists). **[P1]**
3. Add OpenAI rate-limit explicit retry; on persist failure set `distress_score=NULL`, not 0.0. **[P1 data integrity]**
4. Replace `load` Lambda row-by-row INSERT with `executemany` or `COPY`. **[P3]**
5. Add psycopg connection pool in `api` Lambda module scope. **[P1]**
6. Add explicit Step Functions retry policy per state with `BackoffRate` and limited `MaxAttempts`. **[P1]**
7. Add `vcrpy` contract test for RentCast (record-once, replay). **[P1]**
8. Add `tflint` + `terraform validate` + ASL validate gate to CI before any apply. **[P1]**
9. Resolve schema drift: sql/migrations/001_initial.sql is source of truth; remove inline `MIGRATION_SQL` from `load` handler OR generate it from the .sql file. **[P5 explicit]**
10. Move `OpenAI()` client instantiation outside per-listing loop in enrich. **[P3]**
11. Add `MAX_LISTINGS_PER_RUN` env var, default 30 to respect RentCast free tier. **[P5]**
12. Document Terraform two-step bootstrap (local backend → migrate-state) in RUNBOOK. **[P1]**
13. Document RDS 12-month free-tier expiry + post-expiry $12.50/mo in COST.md. **[P1]**
14. Add PII redaction note (regex strip phone/email before OpenAI call) + one-line `docs/security.md`. **[P1]**
15. Pre-write the "honest F1 + rigor of eval" Phase 1D framing now (not after results). **[P5]**

## Phase 1A Hardening (auto-added sub-step)

**Phase 1A.0 — Local Validation Gate** (insert before deploy):
- `terraform validate` + `tflint` clean
- `aws stepfunctions validate-state-machine-definition` on inline ASL
- LocalStack smoke test of Step Functions execution with mocked Lambda payloads
- Acceptance: all 3 pass before Phase 1A's `terraform apply`

This re-frames "single-shot green apply" as Phase 1A acceptance of the *second* deploy after first inevitable cycle of fixes.

## Phase 1C Decoupling (auto-added)

Start hand-labeling the eval set immediately using public Zillow / Realtor.com listings as fixtures (~50 entries). Swap to RDS-pulled data once Phase 1A has 2 weeks of runs. Pulls the differentiator forward by 2+ weeks; eval can be done in parallel with deploy stabilization.

## Decisions Surfaced for User Approval

See "Final Approval Gate" message that follows.


---

## Final Approval — User Decisions (locked 2026-04-25)

**Status:** APPROVED with overrides

### User Challenges
- ❌ **UC1 REJECTED** — Keep real-estate vertical (personal home-buying goal). No pivot.
- ❌ **UC2 REJECTED** — Frontend stays anti-goal for Phase 1. Defer indefinitely.
- ✅ **UC3 ACCEPTED** — Eval harness will be split into a standalone public repo with a Hugging Face dataset card as a separate Phase 1C.3 deliverable.
- ✅ **UC4 ACCEPTED (lite)** — Collapse to **3 phases**, start a contrasting side-project after Phase 1B completes (parallel track, not blocking Phase 1).

### Taste Decisions (all 8 accepted)
- TD1 ✅ N=100–150 with 30% holdout
- TD2 ✅ Cohen's kappa on 20-item rater subset
- TD3 ✅ Regex baseline comparison required
- TD4 ✅ Function URL = AWS_IAM SigV4 (demo curl uses awscurl or signed snippet)
- TD5 ✅ Skip Secrets Manager VPC endpoint; move `load` to public subnet with egress IGW (saves $7/mo)
- TD6 ✅ LocalStack integration test required, not optional
- TD7 ✅ Eval regression in CI required, not optional
- TD8 ✅ README rewrite — GIF + impact number above the fold

### Phase Restructure (UC4 lite applied)

Original 4 phases → **3 phases** + parallel side-project:

- **Phase 1A** — Foundation (deploy + smoke test + Phase 1A.0 local validation gate)
- **Phase 1B** — Combined Test Discipline + Observability (merged 1B + 1C.1)
- **Phase 1C** — Eval Harness + Public Repo Split + README/Demo (merged 1C.2 + 1C.3 + 1D)
- **Side-project** — Begin contrasting project (e.g., agentic / frontend-heavy) after Phase 1B closes; runs in parallel with Phase 1C

### Auto-Applied Items
All 15 auto-decided items + Phase 1A.0 hardening + Phase 1C decoupling (start labeling Zillow fixtures immediately) + 8 taste decisions are now part of the binding spec.

### Items Pending Implementation Plan
The next step (writing-plans or direct execution) must produce a task list covering:
1. All Phase 1A components + Phase 1A.0 local validation
2. All Phase 1B components (test + CI + observability merged)
3. All Phase 1C components including UC3 public-repo split + HF dataset card
4. All 15 auto-decided technical fixes integrated into the right phase
5. All 8 taste decisions integrated
6. Side-project kickoff trigger after Phase 1B acceptance

