# Cost Breakdown

Target: Under $25/month all-in (AWS + OpenAI).

## Monthly Estimate

| Service | Config | $/mo |
|---------|--------|------|
| AWS Lambda | 5 functions, ~3,000 invocations/month | $0.50 |
| AWS S3 | 10GB storage, lifecycle 30d on raw | $0.30 |
| AWS RDS | db.t4g.micro, 20GB gp3, 1-day backup | $13.00 |
| AWS EventBridge Scheduler | 30 triggers/month | $0.00 (free tier) |
| AWS Step Functions | ~90 state transitions/month | $0.05 |
| AWS SQS | DLQ, minimal messages | $0.00 (free tier) |
| AWS CloudWatch Logs | 14-day retention, ~1GB/month | $0.60 |
| AWS CloudWatch Metrics + Alarms | 7 alarms | $0.70 |
| AWS Secrets Manager | 3 secrets | $1.20 |
| AWS X-Ray | Active tracing | $0.10 |
| AWS Data Transfer | Minimal (no cross-AZ) | $0.00 |
| **AWS Subtotal** | | **~$16.45** |
| OpenAI GPT-4o-mini | ~100K tokens/day @ $0.00015/1K input | $3.00 |
| RentCast API | Free tier (50 requests/day) | $0.00 |
| **Total** | | **~$19.45** |

## Cost-Saving Choices

1. **No NAT Gateway** — saves $32/mo. fetch/transform/enrich Lambdas run outside VPC; only load + api touch RDS.
2. **db.t4g.micro** — ARM-based Graviton; 20% cheaper than x86 equivalents for equal workload.
3. **S3 lifecycle on raw bucket** — delete files after 30 days, keep clean for analysis.
4. **Lambda memory 256MB default** — only bump for enrich (512MB) and load (512MB).
5. **CloudWatch Logs retention 14 days** — balances debuggability with cost.
6. **EventBridge Scheduler** instead of always-on Airflow/EC2.
7. **GPT-4o-mini** over GPT-4o — 20x cheaper, sufficient for keyword-style classification.

## Cost Alarms

SNS alarm fires when monthly AWS bill exceeds $50 (set via `scripts/bootstrap.sh`).

## Gotchas Observed

- First apply: RDS snapshot on destroy cost $1 until manually deleted.
- Initial Step Functions runs had retries that spiked invocations — fixed by adding idempotency check in fetch Lambda.
