#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


TARGET_FIELDS = ["组成", "用法", "功用", "主治"]

FIELD_KEY_MAP = {
    "组成": "composition_raw",
    "用法": "usage_raw",
    "功用": "efficacy_raw",
    "主治": "indication_raw",
}

# Strict: only headings at start of line, no markdown '#', no leading whitespace.
FIELD_STRICT_RE = re.compile(r"(?m)^【(?P<field>[^】]+)】")
# Relaxed: allow whitespace and optional markdown heading marker; headings may appear mid-line in OCR output.
FIELD_RELAXED_RE = re.compile(r"【(?P<field>[^】]+)】")


def split_for_source_file(source_file: str) -> tuple[str, int]:
    h = hashlib.sha1(source_file.encode("utf-8")).hexdigest()
    bucket = int(h, 16) % 100
    if bucket < 70:
        return "train", bucket
    if bucket < 85:
        return "dev", bucket
    return "test", bucket


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def normalize_heading_variants(text: str) -> str:
    # Normalize OCR bracket variants in headings: 【主治〗 / 【功用》 / 【宜忌] etc.
    text = re.sub(r"【(?P<f>[^】》〗〕\]」』]{1,20})(?P<c>[】》〗〕\]」』])", r"【\g<f>】", text)
    text = re.sub(
        r"【(?P<f>异名|组成|用法|功用|主治|宜忌|加减|方论选录|临床报道|现代研究|备考)[厂」』]",
        r"【\g<f>】",
        text,
    )
    return text


