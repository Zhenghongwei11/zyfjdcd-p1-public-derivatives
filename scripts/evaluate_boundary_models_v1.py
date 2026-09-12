#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


ID5_RE = re.compile(r"(?<!\d)\d{5}(?!\d)")
EMBEDDED_START_RE = re.compile(r"(?<!\d)(?P<formula_id>\d{5})(?=[\u4e00-\u9fff])")

TOP_HEADINGS = ("【组成】", "【异名】")
CORE_HEADINGS = ("【组成】", "【用法】", "【功用】", "【主治】")


def read_tsv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def norm(v: str) -> str:
    v = (v or "").strip().lower()
    if v in {"y", "yes", "true", "1"}:
        return "yes"
    if v in {"n", "no", "false", "0"}:
        return "no"
    if v in {"unsure", "unknown", "na", "n/a", ""}:
        return ""
    return v


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
    return p, r, f1


def baseline_inline_formula_id(noise_flags: str) -> str:
    flags = set((noise_flags or "").split("|")) if noise_flags else set()
    return "no" if "inline_formula_id" in flags else "yes"


def load_md_span(root: Path, source_file: str, start_line: int, end_line: int) -> str:
    p = Path(source_file)
    if not p.is_absolute():
        p = (root / p).resolve()
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    s = max(0, start_line - 1)
    e = max(s, end_line)  # inclusive -> slice end
    return "\n".join(lines[s:e]).strip()


def looks_like_new_entry(window: str) -> bool:
    has_citation = ("（《" in window) or ("(《" in window)
    has_heading = any(h in window for h in TOP_HEADINGS)
    return has_citation or has_heading


def rule_md_span_v1(span: str) -> str:
    if not span:
        return "no"

    ids = ID5_RE.findall(span)
    uniq = sorted(set(ids))
    if len(uniq) <= 1:
        repeats = [h for h in CORE_HEADINGS if span.count(h) >= 2]
        return "no" if repeats else "yes"

    # Multiple ids: mark "no" when at least one non-initial id looks like a true new entry start.
    for m in EMBEDDED_START_RE.finditer(span):
        if m.start() == 0:
            continue
        window = span[m.start() : m.start() + 400]
        if looks_like_new_entry(window):
            return "no"
    return "yes"


def eval_model(rows: list[dict], label_col: str, model_id: str, root: Path | None) -> tuple[list[dict], list[dict]]:
    # task_eval rows per split + error_slices by noise_flags
    eval_rows = []
    slice_stats = defaultdict(lambda: Counter())

    for split in ["train", "dev", "test", "all"]:
        gold = []
        for r in rows:
            if split != "all" and (r.get("split") or "") != split:
                continue
            y = norm(r.get(label_col) or "")
            if y not in {"yes", "no"}:
                continue

            if model_id == "baseline_inline_formula_id":
                yhat = baseline_inline_formula_id(r.get("noise_flags") or "")
            elif model_id == "rule_md_span_v1":
                if root is None:
                    raise SystemExit("rule_md_span_v1 requires --root")
                try:
                    s = int((r.get("source_line_start") or "0") or "0")
                    e = int((r.get("source_line_end") or "0") or "0")
                except ValueError:
                    s = e = 0
                span = load_md_span(root, r.get("source_file") or "", s, e)
                yhat = rule_md_span_v1(span)
            else:
                raise SystemExit(f"Unknown model_id: {model_id}")

            gold.append((y, yhat, r))

            if split == "all":
                key = (r.get("noise_flags") or "").strip() or "(none)"
                c = slice_stats[(model_id, key)]
                c["n"] += 1
                if y == yhat:
                    c["correct"] += 1
                if y == "no" and yhat == "no":
                    c["tp_no"] += 1
                if y == "yes" and yhat == "no":
                    c["fp_no"] += 1
                if y == "no" and yhat == "yes":
                    c["fn_no"] += 1

        if not gold:
            continue

        n = len(gold)
        correct = sum(1 for y, yhat, _ in gold if y == yhat)
        tp = sum(1 for y, yhat, _ in gold if y == "no" and yhat == "no")
        fp = sum(1 for y, yhat, _ in gold if y == "yes" and yhat == "no")
        fn = sum(1 for y, yhat, _ in gold if y == "no" and yhat == "yes")
        p, r, f1 = prf(tp, fp, fn)
        eval_rows.append(
            {
                "task_id": "entry_segmentation",
                "model_id": model_id,
                "split": split,
                "label_column": label_col,
                "n_labeled": str(n),
                "accuracy": f"{(correct/n):.4f}",
                "no_precision": f"{p:.4f}",
                "no_recall": f"{r:.4f}",
                "no_f1": f"{f1:.4f}",
                "tp_no": str(tp),
                "fp_no": str(fp),
                "fn_no": str(fn),
                "notes": "no treated as positive class",
            }
        )

    slice_rows = []
    for (mid, key), c in sorted(slice_stats.items(), key=lambda kv: (-kv[1]["n"], kv[0][0], kv[0][1])):
        n = c["n"]
        tp, fp, fn = c["tp_no"], c["fp_no"], c["fn_no"]
        p, r, f1 = prf(tp, fp, fn)
        slice_rows.append(
            {
                "task_id": "entry_segmentation",
                "model_id": mid,
                "label_column": label_col,
                "slice_key": "noise_flags",
                "slice_value": key,
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

    return eval_rows, slice_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate boundary_ok models on benchmark items TSV.")
    parser.add_argument("--items-tsv", required=True)
    parser.add_argument("--label-column", default="boundary_ok_eval")
    parser.add_argument("--root", default="", help="Project root for reading source_file spans (needed for rule_md_span_v1)")
    parser.add_argument("--output-task-eval-tsv", required=True)
    parser.add_argument("--output-error-slices-tsv", required=True)
    args = parser.parse_args()

    items = read_tsv(Path(args.items_tsv).resolve())
    if not items:
        raise SystemExit("Empty items TSV")

    root = Path(args.root).resolve() if args.root else None

    all_eval = []
    all_slices = []
    for mid in ["baseline_inline_formula_id", "rule_md_span_v1"]:
        ev, sl = eval_model(items, args.label_column, mid, root)
        all_eval.extend(ev)
        all_slices.extend(sl)

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
        all_eval,
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
        all_slices,
    )

    print(f"Wrote: {Path(args.output_task_eval_tsv).resolve()} ({len(all_eval)} rows)")
    print(f"Wrote: {Path(args.output_error_slices_tsv).resolve()} ({len(all_slices)} rows)")


if __name__ == "__main__":
    main()
