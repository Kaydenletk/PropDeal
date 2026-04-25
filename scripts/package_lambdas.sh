#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for L in fetch transform enrich load api; do
  cd "$ROOT/lambdas/$L"
  rm -rf .build
  mkdir -p .build
  cp handler.py .build/
  if [ -s requirements.txt ] && grep -v '^#' requirements.txt | grep -q .; then
    # Force Lambda-compatible wheels (Linux x86_64, Python 3.12)
    # Without these flags, macOS/arm64 dev machines pull native wheels that
    # break at Lambda runtime with ImportError on binary extensions (psycopg).
    pip install -r requirements.txt -t .build/ --quiet --upgrade \
      --platform manylinux2014_x86_64 \
      --python-version 3.12 \
      --only-binary=:all: \
      --implementation cp \
      --abi cp312
  fi
  # Critical for Task 1: load Lambda needs sql/migrations bundled
  if [ "$L" = "load" ]; then
    mkdir -p .build/sql/migrations
    cp "$ROOT/sql/migrations/"*.sql .build/sql/migrations/
  fi
  # Strip unwanted artifacts
  find .build -name "boto3*" -prune -exec rm -rf {} + 2>/dev/null || true
  find .build -name "botocore*" -prune -exec rm -rf {} + 2>/dev/null || true
  find .build -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
  find .build -name "*.pyc" -delete 2>/dev/null || true
  cd "$ROOT" >/dev/null
done
echo "Packaged: $(ls -la "$ROOT"/lambdas/*/.build 2>/dev/null | head -20)"
