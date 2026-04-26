#!/usr/bin/env bash
set -euo pipefail

# Bootstrap Terraform remote state backend.
# Creates S3 state bucket + DynamoDB lock table, then generates iac/backend.tf
# pointing at them. Idempotent: re-runs against existing resources are no-ops.
#
# Usage: ./scripts/bootstrap_state.sh <alert_email>

ALERT_EMAIL="${1:?usage: $0 <alert_email>}"
REGION="${AWS_REGION:-us-east-1}"
ACCT=$(aws sts get-caller-identity --query Account --output text)
BUCKET="proptech-tfstate-${ACCT}"
TABLE="proptech-tflock"

echo "==> Creating state bucket s3://$BUCKET in $REGION"
if [ "$REGION" = "us-east-1" ]; then
  aws s3api create-bucket --bucket "$BUCKET" 2>&1 | grep -v "BucketAlreadyOwnedByYou" || true
else
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" \
    2>&1 | grep -v "BucketAlreadyOwnedByYou" || true
fi

aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration '{
  "Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]
}'
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

echo "==> Creating lock table $TABLE"
aws dynamodb create-table \
  --table-name "$TABLE" \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --region "$REGION" \
  2>&1 | grep -v "ResourceInUseException" || true

aws dynamodb wait table-exists --table-name "$TABLE" --region "$REGION"

cat > iac/backend.tf <<EOF
terraform {
  backend "s3" {
    bucket         = "$BUCKET"
    key            = "proptech/terraform.tfstate"
    region         = "$REGION"
    dynamodb_table = "$TABLE"
    encrypt        = true
  }
}
EOF

echo ""
echo "==> Bootstrap complete."
echo "Next steps:"
echo "  cd iac"
echo "  terraform init -migrate-state"
echo "  terraform plan -var=\"alert_email=$ALERT_EMAIL\""
echo "  terraform apply -var=\"alert_email=$ALERT_EMAIL\""
