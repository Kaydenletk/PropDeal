#!/usr/bin/env bash
set -euo pipefail

# Local validation gate for PropDeal Phase 1A.0.
# Run before any `terraform apply`.
#
# Prerequisites:
#   brew install terraform tflint awscli   # macOS
#   curl -L https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash  # linux
#   pip install -r requirements-dev.txt    # for python validators (optional)
#
# Usage:
#   ./scripts/validate_local.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> [1/5] terraform fmt -check"
terraform -chdir=iac fmt -check -recursive

echo "==> [2/5] terraform validate"
terraform -chdir=iac init -backend=false -upgrade
terraform -chdir=iac validate

echo "==> [3/5] tflint"
if command -v tflint >/dev/null 2>&1; then
  tflint --chdir=iac --recursive || {
    echo "tflint reported issues. Fix or update .tflint.hcl rules."
    exit 1
  }
else
  echo "  WARN: tflint not installed; skipping. brew install tflint"
fi

echo "==> [4/5] ASL JSON parse"
python3 - <<'PY'
import json, sys
try:
    json.load(open("iac/asl/pipeline.json"))
    print("  pipeline.json: valid JSON")
except Exception as e:
    print(f"  FAIL: pipeline.json invalid: {e}")
    sys.exit(1)
PY

echo "==> [5/5] ASL semantic validate (aws CLI)"
if command -v aws >/dev/null 2>&1; then
  TMP=$(mktemp)
  sed -e 's/${fetch_arn}/arn:aws:lambda:us-east-1:000000000000:function:fetch/g' \
      -e 's/${transform_arn}/arn:aws:lambda:us-east-1:000000000000:function:transform/g' \
      -e 's/${enrich_arn}/arn:aws:lambda:us-east-1:000000000000:function:enrich/g' \
      -e 's/${load_arn}/arn:aws:lambda:us-east-1:000000000000:function:load/g' \
      -e 's/${sns_topic_arn}/arn:aws:sns:us-east-1:000000000000:alerts/g' \
      -e 's/${raw_bucket}/propdeal-raw/g' \
      -e 's/${clean_bucket}/propdeal-clean/g' \
      iac/asl/pipeline.json > "$TMP"
  aws stepfunctions validate-state-machine-definition \
    --definition file://"$TMP" \
    --type STANDARD \
    --query result --output text || {
    echo "  ASL semantic validation failed."
    cat "$TMP"
    rm -f "$TMP"
    exit 1
  }
  rm -f "$TMP"
else
  echo "  WARN: aws CLI not installed; skipping. brew install awscli"
fi

echo ""
echo "==> All local validation gates passed"
