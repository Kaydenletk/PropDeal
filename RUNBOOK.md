# Runbook

## Pipeline Failed — Where to Look

1. **Step Functions console** → executions → click failed run → graph shows failing state
2. **CloudWatch Logs** → `/aws/lambda/proptech-<stage>` → most recent stream
3. **SQS DLQ** → `aws sqs receive-message --queue-url $(cd iac && terraform output -raw dlq_url)` to see failure payloads

## Common Failures

### fetch Lambda: `RentCast API error 401`
API key invalid or rate-limited.
```bash
# Check secret
aws secretsmanager get-secret-value --secret-id proptech/rentcast/api-key
# Rotate
aws secretsmanager update-secret --secret-id proptech/rentcast/api-key --secret-string '{"api_key":"new-key"}'
```

### load Lambda: `could not connect to server`
RDS unreachable from Lambda. Verify:
- Lambda has VPC config
- Security group allows 5432 from Lambda SG
- RDS is in same VPC

### enrich Lambda: timeout
Increase timeout in `iac/main.tf` `enrich_lambda` module, reapply.

### Step Functions execution stuck
Check individual Lambda — DLQ likely has message. Drain DLQ and replay:
```bash
aws sqs receive-message --queue-url $DLQ_URL --max-number-of-messages 10
# Inspect, fix root cause, then:
aws lambda invoke --function-name proptech-<stage> --payload '<from-dlq>' out.json
```

## Rotating Secrets

```bash
./scripts/seed_secrets.sh NEW_RENTCAST_KEY NEW_OPENAI_KEY
# Lambdas pick up on next cold start; force:
aws lambda update-function-configuration --function-name proptech-fetch --environment Variables={}
```

## Cost Spike Investigation

1. Cost Explorer → group by service → identify offender
2. CloudWatch dashboard `proptech-pipeline` → check Lambda invocation count
3. If invocations spiked: check EventBridge Scheduler for accidental manual triggers
4. If RDS CPU high: check for long-running query via `pg_stat_activity`

## Disaster Recovery

Terraform state is the source of truth.
```bash
cd iac
terraform destroy  # nukes everything except state bucket + RDS final snapshot
terraform apply    # recreate
```

Migration SQL is embedded in load Lambda — runs on first invocation.
