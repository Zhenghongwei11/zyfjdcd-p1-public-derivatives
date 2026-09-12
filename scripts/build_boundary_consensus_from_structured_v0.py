#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ID5_RE = re.compile(r"(?<!\d)\d{5}(?!\d)")
EMBEDDED_START_RE = re.compile(r"(?<!\d)(?P<formula_id>\d{5})(?=[\u4e00-\u9fff])")

TOP_HEADINGS = ("【组成】", "【异名】")
CORE_HEADINGS = ("【组成】", "【用法】", "【功用】", "【主治】")


def split_for_source_file(source_file: str) -> tuple[str, int]:
    h = hashlib.sha1(source_file.encode("utf-8")).hexdigest()
    bucket = int(h, 16) % 100
    if bucket < 70:
        return "train", bucket
    if bucket < 85:
        return "dev", bucket
    return "test", bucket


def norm(v: str) -> str:
    v = (v or "").strip().lower()
    if v in {"y", "yes", "true", "1"}:
        return "yes"
    if v in {"n", "no", "false", "0"}:
        return "no"
    return v


def noise_flags_to_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return "|".join(str(x).strip() for x in v if str(x).strip())
    return str(v).strip()


def baseline_inline_formula_id(noise_flags: str) -> str:
    flags = set((noise_flags or "").split("|")) if noise_flags else set()
    return "no" if "inline_formula_id" in flags else "yes"


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

    for m in EMBEDDED_START_RE.finditer(span):
        if m.start() == 0:
            continue
        window = span[m.start() : m.start() + 400]
        if looks_like_new_entry(window):
            return "no"
    return "yes"

def label_id_count_v0(span: str) -> str:
    if not span:
        return "no"
    uniq = sorted(set(ID5_RE.findall(span)))
    return "no" if len(uniq) >= 2 else "yes"

def label_embedded_start_v0(span: str) -> str:
    if not span:
        return "no"
    for m in EMBEDDED_START_RE.finditer(span):
        if m.start() > 0:
            return "no"
    return "yes"


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a consensus-labeled boundary dataset from structured JSONL (two independent rule labelers)."
    )
    parser.add_argument("--structured-jsonl", required=True, help="data/structured/formulas_v14.jsonl")
    parser.add_argument("--output-tsv", required=True, help="data/benchmarks/boundary_consensus_v1.tsv")
    parser.add_argument("--summary-json", required=True, help="results/benchmarks/boundary_consensus_summary_v1.json")
    args = parser.parse_args()

    structured = Path(args.structured_jsonl).resolve()

    rows = []
    ctr = Counter()

    for rec in iter_jsonl(structured):
        rid = (rec.get("record_id") or "").strip()
        if not rid:
            continue

        src = (rec.get("source_file") or "").strip()
        sline = rec.get("source_line_start")
        eline = rec.get("source_line_end")

        split, bucket = split_for_source_file(src)
        noise = noise_flags_to_str(rec.get("noise_flags"))

        # Two labelers, designed to create:
        # - an agreement set (high precision) and
        # - a disagreement set (challenge cases)
        # A: embedded-start detector (very simple)
        # B: embedded-start detector + window cues (more conservative)
        a = label_embedded_start_v0((rec.get("raw_text") or "").strip())
        b = rule_md_span_v1((rec.get("raw_text") or "").strip())

        consensus_status = "agree" if a == b else "disagree"
        consensus = a if consensus_status == "agree" else ""

        dt = (rec.get("doc_type") or "").strip()

        rows.append(
            {
                "item_id": rid,
                "source_file": src,
                "source_line_start": str(sline or ""),
                "source_line_end": str(eline or ""),
                "doc_type": dt,
                "noise_flags": noise,
                "split": split,
                "split_bucket": str(bucket),
                "label_a": a,
                "label_b": b,
                "consensus_status": consensus_status,
                "boundary_ok_consensus": consensus,
            }
        )

        ctr["records"] += 1
        ctr[f"doc_type::{dt or '(none)'}"] += 1
        ctr[f"consensus::{consensus_status}"] += 1
        if consensus_status == "agree":
            ctr[f"consensus_label::{consensus}"] += 1

    out_tsv = Path(args.output_tsv).resolve()
    write_tsv(
        out_tsv,
        [
            "item_id",
            "source_file",
            "source_line_start",
            "source_line_end",
            "doc_type",
            "noise_flags",
            "split",
            "split_bucket",
            "label_a",
            "label_b",
            "consensus_status",
            "boundary_ok_consensus",
        ],
        rows,
    )

    summary = {
        "input": str(args.structured_jsonl),
        "n_rows": len(rows),
        "counters": dict(ctr),
    }
    out_summary = Path(args.summary_json).resolve()
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote: {out_tsv} ({len(rows)} rows)")
    print(f"Wrote: {out_summary}")


if __name__ == "__main__":
    main()
