# Job Hunt Plan — PropDeal as Portfolio (2026)

> Goal: get project recruiter-ready in 4 weeks, start applying week 5. Personal-use features deferred until after job offer.

## Strategy

- **Phase 1 (Week 1–4): Recruiter-scan ready.** Polish what exists. No new domains.
- **Apply jobs from Week 5.** Don't wait for "perfect."
- **Phase 2 (post-offer): Personal-use features.** Buy box, comp engine, deal report — only after stable income.

Story to tell: *"Production-grade serverless AI pipeline. Built it solo. Costs $14/mo. Validated LLM scoring with eval harness. Plan to use it for my own first investment property."*

---

## Phase 1 — Recruiter Polish (4 weeks)

### Week 1: Test Coverage + CI

Goal: prove production discipline. Coverage > 70%.

- [ ] Add `pytest` for each Lambda (`fetch`, `transform`, `enrich`, `load`, `api`)
- [ ] Mock external calls (RentCast, OpenAI, S3, RDS) via `moto` + `responses`
- [ ] Coverage report via `pytest-cov`
- [ ] GitHub Actions workflow: run tests + coverage on PR
- [ ] Coverage badge in README
- [ ] Target: each Lambda has happy-path + 2 edge-case tests

**Deliverable:** green CI badge, coverage badge, `tests/` directory.

### Week 2: Observability Story

Goal: show "I run production."

- [ ] CloudWatch dashboard screenshot → `docs/observability.png`
- [ ] Switch all Lambda logs to structured JSON (one `log()` helper)
- [ ] Add 3 example Logs Insights queries to `RUNBOOK.md`
- [ ] Define 1 SLO: "99% pipeline success / 30 days"
- [ ] Add SLO breach alarm to Terraform
- [ ] Update README "Observability" section with screenshot + SLO

**Deliverable:** observability section in README with real screenshots + SLO.

### Week 3: LLM Eval Harness ⭐ DIFFERENTIATOR

Goal: prove Applied-AI competence. This is the single most important week.

- [ ] Hand-label 50 listings: `{listing_id, distress_yes_no, reasoning}`
- [ ] Store labels as `tests/fixtures/distress_eval.jsonl`
- [ ] Build `scripts/eval_distress_score.py`:
  - run current prompt over 50 labels
  - compute precision, recall, F1
  - print confusion matrix
- [ ] Try 2 prompt variants. Document winner.
- [ ] Try GPT-4o-mini vs Haiku 4.5. Document cost vs accuracy.
- [ ] Write `docs/eval.md` with results table
- [ ] Add "Eval-driven prompt iteration" line to README

**Deliverable:** `docs/eval.md` with real numbers, e.g. *"v2 prompt: precision 0.84, recall 0.78, F1 0.81 on 50-listing eval set. Cost $0.0012/listing."*

This single artifact lifts portfolio from "junior pipeline" to "applied AI engineer."

### Week 4: README + Demo + Launch

Goal: 30-second recruiter scan = win.

- [ ] Rewrite README with sections in this order:
  1. One-line pitch + screenshot/diagram
  2. Live demo (curl example)
  3. Architecture diagram (PNG, not Mermaid)
  4. Key results (eval F1, cost, throughput)
  5. Stack
  6. Architecture decisions (already good)
  7. What I learned
- [ ] Record 90-second Loom: pipeline running + dashboard + eval + curl response
- [ ] Add Loom link to top of README
- [ ] Polish architecture PNG (export Mermaid to clean PNG)
- [ ] LinkedIn post + Twitter/X thread linking repo
- [ ] Pin repo on GitHub profile
- [ ] Update LinkedIn headline + featured section

**Deliverable:** repo passes 30-second recruiter scan.

→ **Start applying Week 5.**

---

## Week 5+ — Apply While Iterating

Don't pause project to job hunt. Run in parallel.

- Apply 5–10 jobs/week
- Tailor resume bullets from project
- Use project as opening line in cover letter
- If interview asks "tell me about a project" → 2-min pitch ready

### Resume bullets (copy these)

- Built serverless AWS pipeline (Lambda, Step Functions, RDS, S3) processing 10k+ real-estate listings nightly with $14/mo total cost
- Implemented LLM eval harness (50-listing labeled set, precision/recall/F1) to iterate on GPT-4o-mini prompts; raised distress-signal F1 from 0.62 → 0.84
- Provisioned full infrastructure with Terraform; CI/CD via GitHub Actions; 75% test coverage
- Designed VPC boundary to avoid NAT Gateway, saving $32/mo while keeping RDS private
- CloudWatch dashboards + SNS alarms; defined and met 99% pipeline-success SLO

### Interview talking points

- **Why no NAT Gateway?** → cost tradeoff, only `load` + `api` in VPC
- **Why Step Functions over chained Lambdas?** → retry semantics, visual debug, failure isolation
- **How do you know the LLM works?** → eval harness, label set, F1 score, prompt iteration
- **What broke in prod?** → write 1–2 real incidents in RUNBOOK
- **What would you do differently?** → list 3 things (e.g. partition strategy, vector cache, agent layer)

---

## Phase 2 — POST-OFFER (defer until stable income)

Only after signed offer. Don't build now.

| Priority | Feature | Personal value | Time |
|----------|---------|----------------|------|
| 1 | Buy box config (price/zip/bed filter) | Cuts noise to 1 metro | 3 days |
| 2 | Comp engine (5 nearest sold comps) | Underwrite each listing | 1 week |
| 3 | Insurance/climate flag (NOAA + FEMA) | Avoid premium-spike traps | 4 days |
| 4 | Deal report PDF (per listing) | Decision document | 1 week |
| 5 | 1 Bedrock Agent (router + 2 tools) | Resume keyword "agentic AI" | 1 week |
| 6 | Cost optimization (batch S3, cache LLM) | $20 → $14/mo story | 3 days |

Target metro for personal use: Memphis / Cleveland / Birmingham / Indianapolis / Kansas City. Pick one.

---

## Anti-Goals (DO NOT BUILD)

- ❌ Multi-persona platform (investor + buyer + seller)
- ❌ 6 specialist agents
- ❌ Frontend / web UI
- ❌ Stripe / billing / SaaS
- ❌ Foreclosure / county-record scraper
- ❌ Custom ML model training
- ❌ Marketplace
- ❌ Landing page proptech.ai

These are distractions. Each costs 2+ weeks and adds zero recruiter signal.

---

## Success Metrics

### Phase 1 (Week 4 end)
- [ ] Repo: 75%+ coverage, green CI, eval doc, polished README, Loom demo
- [ ] LinkedIn updated, repo pinned
- [ ] First 10 applications submitted

### Job Hunt (Week 5–12)
- [ ] 5–10 apps/week
- [ ] 20%+ response rate
- [ ] 3+ technical interviews
- [ ] 1+ offer by Week 16

### Phase 2 (post-offer)
- [ ] Personal tool used to screen 100+ listings
- [ ] 1 property toured / underwritten using tool output

---

## Weekly Checklist Template

Each Sunday:
1. What shipped this week?
2. README updated?
3. README still passes 30-sec scan?
4. How many job apps submitted?
5. Any interview feedback to fold back?

---

## TL;DR

- 4 weeks polish → apply Week 5
- Eval harness (Week 3) = single biggest differentiator
- Story: "I built and *use* it" beats 90% portfolios
- Personal-use features wait until offer
- Don't expand scope. Don't build features for fun. Ship → apply → iterate from interview feedback.
