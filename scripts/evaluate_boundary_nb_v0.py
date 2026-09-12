#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


ID5_RE = re.compile(r"(?<!\d)\d{5}(?!\d)")


def read_tsv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def norm(v: str) -> str:
    v = (v or "").strip().lower()
    if v in {"y", "yes", "true", "1"}:
        return "yes"
    if v in {"n", "no", "false", "0"}:
        return "no"
    return ""


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
    return p, r, f1


def char_ngrams(text: str, n: int) -> Counter:
    t = (text or "").strip()
    if not t:
        return Counter()
    # Normalize whitespace runs; keep CJK chars as-is.
    t = re.sub(r"\s+", " ", t)
    if len(t) < n:
        return Counter()
    return Counter(t[i : i + n] for i in range(0, len(t) - n + 1))


class NaiveBayes:
    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self.class_doc = Counter()
        self.class_feat = defaultdict(Counter)  # cls -> feat -> count
        self.class_total = Counter()  # cls -> total feat count
        self.vocab = []

    def fit(self, docs: list[tuple[str, Counter]], max_features: int) -> None:
        total_feat = Counter()
        for y, feats in docs:
            self.class_doc[y] += 1
            for f, c in feats.items():
                if c <= 0:
                    continue
                self.class_feat[y][f] += c
                self.class_total[y] += c
                total_feat[f] += c

        self.vocab = [f for f, _ in total_feat.most_common(max_features)]
        vocab_set = set(self.vocab)

        # Drop features outside vocab for speed.
        for y in list(self.class_feat.keys()):
            self.class_feat[y] = Counter({f: c for f, c in self.class_feat[y].items() if f in vocab_set})
            self.class_total[y] = sum(self.class_feat[y].values())

    def predict(self, feats: Counter) -> str:
        if not self.vocab:
            return "yes"

        vocab_set = set(self.vocab)
        feats = Counter({f: c for f, c in feats.items() if f in vocab_set and c > 0})
        v = len(self.vocab)

        best_y = None
        best_score = -1e300
        for y in ["yes", "no"]:
            # Use balanced priors to avoid majority-class collapse on highly imbalanced silver labels.
            score = math.log(0.5)
            denom = self.class_total.get(y, 0) + self.alpha * v
            for f, c in feats.items():
                num = self.class_feat[y].get(f, 0) + self.alpha
                score += c * math.log(num / denom)
            if best_y is None or score > best_score:
                best_y = y
                best_score = score
        return best_y or "yes"


