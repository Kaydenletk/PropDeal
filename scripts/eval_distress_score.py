"""Eval harness for distress scoring.

Usage:
  python scripts/eval_distress_score.py --prompt v3 --model gpt-4o-mini --threshold 0.5
  python scripts/eval_distress_score.py --baseline regex
"""
import argparse
import json
import os
import pathlib
import random
import sys
import time
from typing import Iterable

EVAL_FILE = "tests/fixtures/distress_eval.jsonl"
HOLDOUT_FRAC = 0.30
SEED = 42

# Add scripts/ to path so regex_baseline imports
sys.path.insert(0, str(pathlib.Path(__file__).parent))


def load_data():
    if not os.path.exists(EVAL_FILE):
        print(f"  WARN: {EVAL_FILE} not found. Returning empty dataset.", file=sys.stderr)
        return [], []
    with open(EVAL_FILE) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    rng = random.Random(SEED)
    rng.shuffle(rows)
    n_holdout = int(len(rows) * HOLDOUT_FRAC)
    holdout = rows[:n_holdout]
    dev = rows[n_holdout:]
    return dev, holdout


def predict_llm(rows: Iterable[dict], prompt: str, model: str, threshold: float):
    if model.startswith("claude"):
        from anthropic import Anthropic
        client = Anthropic()
        def call(desc):
            r = client.messages.create(
                model=model, max_tokens=200,
                messages=[{"role": "user", "content": prompt + (desc or "")}],
            )
            return r.content[0].text
    else:
        from openai import OpenAI
        client = OpenAI()
        def call(desc):
            r = client.chat.completions.create(
                model=model, temperature=0,
                messages=[{"role": "user", "content": prompt + (desc or "")}],
                response_format={"type": "json_object"},
            )
            return r.choices[0].message.content
    preds = []
    cost = 0.0
    for r in rows:
        try:
            txt = call(r.get("description") or "")
            obj = json.loads(txt)
            score = float(obj.get("score", 0))
            preds.append(1 if score >= threshold else 0)
        except Exception as e:
            print(f"  fail on {r.get('listing_id')}: {e}", file=sys.stderr)
            preds.append(0)
        cost += 0.0005 if "mini" in model else 0.005
    return preds, cost


def predict_regex(rows: Iterable[dict]):
    from regex_baseline import predict
    return [predict(r.get("description")) for r in rows], 0.0


def bootstrap_ci(y_true, y_pred, metric_fn, n_iter=1000):
    rng = random.Random(SEED)
    n = len(y_true)
    samples = []
    for _ in range(n_iter):
        idx = [rng.randrange(n) for _ in range(n)]
        yt = [y_true[i] for i in idx]
        yp = [y_pred[i] for i in idx]
        samples.append(metric_fn(yt, yp))
    samples.sort()
    return samples[int(0.025 * n_iter)], samples[int(0.975 * n_iter)]


def f1(y_true, y_pred):
    from sklearn.metrics import precision_recall_fscore_support
    _, _, f, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="v3", choices=["v1", "v2", "v3"])
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--baseline", choices=["regex"], help="Run regex baseline instead of LLM")
    ap.add_argument("--split", default="dev", choices=["dev", "holdout"])
    args = ap.parse_args()

    dev, holdout = load_data()
    rows = dev if args.split == "dev" else holdout
    if not rows:
        print("No labeled data — run scripts/label_listings.py first.")
        return

    from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

    y_true = [r["human_label"] for r in rows]
    print(f"\n=== Eval split={args.split} N={len(rows)} positives={sum(y_true)} ===")

    t0 = time.time()
    if args.baseline:
        y_pred, cost = predict_regex(rows)
        label = "regex_baseline"
    else:
        prompt = open(f"lambdas/enrich/prompts/{args.prompt}.txt").read()
        y_pred, cost = predict_llm(rows, prompt, args.model, args.threshold)
        label = f"{args.model}+{args.prompt}"

    p, r, fscore, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    f1_lo, f1_hi = bootstrap_ci(y_true, y_pred, f1)

    print(f"\n## Results ({label})")
    print(f"| Metric | Value |")
    print(f"|--------|-------|")
    print(f"| Precision | {p:.3f} |")
    print(f"| Recall    | {r:.3f} |")
    print(f"| F1        | {fscore:.3f} |")
    print(f"| F1 95% CI | [{f1_lo:.3f}, {f1_hi:.3f}] |")
    print(f"| Confusion matrix (TN FP / FN TP) | {cm.tolist()} |")
    print(f"| Cost (USD) | {cost:.4f} |")
    print(f"| Wall time (s) | {time.time()-t0:.1f} |")


if __name__ == "__main__":
    main()
