#!/usr/bin/env bash
set -euo pipefail

# One-time billing alarm bootstrap.
# Creates an SNS topic + email subscription + CloudWatch billing alarm
# that fires when estimated charges exceed $50. Independent of Terraform
# state (see scripts/bootstrap_state.sh for that) so the alarm is in
# place even if a later Terraform apply fails.
#
# Usage: ./scripts/bootstrap.sh <billing-email>

BILLING_EMAIL="${1:?Usage: bootstrap.sh <your-email>}"
REGION="us-east-1"  # AWS/Billing metrics only publish to us-east-1

echo "==> Creating billing alarm (threshold \$50) in $REGION"

aws sns create-topic --name propdeal-billing-alerts --region "$REGION" >/dev/null
TOPIC_ARN=$(aws sns list-topics --region "$REGION" \
  --query "Topics[?contains(TopicArn,'propdeal-billing-alerts')].TopicArn" \
  --output text)

aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "$BILLING_EMAIL" \
  --region "$REGION" >/dev/null

aws cloudwatch put-metric-alarm \
  --alarm-name propdeal-billing-50-usd \
  --alarm-description "Alert when AWS bill exceeds \$50" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 21600 \
  --evaluation-periods 1 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Currency,Value=USD \
  --alarm-actions "$TOPIC_ARN" \
  --region "$REGION"

echo "==> Billing alarm provisioned. Confirm the SNS subscription email sent to $BILLING_EMAIL."
