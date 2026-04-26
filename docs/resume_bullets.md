# Resume bullets — ProptechAI (2026)

- Designed and shipped a production-grade serverless AI pipeline on AWS (Lambda, Step Functions, RDS, S3) that scores ~1k real-estate listings/day for distress signals; runs $3–5/mo on Free Tier with 99%/30d success SLO.
- Built rigorous LLM eval harness (N=120 hand-labeled, 30% sealed holdout, Cohen's κ inter-rater, bootstrap 95% CI, regex baseline); raised F1 from [baseline] → [final] across 3 prompt iterations and 2 model variants. Open-sourced harness + dataset (Hugging Face).
- Provisioned full infrastructure with Terraform (layered apply, ASL extracted for validation, t4g.nano NAT instance saving $32/mo); CI pipeline with lint + 70%+ branch coverage + nightly eval regression check.
- Implemented module-scoped DB connection pool + idempotent enrichment with rate-limit retry; persistent failures yield NULL (not silent 0.0) to prevent eval corruption. Reduced enrich p95 from [N]s → [N]s.
- Designed PII redaction layer + AWS_IAM-signed Function URL + structured JSON logging with 3 Logs Insights query templates; documented honest cost breakdown including post-12-mo RDS expiry mitigation.
