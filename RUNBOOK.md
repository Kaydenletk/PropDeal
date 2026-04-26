# Runbook

## Initial Deploy Bootstrap (one-time)

Run from repo root. `bootstrap_state.sh` is idempotent — re-running against
existing resources is a no-op. `bootstrap.sh` is independent and only sets up
the billing alarm; run it once.

1. `./scripts/bootstrap_state.sh you@example.com`
   - Creates S3 state bucket + DynamoDB lock table
   - Generates `iac/backend.tf` with the real bucket/table names
2. `cd iac && terraform init -migrate-state`
3. `./scripts/seed_secrets.sh` (provide RentCast + OpenAI keys via prompts)
4. `./scripts/package_lambdas.sh`
5. `terraform plan -var="alert_email=you@example.com"` — review
6. `terraform apply -var="alert_email=you@example.com"` — apply
7. `./scripts/bootstrap.sh you@example.com` — billing alarm (one-time, AWS-account-wide)

### Re-deploy

After Bootstrap:

1. `./scripts/package_lambdas.sh` (rebuild zips on every code change)
2. `cd iac && terraform apply -var="alert_email=you@example.com"`

### Script scopes

| Script                        | Purpose                                                              | Re-run safe?                                  |
| ----------------------------- | -------------------------------------------------------------------- | --------------------------------------------- |
| `scripts/bootstrap_state.sh`  | Terraform S3 backend + DynamoDB lock + writes `iac/backend.tf`       | yes                                           |
| `scripts/bootstrap.sh`        | Account-wide billing alarm via SNS + CloudWatch                      | yes (subscription confirm email may resend)   |
| `scripts/seed_secrets.sh`     | Push RentCast/OpenAI keys to Secrets Manager                         | yes                                           |
| `scripts/package_lambdas.sh`  | Build Lambda zips for Terraform to upload                            | yes                                           |

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
