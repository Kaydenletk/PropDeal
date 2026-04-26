# Cost Breakdown

## Free-tier baseline (first 12 months, US-East-1)

| Service | Free tier | This pipeline |
|---------|-----------|---------------|
| Lambda  | 1M req/mo forever | ~150 req/mo (5 lambdas × 30 days) |
| Step Functions Standard | 4k transitions/mo forever | ~150 transitions/mo |
| S3 Standard | 5GB + 2k PUT/mo for 12 mo | <1GB, ~90 PUT/mo |
| RDS t4g.micro | 750 hr/mo for 12 mo | 730 hr/mo |
| CloudWatch Logs | 5GB/mo forever | ~0.5–2 GB/mo |
| SQS / SNS | 1M req/mo forever | trivial |

## Real ongoing line items (NOT free)

| Item | Monthly cost | Why |
|------|-------------|-----|
| Secrets Manager (3 secrets) | $1.20 | Not in free tier ($0.40/secret) |
| CloudWatch alarm metrics (~6 alarms) | $0.60 | $0.10/alarm/mo |
| CloudWatch dashboard | $3.00 | $3/dashboard after first 3 |
| NAT instance t4g.nano (free tier) | $0.00 | Free under t4g 750hr |
| Data transfer | <$0.50 | Inbound free, outbound minimal |

**Total during free tier (months 1-12): ~$3-5/mo**

## Post-12-month run rate

| Item | Monthly cost |
|------|-------------|
| RDS t4g.micro | $12.50 |
| All free-tier-expired storage | ~$1 |
| Secrets + alarms + dashboard | ~$5 |
| **Total** | **~$18-20/mo** |

Mitigation post-12-mo: migrate to Aurora Serverless v2 (auto-pause at 0 ACU = $0 idle) OR Neon free tier OR shut down RDS and replay from S3 archive on demand.

## One-time costs

| Item | Cost |
|------|------|
| OpenAI prepaid credit | $5 (lasts ~6 months) |
| RentCast | $0 (free tier 50 calls/day) |

## Honest summary

- **First 12 months:** $3-5/month + $5 one-time OpenAI = ~$45 total year 1
- **Year 2+:** ~$18-20/month unless migrated off RDS
