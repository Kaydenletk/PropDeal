# How to Showcase PropDeal for 2026 Job Hunt

> Your project is the artifact. The showcase is the distribution. Treat them as separate problems.

## The 4 audiences

| Audience | What they want | Time budget | Where they look |
|----------|----------------|-------------|------------------|
| **Recruiter (non-technical)** | "Is this person worth a 30-min screen?" | 30 seconds | LinkedIn → repo top → README hero |
| **Hiring manager (eng)** | "Can they ship production code?" | 5 minutes | README → architecture → 3 commits → tests |
| **Interviewer (deep dive)** | "Can they explain tradeoffs?" | 30 minutes in interview | docs/eval.md → docs/interview_prep.md → war stories |
| **Future you / community** | Reference for next project | 1 hour | docs/ + RUNBOOK |

Optimize the README hero for #1. Optimize the docs for #2 and #3.

---

## Channel-by-channel showcase plan

### 1. GitHub repo (the canonical artifact)

**Above the fold** (first viewport on github.com without scrolling):
- Title + 1-line tagline
- 5 badges: CI / coverage / eval regression / python / aws
- Loom link + eval link + cost link
- Animated GIF of pipeline running OR architecture diagram

**Repo-level polish:**
- [ ] Set repo description: "Serverless AI pipeline scoring distress signals on real-estate listings. AWS Free Tier (~$5/mo). Eval-driven LLM iteration with 30% sealed holdout + Cohen's κ + regex baseline."
- [ ] Set homepage URL (when you buy domain)
- [ ] Add topics: `aws`, `serverless`, `terraform`, `llm`, `applied-ai`, `step-functions`, `real-estate`, `eval`, `portfolio`
- [ ] Pin to your GitHub profile (max 6 pinned)

```bash
gh repo edit Kaydenletk/PropDeal \
  --description "Serverless AI pipeline scoring distress signals on real-estate listings. AWS Free Tier (~\$5/mo). Eval-driven LLM iteration." \
  --add-topic aws --add-topic serverless --add-topic terraform --add-topic llm \
  --add-topic applied-ai --add-topic step-functions --add-topic real-estate \
  --add-topic eval --add-topic portfolio
```

### 2. GitHub profile README

If you don't have one: create `Kaydenletk/Kaydenletk` repo with a README. Pin PropDeal at top with 1-line story:

```markdown
## 👋 Hi, I'm Khanh — self-taught engineer applying for 2026 Applied AI / Cloud roles

### 🛠 Currently shipping

**[PropDeal](https://github.com/Kaydenletk/PropDeal)** — Serverless AI pipeline scoring real-estate distress signals on AWS (~$5/mo). Built solo with rigorous LLM eval harness (sealed holdout, Cohen's κ, regex baseline).
- F1 [TBD] · 91% test coverage · 99% pipeline SLO
- Stack: Lambda · Step Functions · RDS · Terraform · GPT-4o-mini

### 📈 Open eval data

**[propdeal-eval](https://github.com/Kaydenletk/propdeal-eval)** — Public eval harness + labeled distress-listing dataset on Hugging Face.

### 📫 Reach me

📧 khanhleetk@gmail.com · 💼 LinkedIn · 🐦 X
```

### 3. LinkedIn

**Headline (top of profile):**
> Applied AI / Cloud Engineer · Building production-grade AI systems on AWS · Open to 2026 roles

**Featured section:** Pin PropDeal repo + 90s Loom + LinkedIn launch post.

**Launch post (write once, post once):**

```text
After a month of nights+weekends I shipped PropDeal — a production-grade serverless AI pipeline that scores real-estate listings for distress signals on AWS Free Tier (~$5/mo).

What's interesting:

→ The differentiator isn't the pipeline (5 Lambdas + Step Functions + RDS is table stakes). It's the eval harness:
  • 30% sealed holdout (no peeking)
  • Cohen's κ inter-rater on 20-item second-rater subset
  • Bootstrap 95% CI on F1 (N=50 single-rater = ±0.12 — meaningless)
  • Regex keyword baseline as the floor — if LLM doesn't beat regex by ≥0.10 F1, the LLM is unjustified

→ Stack tradeoffs I made + why:
  • t4g.nano NAT instance over $32/mo NAT Gateway
  • Function URL + AWS_IAM auth over API Gateway (zero cost)
  • GPT-4o-mini over GPT-4o (20× cheaper, F1 within margin on this task)
  • Idempotent enrich (skip if S3 enriched key exists) so retries don't double-charge OpenAI

→ Why I built it: practice production AWS + applied AI for [target 2026 roles], then use it personally to find my first investment property.

📦 Repo: github.com/Kaydenletk/PropDeal
📊 Eval methodology: github.com/Kaydenletk/PropDeal/blob/main/docs/eval.md
🎥 90s walkthrough: [Loom URL]

Feedback welcome — happy to talk tradeoffs, eval rigor, or AWS cost optimization. Open to Applied AI / Cloud Engineer roles in 2026.

#AppliedAI #CloudEngineering #AWS #LLM #BuildingInPublic
```

