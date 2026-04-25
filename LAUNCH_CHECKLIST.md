# Launch Checklist

Manual steps required before/after deploy. Code is complete; these require AWS credentials, API keys, and your own infrastructure.

## Pre-Deploy

- [ ] **AWS CLI configured** with admin credentials (`aws sts get-caller-identity` works)
- [ ] **Region set** to `us-east-1` (or update `iac/variables.tf` + `iac/backend.tf`)
- [ ] **RentCast account** created — free tier API key obtained
- [ ] **OpenAI account** created — API key with billing enabled
- [ ] **Bootstrap** the Terraform state backend + billing alarm:
  ```bash
  ./scripts/bootstrap.sh your-email@example.com
  ```
- [ ] **Replace `<ACCOUNT_ID>`** in `iac/backend.tf` with your AWS account ID:
  ```bash
  ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
  sed -i.bak "s/<ACCOUNT_ID>/$ACCOUNT/" iac/backend.tf
  rm iac/backend.tf.bak
  ```
- [ ] **Seed secrets**:
  ```bash
  ./scripts/seed_secrets.sh YOUR_RENTCAST_KEY YOUR_OPENAI_KEY
  ```

## Deploy

- [ ] `cd iac && terraform init`
- [ ] `terraform fmt -recursive`
- [ ] `terraform validate`
- [ ] `terraform plan -var="alert_email=you@example.com"`
- [ ] `terraform apply -var="alert_email=you@example.com"` (~10 min — RDS provisioning dominates)
- [ ] **Confirm SNS subscription** in your email inbox (billing + alerts)

## Verify

- [ ] **Trigger pipeline manually**:
  ```bash
  aws stepfunctions start-execution \
    --state-machine-arn $(cd iac && terraform output -raw state_machine_arn) \
    --input '{}'
  ```
- [ ] **Step Functions console** shows green run end-to-end (~2 min)
- [ ] **RDS query** via Query Editor:
  ```sql
  SELECT listing_id, city, price, distress_score
  FROM listings
  WHERE distress_score > 0.5
  ORDER BY distress_score DESC LIMIT 10;
  ```
- [ ] **API curl**:
  ```bash
  curl "$(cd iac && terraform output -raw api_url)?limit=5" | jq
  ```

## CI/CD Setup

- [ ] **GitHub repo** created and code pushed (`git remote add origin ...; git push -u origin main`)
- [ ] **GitHub Actions secrets** set:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
- [ ] **Open dummy PR** touching `iac/` — confirm `terraform-plan` workflow runs and comments
- [ ] **Merge to main** with `iac/` change — confirm `terraform-apply` runs

## Portfolio Artifacts

- [ ] `docs/architecture.png` — export from `docs/architecture.md` Mermaid via excalidraw.com or draw.io
- [ ] `docs/screenshots/step-functions-success.png`
- [ ] `docs/screenshots/cloudwatch-dashboard.png`
- [ ] `docs/screenshots/github-actions.png`
- [ ] `docs/screenshots/rds-query.png`
- [ ] **Blog post** (~800 words) on dev.to or personal blog
- [ ] **Demo video** (3 min, YouTube unlisted) covering: architecture → terraform apply → SFN run → dashboard → API curl
- [ ] **LinkedIn launch post** (template in `docs/plans/2026-04-24-proptech-ai-cloud-pipeline.md` Task 25)

## Final Tag

```bash
git add docs/screenshots/ docs/architecture.png
git commit -m "docs: add portfolio screenshots"
git tag -a v1.0.0 -m "Week 8 launch — full pipeline operational"
git push origin main --tags
```

## Notes

- `psycopg[binary]==3.2.3` in plan was a typo — actual version 3.2.4 is used (gap in PyPI between 3.1.18 and 3.2.4).
- Local pytest of all 5 Lambda test suites passed (14 tests total).
- `<ACCOUNT_ID>` in `iac/backend.tf` is intentional — replace before `terraform init`.
