# Service Level Objectives

## Pipeline Success SLO

**Target:** 99% successful Step Functions executions over rolling 30 days.

**Metric source:** `AWS/States` namespace, `ExecutionsSucceeded` / `ExecutionsStarted` per state machine.

**Error budget (30 days):**
- Total expected runs: 30 (1/day via EventBridge cron)
- Allowed failures: 0.3 → effectively 0 in any month
- Therefore: any failed execution = SLO breach

**Alarm:** `proptech-pipeline-slo-breach` fires when `ExecutionsSucceeded < 1` over a 24-hour window. Action: SNS → email.

**Reporting:** CloudWatch dashboard "Pipeline success vs fail" widget.

## Lambda Latency SLO

**Target:** p95 < 30s per Lambda over rolling 7 days.

**Metric source:** `AWS/Lambda` `Duration` p95 per function.

## API Availability SLO

**Target:** 99% of `api` invocations return 2xx over rolling 7 days (excluding deliberate IAM 403 from unsigned requests).

**Metric source:** Lambda errors + Function URL request count.

## Cost SLO

**Target:** Monthly AWS bill < $20 in months 1-12, < $25 in months 13-24.

**Source:** AWS Cost Explorer monthly report.