**Recurring posts** (one every 1-2 weeks during job hunt):
- "What broke in production this week" (war story format)
- "I compared 3 prompt variants on the same eval set — here's what won and why"
- "Cost story: my AWS bill went from $X to $Y when I did Z"
- Each post links back to repo + invites convo

### 4. X / Twitter

Same launch post compressed to 280 chars + a 5-tweet thread:

```text
1/ Built PropDeal: serverless AI pipeline scoring real-estate distress signals on AWS Free Tier (~$5/mo).

The differentiator isn't the pipeline — it's the eval harness.

🧵 5 things I'd tell my past self:

2/ N=50 single-rater binary F1 has ±0.12 confidence interval.
"F1 0.81" is meaningless without holdout, κ, and bootstrap CI.
Methodology > absolute number.

3/ NAT Gateway = $32/mo. Killed my entire budget.
Solution: t4g.nano NAT instance (free tier) + put as many Lambdas outside VPC as possible.
Result: $5/mo total.

4/ Idempotent enrich = critical for LLM Lambdas.
Step Functions retries WILL fire. Without idempotency, every transient OpenAI 429 doubles your cost.
Pattern: skip if S3 enriched key exists.

5/ Honest cost wins credibility.
"$1/mo" sounds great in a README but recruiters check AWS pricing.
"$3-5/mo months 1-12, $18-20 year 2 unless you migrate RDS" → believable, signals you actually know.

repo: github.com/Kaydenletk/PropDeal
```

### 5. Hacker News (Show HN)

Submit once when README is polished + Loom is live + eval numbers are real (post-Tasks 27-29).

**Title format:** `Show HN: PropDeal – serverless AI distress-listing scorer with rigorous eval harness`

**Top comment from you (immediately after submission):**

```text
Built this as a 2026 Applied AI / Cloud portfolio piece — and as a tool to find my own first investment property after I land a role.

Three things I'd love feedback on:

1. Eval methodology: 30% sealed holdout, Cohen's κ on 20-item subset, bootstrap 95% CI. Is this overkill for N=120, or appropriate? Open to better approaches.

2. Cost: $3-5/mo on AWS Free Tier without sacrificing observability (CloudWatch dashboard, SLO alarm, structured JSON logs). Anything I missed?

3. Architecture: t4g.nano NAT instance to avoid $32/mo NAT Gateway. Trading single-AZ HA for cost. Defensible at portfolio scale, but would I get crucified for this in production?

Code is MIT, eval set + dataset card on Hugging Face: [link]. Happy to answer questions on any tradeoff.
```

HN front page is rare but the audience is exactly your target. One good post = better than 100 LinkedIn posts.

### 6. Reddit

| Subreddit | Pitch angle |
|-----------|-------------|
| r/aws | Cost story — "How I got a serverless ML pipeline to $5/mo on Free Tier" |
| r/MachineLearning | Eval rigor — "Eval harness with sealed holdout + Cohen's κ for a single-rater binary classification task" |
| r/realestateinvesting | Domain — "I built an AI that scores listings for distress signals" (only after deploy works + eval F1 is real) |
| r/Python | Stack — "Building a serverless Lambda pipeline with module-scoped clients + connection pools" |

Don't spam. Pick one. Write a real post with code + numbers + an honest "what would you do differently."

### 7. Cold-outreach to hiring managers

After you've landed 1-2 interviews and have feedback to fold back, cold-DM hiring managers at target companies:

```text
Subject: Applied AI / Cloud engineer — built+evaluated production LLM pipeline

Hi [Name], I'm Khanh — self-taught engineer applying for [Role] at [Company].

I built a production-grade serverless AI pipeline solo over the past month: github.com/Kaydenletk/PropDeal.
- AWS Free Tier (~$5/mo), 99% pipeline SLO, 91% test coverage
- LLM eval harness with sealed holdout, Cohen's κ, regex baseline
- F1 [v] on holdout, beats regex by +[Δ]

I'd love 15 min to walk through the eval methodology + cost tradeoffs. The repo's all open-source if you want to look first.

Open to [Role] in 2026.

— Khanh
github.com/Kaydenletk · linkedin.com/in/...
```

Send 5/week max. Response rate 5–15% from cold DMs is normal.

---

## Visual assets to produce (one-time work)

### Required for above-the-fold scan

