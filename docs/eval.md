# Distress-Score Eval Harness

## Methodology

- **Dataset:** N=[N] hand-labeled listings (`tests/fixtures/distress_eval.jsonl`)
  - Sources: 80 public Zillow / Realtor.com seed listings + ~50 RDS-pulled RentCast listings
  - Composition: ~50% positive (distress signals present), ~50% negative
- **Split:** 70% dev (prompt iteration) / 30% holdout (final number reported once, no peeking)
- **Labels:** Binary 0/1 by primary rater following rubric in `scripts/label_listings.py`
- **Inter-rater reliability:** Cohen's κ = [κ value] on 20-item second-rater subset
  - Interpretation: [poor / fair / moderate / substantial / almost perfect]
- **CI:** 95% bootstrap (1000 resamples) on F1
- **Threshold:** 0.5 score → label 1

## Results (dev split)

| Variant | Precision | Recall | F1 | F1 95% CI | Cost / 1k listings |
|---------|-----------|--------|----|-----------|--------------------|
| Regex baseline | TBD | TBD | TBD | — | $0.00 |
| GPT-4o-mini + v1 prompt | TBD | TBD | TBD | TBD | $0.50 |
| GPT-4o-mini + v2 prompt | TBD | TBD | TBD | TBD | $0.50 |
| GPT-4o-mini + v3 prompt | TBD | TBD | TBD | TBD | $0.50 |
| Claude Haiku 4.5 + v3 (if available) | TBD | TBD | TBD | TBD | $1.00 |

**Best dev variant:** TBD

## Holdout result (final, no further iteration)

| Metric | Value |
|--------|-------|
| Precision | TBD |
| Recall | TBD |
| F1 | TBD |
| F1 95% CI | TBD |

## Failure mode analysis

### False positives (model said 1, human said 0)

1. **Listing [id]:** [description of why model misfired]
2. ...
3. ...

### False negatives (model said 0, human said 1)

1. **Listing [id]:** [description of subtle distress phrasing model missed]
2. ...
3. ...

## Decision: shipped variant

**Production prompt + model:** TBD (selected based on best holdout F1 within cost budget)

**Rationale:** [Δ vs regex] beat regex baseline; within 95% CI of best variant; lowest cost.

## Limitations

- N=[N] with single primary rater means F1 has ±[CI] confidence interval at this sample size; treat the F1 number as a methodology demonstration, not a precise performance claim.
- Geographic distribution skews toward investor-friendly metros (Memphis, Cleveland, Birmingham). Performance may differ in coastal markets.
- Eval set was labeled blind from model output to avoid circular validation.

## Reproducing this report

```bash
pip install -r requirements-dev.txt
python scripts/eval_distress_score.py --baseline regex
python scripts/eval_distress_score.py --prompt v3 --model gpt-4o-mini --split dev
python scripts/eval_distress_score.py --prompt v3 --model gpt-4o-mini --split holdout
```
