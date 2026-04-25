# PROPTECH AI Cloud Pipeline

> Serverless AWS data pipeline for real estate listings — Terraform provisioned, GitHub Actions CI/CD, CloudWatch monitored, under $20/month.

![Architecture](docs/architecture.png)

## Live Demo

```bash
curl "<API_URL>?limit=10"
```

Returns top 10 distressed-signal listings.

## Stack

- **Compute:** AWS Lambda (Python 3.12), Step Functions
- **Schedule:** EventBridge Scheduler (cron 0 2 * * *)
- **Storage:** RDS Postgres 16 (t4g.micro), S3
- **Queue:** SQS (DLQ)
- **Observability:** CloudWatch dashboards + SNS alarms
- **Secrets:** AWS Secrets Manager
- **IaC:** Terraform 1.7+
- **CI/CD:** GitHub Actions
- **AI:** OpenAI GPT-4o-mini (distress signal scoring)

## Architecture Decisions

| Decision | Why |
|----------|-----|
| No NAT Gateway | Saves $32/mo; only load + api Lambdas in VPC (for RDS) |
| RDS t4g.micro | Cheapest burst-capable instance; SQL skill signal |
| Step Functions over chained Lambdas | Retry + visual state + failure isolation |
| Lambda Function URL over API Gateway | Zero-cost, sufficient for single endpoint MVP |
| S3 + SQS as Lambda boundary | Avoid event payload size limits; decouple stages |
| GPT-4o-mini over GPT-4o | 20x cheaper; sufficient for keyword-style classification |

## Quickstart

```bash
# 1. Bootstrap (one-time)
./scripts/bootstrap.sh your-email@example.com

# 2. Seed API keys
./scripts/seed_secrets.sh RENTCAST_KEY OPENAI_KEY

# 3. Deploy
cd iac
terraform init
terraform apply -var="alert_email=you@example.com"

# 4. Trigger first run manually
aws stepfunctions start-execution \
  --state-machine-arn $(terraform output -raw state_machine_arn) \
  --input '{}'

# 5. Query API
curl "$(terraform output -raw api_url)?limit=5"
```

## Cost Breakdown

See [COST.md](COST.md).

## Runbook

See [RUNBOOK.md](RUNBOOK.md).

## What I Learned

- Serverless pipelines need careful boundary design to avoid NAT Gateway
- Step Functions retry saved hours of bespoke error handling code
- CloudWatch Logs Insights beats kibana-style search for one-off debugging
- Lambda deploy-as-zip is faster than container image for simple Python functions
