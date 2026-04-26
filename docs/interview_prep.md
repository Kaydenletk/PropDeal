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