def main() -> None:
    parser = argparse.ArgumentParser(description="Train/evaluate a simple char-ngram NB baseline for boundary_ok.")
    parser.add_argument("--structured-jsonl", required=True, help="data/structured/formulas_v14.jsonl (private; includes raw_text)")
    parser.add_argument("--train-consensus-tsv", required=True, help="data/benchmarks/boundary_consensus_v1.tsv")
    parser.add_argument("--eval-items-tsv", required=True, help="data/benchmarks/items_gold_v2.tsv")
    parser.add_argument("--output-task-eval-tsv", required=True)
    parser.add_argument("--output-error-slices-tsv", required=True)
    parser.add_argument("--model-id", default="nb_char3_v0")
    parser.add_argument("--ngram", type=int, default=3)
    parser.add_argument("--max-features", type=int, default=50000)
    args = parser.parse_args()

    # Map record_id -> raw_text
    text_by_id: dict[str, str] = {}
    for rec in iter_jsonl(Path(args.structured_jsonl).resolve()):
        rid = (rec.get("record_id") or "").strip()
        if not rid:
            continue
        text_by_id[rid] = (rec.get("raw_text") or "").strip()

    train_rows = read_tsv(Path(args.train_consensus_tsv).resolve())
    eval_rows = read_tsv(Path(args.eval_items_tsv).resolve())
    if not train_rows or not eval_rows:
        raise SystemExit("Empty train/eval TSV")

    eval_item_ids = {
        (row.get("item_id") or "").strip()
        for row in eval_rows
        if norm(row.get("boundary_ok_gold") or "") in {"yes", "no"}
    }

    # Train on consensus-agree, train split only.
    train_docs: list[tuple[str, Counter]] = []
    for r in train_rows:
        if (r.get("consensus_status") or "") != "agree":
            continue
        if (r.get("split") or "") != "train":
            continue
        if (r.get("item_id") or "").strip() in eval_item_ids:
            continue
        y = norm(r.get("boundary_ok_consensus") or "")
        if y not in {"yes", "no"}:
            continue
        rid = (r.get("item_id") or "").strip()
        text = text_by_id.get(rid, "")
        if not text:
            continue
        feats = char_ngrams(text, args.ngram)
        train_docs.append((y, feats))

    nb = NaiveBayes(alpha=1.0)
    nb.fit(train_docs, max_features=args.max_features)

    # Evaluate on gold items.
    per_split = defaultdict(list)  # split -> (y, yhat, noise_flags)
    for r in eval_rows:
        split = (r.get("split") or "").strip() or "unknown"
        rid = (r.get("item_id") or "").strip()
        y = norm(r.get("boundary_ok_gold") or "")
        if y not in {"yes", "no"}:
            continue
        text = text_by_id.get(rid, "")
        feats = char_ngrams(text, args.ngram) if text else Counter()
        yhat = nb.predict(feats)
        per_split[split].append((y, yhat, (r.get("noise_flags") or "").strip() or "(none)"))

    eval_table = []
    slice_stats = defaultdict(lambda: Counter())  # (slice_value) -> counts, for split=all

    for split in ["train", "dev", "test", "all"]:
        gold = []
        if split == "all":
            for s in ["train", "dev", "test"]:
                gold.extend(per_split.get(s, []))
        else:
            gold = per_split.get(split, [])
        if not gold:
            continue

        n = len(gold)
        correct = sum(1 for y, yhat, _ in gold if y == yhat)
        tp = sum(1 for y, yhat, _ in gold if y == "no" and yhat == "no")
        fp = sum(1 for y, yhat, _ in gold if y == "yes" and yhat == "no")
        fn = sum(1 for y, yhat, _ in gold if y == "no" and yhat == "yes")
        p, r, f1 = prf(tp, fp, fn)

        eval_table.append(
            {
                "task_id": "entry_segmentation",
                "model_id": args.model_id,
                "split": split,
                "label_column": "boundary_ok_gold",
                "n_labeled": str(n),
                "accuracy": f"{(correct/n):.4f}",
                "no_precision": f"{p:.4f}",
                "no_recall": f"{r:.4f}",
                "no_f1": f"{f1:.4f}",
                "tp_no": str(tp),
                "fp_no": str(fp),
                "fn_no": str(fn),
                "notes": f"char_{args.ngram}gram_nb trained on consensus(train) after excluding all gold-evaluation item IDs; no treated as positive class",
            }
        )

    # Error slices across all splits (to match existing tables).
    all_gold = []
    for s in ["train", "dev", "test"]:
        all_gold.extend(per_split.get(s, []))
    for y, yhat, noise in all_gold:
        c = slice_stats[noise]
        c["n"] += 1
        if y == yhat:
            c["correct"] += 1
        if y == "no" and yhat == "no":
            c["tp_no"] += 1
        if y == "yes" and yhat == "no":
            c["fp_no"] += 1
        if y == "no" and yhat == "yes":
            c["fn_no"] += 1

    slice_rows = []
    for noise, c in sorted(slice_stats.items(), key=lambda kv: (-kv[1]["n"], kv[0])):
        n = c["n"]
        tp, fp, fn = c["tp_no"], c["fp_no"], c["fn_no"]
        p, r, f1 = prf(tp, fp, fn)
        slice_rows.append(
            {
                "task_id": "entry_segmentation",
                "model_id": args.model_id,
                "label_column": "boundary_ok_gold",
                "slice_key": "noise_flags",
                "slice_value": noise,
                "n_labeled": str(n),
                "accuracy": f"{(c['correct']/n):.4f}",
                "no_precision": f"{p:.4f}",
                "no_recall": f"{r:.4f}",
                "no_f1": f"{f1:.4f}",
                "tp_no": str(tp),
                "fp_no": str(fp),
                "fn_no": str(fn),
            }
        )

    write_tsv(
        Path(args.output_task_eval_tsv).resolve(),
        [
            "task_id",
            "model_id",
            "split",
            "label_column",
            "n_labeled",
            "accuracy",
            "no_precision",
            "no_recall",
            "no_f1",
            "tp_no",
            "fp_no",
            "fn_no",
            "notes",
        ],
        eval_table,
    )
    write_tsv(
        Path(args.output_error_slices_tsv).resolve(),
        [
            "task_id",
            "model_id",
            "label_column",
            "slice_key",
            "slice_value",
            "n_labeled",
            "accuracy",
            "no_precision",
            "no_recall",
            "no_f1",
            "tp_no",
            "fp_no",
            "fn_no",
        ],
        slice_rows,
    )

    print(f"Wrote: {Path(args.output_task_eval_tsv).resolve()} ({len(eval_table)} rows)")
    print(f"Wrote: {Path(args.output_error_slices_tsv).resolve()} ({len(slice_rows)} rows)")


if __name__ == "__main__":
    main()