def strip_html_simple(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def parse_fields(text: str, mode: str) -> dict[str, str]:
    """
    Return {field_key: value_str} for TARGET_FIELDS only.
    mode:
      - strict: headings must appear at line start
      - relaxed: headings can appear anywhere (OCR glues headings mid-line)
    """
    if not text:
        return {}

    t = normalize_heading_variants(text)
    if "<html" in t or "</table>" in t:
        t = strip_html_simple(t)

    rx = FIELD_STRICT_RE if mode == "strict" else FIELD_RELAXED_RE
    matches = list(rx.finditer(t))
    if not matches:
        return {}

    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        fname = (m.group("field") or "").strip()
        if fname not in TARGET_FIELDS:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(t)
        v = t[start:end].strip()
        if v.endswith("【"):
            v = v[:-1].rstrip()
        key = FIELD_KEY_MAP.get(fname)
        if key and v:
            out[key] = v
    return out


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
    return p, r, f1


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate field-value extraction robustness via strict vs relaxed parsing.")
    parser.add_argument("--structured-jsonl", required=True, help="data/structured/formulas_v14.jsonl")
    parser.add_argument("--output-eval-tsv", required=True, help="results/benchmarks/field_value_eval.tsv")
    parser.add_argument("--output-slices-tsv", required=True, help="results/error_analysis/field_value_error_slices.tsv")
    parser.add_argument(
        "--output-item-outcomes-tsv",
        default="",
        help="Optional public-safe per-record outcomes without field text or extracted values.",
    )
    args = parser.parse_args()

    stats = defaultdict(lambda: Counter())  # (model, split, field) -> counts
    slice_stats = defaultdict(lambda: Counter())  # (model, split, noise, field) -> counts

    item_handle = None
    item_writer = None
    if args.output_item_outcomes_tsv:
        item_path = Path(args.output_item_outcomes_tsv).resolve()
        item_path.parent.mkdir(parents=True, exist_ok=True)
        item_handle = item_path.open("w", encoding="utf-8", newline="")
        item_fields = [
            "record_id",
            "split",
            "doc_type",
            "noise_flags",
            "field",
            "relaxed_reference_present",
            "strict_prediction_present",
            "strict_exact_match_to_relaxed",
            "strict_outcome",
        ]
        item_writer = csv.DictWriter(item_handle, fieldnames=item_fields, delimiter="\t")
        item_writer.writeheader()

    for rec in iter_jsonl(Path(args.structured_jsonl).resolve()):
        dt = (rec.get("doc_type") or "").strip()
        if dt not in {"FORMULA_ENTRY_FULL", "FORMULA_ENTRY_NOISY"}:
            continue

        raw = (rec.get("raw_text") or "").strip()
        src = (rec.get("source_file") or "").strip()
        split, _ = split_for_source_file(src)
        noise = "|".join((rec.get("noise_flags") or [])) if isinstance(rec.get("noise_flags"), list) else (rec.get("noise_flags") or "")
        noise = (noise or "").strip() or "(none)"

        truth = parse_fields(raw, "relaxed")  # truth definition for this proxy task
        strict = parse_fields(raw, "strict")

        if item_writer is not None:
            for fname in TARGET_FIELDS:
                key = FIELD_KEY_MAP[fname]
                relaxed_value = norm_ws(truth.get(key, ""))
                strict_value = norm_ws(strict.get(key, ""))
                if relaxed_value and strict_value == relaxed_value:
                    outcome = "tp"
                elif not relaxed_value and strict_value:
                    outcome = "fp"
                elif relaxed_value:
                    outcome = "fn"
                else:
                    outcome = "tn"
                item_writer.writerow(
                    {
                        "record_id": (rec.get("record_id") or "").strip(),
                        "split": split,
                        "doc_type": dt,
                        "noise_flags": noise,
                        "field": fname,
                        "relaxed_reference_present": "1" if relaxed_value else "0",
                        "strict_prediction_present": "1" if strict_value else "0",
                        "strict_exact_match_to_relaxed": "1" if relaxed_value and strict_value == relaxed_value else "0",
                        "strict_outcome": outcome,
                    }
                )

        models = [
            ("field_value_strict_heading_v0", strict),
            ("field_value_relaxed_heading_v0", truth),  # sanity baseline
        ]

        for model_id, pred in models:
            for fname in TARGET_FIELDS:
                key = FIELD_KEY_MAP[fname]
                y = norm_ws(truth.get(key, ""))
                yhat = norm_ws(pred.get(key, ""))

                k = (model_id, split, fname)
                c = stats[k]
                c["n"] += 1
                if y:
                    c["n_true"] += 1
                if yhat:
                    c["n_pred"] += 1
                if y and yhat and (yhat == y):
                    c["tp"] += 1
                if (not y) and yhat:
                    c["fp"] += 1
                if y and (not yhat or yhat != y):
                    c["fn"] += 1

                sk = (model_id, split, noise, fname)
                sc = slice_stats[sk]
                sc["n"] += 1
                if y:
                    sc["n_true"] += 1
                if yhat:
                    sc["n_pred"] += 1
                if y and yhat and (yhat == y):
                    sc["tp"] += 1
                if (not y) and yhat:
                    sc["fp"] += 1
                if y and (not yhat or yhat != y):
                    sc["fn"] += 1

    out_rows = []
    for model_id in ["field_value_strict_heading_v0", "field_value_relaxed_heading_v0"]:
        for split in ["train", "dev", "test", "all"]:
            for fname in TARGET_FIELDS:
                if split == "all":
                    tp = fp = fn = n = n_true = n_pred = 0
                    for s in ["train", "dev", "test"]:
                        c = stats.get((model_id, s, fname), Counter())
                        tp += c.get("tp", 0)
                        fp += c.get("fp", 0)
                        fn += c.get("fn", 0)
                        n += c.get("n", 0)
                        n_true += c.get("n_true", 0)
                        n_pred += c.get("n_pred", 0)
                else:
                    c = stats.get((model_id, split, fname), Counter())
                    tp, fp, fn = c.get("tp", 0), c.get("fp", 0), c.get("fn", 0)
                    n, n_true, n_pred = c.get("n", 0), c.get("n_true", 0), c.get("n_pred", 0)
                if n == 0:
                    continue
                p, r, f1 = prf(tp, fp, fn)
                out_rows.append(
                    {
                        "task_id": "field_extraction_value",
                        "model_id": model_id,
                        "split": split,
                        "field": fname,
                        "n_items": str(n),
                        "n_true": str(n_true),
                        "n_pred": str(n_pred),
                        "precision": f"{p:.4f}",
                        "recall": f"{r:.4f}",
                        "f1": f"{f1:.4f}",
                        "tp": str(tp),
                        "fp": str(fp),
                        "fn": str(fn),
                        "notes": "truth=relaxed_heading_value_parse on raw_text; exact match after whitespace normalization",
                    }
                )

    slice_rows = []
    for (mid, split, noise, fname), c in sorted(slice_stats.items(), key=lambda kv: (-kv[1]["n"], kv[0][0], kv[0][1], kv[0][2], kv[0][3])):
        n = c.get("n", 0)
        if n <= 0:
            continue
        tp, fp, fn = c.get("tp", 0), c.get("fp", 0), c.get("fn", 0)
        p, r, f1 = prf(tp, fp, fn)
        slice_rows.append(
            {
                "task_id": "field_extraction_value",
                "model_id": mid,
                "split": split,
                "field": fname,
                "slice_key": "noise_flags",
                "slice_value": noise,
                "n_items": str(n),
                "n_true": str(c.get("n_true", 0)),
                "n_pred": str(c.get("n_pred", 0)),
                "precision": f"{p:.4f}",
                "recall": f"{r:.4f}",
                "f1": f"{f1:.4f}",
                "tp": str(tp),
                "fp": str(fp),
                "fn": str(fn),
            }
        )

    write_tsv(
        Path(args.output_eval_tsv).resolve(),
        [
            "task_id",
            "model_id",
            "split",
            "field",
            "n_items",
            "n_true",
            "n_pred",
            "precision",
            "recall",
            "f1",
            "tp",
            "fp",
            "fn",
            "notes",
        ],
        out_rows,
    )
    write_tsv(
        Path(args.output_slices_tsv).resolve(),
        [
            "task_id",
            "model_id",
            "split",
            "field",
            "slice_key",
            "slice_value",
            "n_items",
            "n_true",
            "n_pred",
            "precision",
            "recall",
            "f1",
            "tp",
            "fp",
            "fn",
        ],
        slice_rows,
    )
    if item_handle is not None:
        item_handle.close()

    print(f"Wrote: {Path(args.output_eval_tsv).resolve()} ({len(out_rows)} rows)")
    print(f"Wrote: {Path(args.output_slices_tsv).resolve()} ({len(slice_rows)} rows)")
    if args.output_item_outcomes_tsv:
        print(f"Wrote: {Path(args.output_item_outcomes_tsv).resolve()} (public-safe per-record outcomes)")


if __name__ == "__main__":
    main()
