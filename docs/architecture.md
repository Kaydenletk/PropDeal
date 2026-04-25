# Architecture

> Source diagram. Export PNG to `docs/architecture.png` via excalidraw.com or draw.io.

```mermaid
flowchart LR
  EB[EventBridge Scheduler<br/>cron 0 2 * * *]
  SFN[Step Functions<br/>proptech-pipeline]
  FETCH[Lambda: fetch]
  TRANSFORM[Lambda: transform]
  ENRICH[Lambda: enrich<br/>GPT-4o-mini]
  LOAD[Lambda: load<br/>VPC]
  API[Lambda: api<br/>VPC + Function URL]
  RAW[(S3: raw)]
  CLEAN[(S3: clean)]
  RDS[(RDS Postgres<br/>private subnet)]
  DLQ[[SQS DLQ]]
  SECRETS[Secrets Manager<br/>rentcast / openai / rds]
  CW[CloudWatch<br/>dashboard + alarms]
  SNS[SNS<br/>email alerts]

  EB --> SFN
  SFN --> FETCH --> RAW
  FETCH -. failure .-> DLQ
  SFN --> TRANSFORM
  RAW --> TRANSFORM --> CLEAN
  TRANSFORM -. failure .-> DLQ
  SFN --> ENRICH
  CLEAN --> ENRICH --> CLEAN
  ENRICH -. failure .-> DLQ
  SFN --> LOAD
  CLEAN --> LOAD --> RDS
  LOAD -. failure .-> DLQ
  API --> RDS
  SECRETS --> FETCH
  SECRETS --> ENRICH
  SECRETS --> LOAD
  SECRETS --> API
  FETCH & TRANSFORM & ENRICH & LOAD & API --> CW
  CW --> SNS
```

## Components

- **EventBridge Scheduler** — nightly trigger 02:00 UTC.
- **Step Functions** — orchestrates fetch → transform → enrich → load with retries.
- **fetch Lambda** — RentCast API → S3 raw bucket.
- **transform Lambda** — S3 raw → S3 clean (normalize fields).
- **enrich Lambda** — S3 clean → S3 clean (GPT-4o-mini distress score).
- **load Lambda** — S3 clean → RDS Postgres (in VPC).
- **api Lambda** — RDS → JSON via Lambda Function URL.
- **SQS DLQ** — captures Lambda failures.
- **CloudWatch dashboard + SNS alarms** — observability + email on errors.
- **Secrets Manager** — RentCast key, OpenAI key, RDS credentials.

## VPC Boundary

Only `load` and `api` Lambdas attach to VPC (RDS access). `fetch`, `transform`, `enrich` run outside VPC to avoid NAT Gateway cost.
