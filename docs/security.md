# Security Posture

## Data handling
- All listing data is sourced from RentCast public real-estate API (no PII at source by design).
- Free-text descriptions may contain seller-supplied phone/email; the `transform` Lambda redacts these via regex before any data reaches OpenAI or RDS.
- Listings are stored in private RDS Postgres in a VPC private subnet.
- The public API Lambda Function URL requires AWS IAM (SigV4) authentication — no anonymous access.

## Secret management
- All credentials in AWS Secrets Manager.
- Quarterly manual key rotation documented in RUNBOOK.md.
- Lambda IAM roles use least-privilege resource-scoped policies.

## Known limits
- Single-region (us-east-1) — no cross-region failover.
- No WAF in front of API (free-tier constraint). IAM auth + low rate limits provide minimal abuse protection.
- No automated dependency scanning yet (TODO: enable Dependabot post-Phase 1).

## Incident response
- CloudWatch alarms → SNS topic → email.
- Manual: `terraform destroy` to scrub all infra; secrets stay in Secrets Manager 7 days for recovery.