1. **Animated GIF of pipeline running** (15-30s loop, ≤ 5 MB)
   - Tool: [Kap](https://getkap.co) or [LiceCap](https://www.cockos.com/licecap/) or `peek` (Linux)
   - Content: terminal showing Step Functions execution → CloudWatch dashboard → curl returning JSON
   - Save: `docs/demo.gif`

2. **Architecture diagram (PNG, 1080p+)**
   - Tool: [Excalidraw](https://excalidraw.com) (looks intentional, not auto-generated)
   - Source: Mermaid in `docs/architecture.md` is the spec; redraw in Excalidraw for production look
   - Save: `docs/architecture.png`

3. **CloudWatch dashboard screenshot** (after deploy + 24hr data)
   - Just `cmd-shift-4` on the dashboard view
   - Save: `docs/observability.png`

### Nice-to-have

4. **Loom 90s walkthrough**
   - Cover order: README → repo → Step Functions execution → dashboard → eval harness output → curl → public eval repo
   - Tool: [Loom](https://loom.com) free tier
   - Add link to top of README

5. **Eval results plot** (after labeling done)
   - Bar chart of F1 across 6 variants (3 prompts × 2 models) + regex baseline
   - Tool: matplotlib quick-and-dirty or Excel screenshot
   - Save: `docs/eval-results.png`, embed in `docs/eval.md`

---

## Job-hunt operating cadence

Once README is polished + project deployed:

**Daily** (30 min)
- Check inbox, reply to recruiter messages
- Apply to 1-2 jobs (tailored cover line, not mass spray)

**Weekly** (~3 hr)
- 5-10 applications
- 1 LinkedIn or X post (pull from war stories / tradeoffs)
- Follow up on prior-week applications

**Bi-weekly**
- Refine resume bullets based on interview feedback
- Update README if any major thing changed
- Track response rate, interview rate, offer rate (spreadsheet)

### Application targeting

Don't apply to "Senior Staff AI Engineer" with 1 portfolio project. Target ranges:

| Role | Years signaled | Salary range (US remote) |
|------|----------------|---------------------------|
| **Junior Applied AI Engineer** | 0-2 | $90-130k base |
| **Mid Applied AI Engineer** | 2-5 | $130-180k base |
| **Junior Cloud Engineer** | 0-2 | $80-120k base |
| **Mid Cloud Engineer** | 2-5 | $120-170k base |

This portfolio + good interview = strong mid-level signal. Don't sell yourself junior. Don't reach for senior.

### Where to apply

- **AI-native companies**: Anthropic, OpenAI, Mistral, Cohere, Hugging Face, Replicate, Together AI, Modal, Banana, RunPod, Vellum, Humanloop, LangChain, Weights & Biases, Galileo, Braintrust
- **Real-estate tech**: HouseCanary, Zillow, Opendoor, Roofstock, Pacaso, Mynd, REimagineHome, BoxCast (real-estate angle = stronger pitch)
- **Cloud-first SaaS**: Vercel, Linear, Railway, Render, Fly.io, Supabase, Neon, Convex
- **YC W26 / S26 batches**: Filter Y Combinator companies for "applied AI" or "data infra"
- **Recruiters who specialize in AI**: Reach out on LinkedIn

### Tools

- **Resume tracker**: [Teal](https://tealhq.com) free
- **JD analyzer**: paste 5 target JDs into Claude/GPT, ask "what keywords are common?"
- **Application tracker**: spreadsheet — company, role, applied date, response, interview stages, offer/reject

---

## Anti-patterns

❌ **Posting half-baked.** README without real F1 numbers + Loom = "yet another tutorial follower." Wait until eval is real.

❌ **Spray-and-pray applications.** 100 generic applications < 10 tailored ones with a custom cover line that mentions one specific thing about the company.

❌ **Multiple landing pages.** One repo, one Loom, one launch post. Not a Notion site, a Vercel landing page, a Substack, AND a Twitter thread. Distribution is the bottleneck — focus.

❌ **"I'm self-taught" apologetics.** Don't lead with it. The artifact speaks. Mention it once in About + only when relevant in interviews.

❌ **Comparing yourself to FAANG candidates.** Different game. You compete on real-world utility + eval rigor + open-source distribution, not LeetCode.

❌ **Polishing forever.** Ship at 80%. Apply. Iterate from interview feedback. The biggest portfolio mistake is "I'll launch when it's perfect."

---

## Success metrics (8-week window after launch)

| Metric | Target |
|--------|--------|
| Repo stars | 50+ (HN/Reddit hits boost this) |
| LinkedIn post impressions | 10k+ on launch post |
| Inbound recruiter messages | 5+ per week after launch |
| Cold-outreach response rate | 10%+ |
| Technical interviews | 5+ in 8 weeks |
| Offers | 1+ by week 12 |

If targets are missed by week 6, diagnose: is the repo not landing, or are you not applying enough? Usually it's the second.

---

## TL;DR

1. **README hero matters most** — 30 seconds decides everything
2. **One launch post per channel, not 5** — distribution is a focused bet
3. **Real numbers > polished prose** — fill in F1/κ/cost as soon as Tasks 27-29 produce them
4. **Apply early, iterate from feedback** — don't wait for perfect
5. **Mid-level positioning** — this portfolio + good interview = strong mid signal, not junior
