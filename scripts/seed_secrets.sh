#!/usr/bin/env bash
set -euo pipefail

RENTCAST_KEY="${1:?Usage: seed_secrets.sh <rentcast_key> <openai_key>}"
OPENAI_KEY="${2:?Missing openai key}"

aws secretsmanager create-secret \
  --name propdeal/rentcast/api-key \
  --secret-string "{\"api_key\":\"$RENTCAST_KEY\"}" \
  --description "RentCast API key" \
  || aws secretsmanager update-secret \
       --secret-id propdeal/rentcast/api-key \
       --secret-string "{\"api_key\":\"$RENTCAST_KEY\"}"

aws secretsmanager create-secret \
  --name propdeal/openai/api-key \
  --secret-string "{\"api_key\":\"$OPENAI_KEY\"}" \
  --description "OpenAI API key" \
  || aws secretsmanager update-secret \
       --secret-id propdeal/openai/api-key \
       --secret-string "{\"api_key\":\"$OPENAI_KEY\"}"

echo "Secrets seeded."
