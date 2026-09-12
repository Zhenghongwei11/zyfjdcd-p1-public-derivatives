#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


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


def sha1_text(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit that structured raw_text matches the exact source span by source_char_start/end."
    )
    parser.add_argument("--input-jsonl", required=True, help="data/structured/formulas_v14.jsonl")
    parser.add_argument("--root", required=True, help="Project root for resolving source_file paths")
    parser.add_argument("--output-summary-json", required=True, help="results/corpus/span_fidelity_summary_v0.json")
    parser.add_argument("--output-issues-tsv", required=True, help="results/corpus/span_fidelity_issues_v0.tsv")
    parser.add_argument("--max-issues", type=int, default=2000)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    in_path = Path(args.input_jsonl).resolve()

    cache: dict[str, str] = {}
    issues = []
    ctr = Counter()

    for rec in iter_jsonl(in_path):
        ctr["records"] += 1
        rid = (rec.get("record_id") or "").strip()
        src = (rec.get("source_file") or "").strip()
        if not src:
            ctr["missing_source_file"] += 1
            continue
        try:
            cs = int(rec.get("source_char_start") or 0)
            ce = int(rec.get("source_char_end") or 0)
        except Exception:
            ctr["bad_char_offsets"] += 1
            continue
        if cs < 0 or ce < 0 or ce < cs:
            ctr["bad_char_offsets"] += 1
            continue

        p = Path(src)
        if not p.is_absolute():
            p = (root / p).resolve()
        key = str(p)
        if key not in cache:
            try:
                cache[key] = p.read_text(encoding="utf-8")
            except Exception:
                cache[key] = ""
        text = cache[key]
        if not text:
            ctr["missing_source_text"] += 1
            continue

        span = text[cs:ce].strip()
        raw = (rec.get("raw_text") or "").strip()
        if span == raw:
            ctr["ok"] += 1
            continue

        ctr["mismatch"] += 1
        if len(issues) < args.max_issues:
            issues.append(
                {
                    "record_id": rid,
                    "source_file": src,
                    "source_char_start": str(cs),
                    "source_char_end": str(ce),
                    "span_sha1": sha1_text(span),
                    "raw_sha1": sha1_text(raw),
                    "span_len": str(len(span)),
                    "raw_len": str(len(raw)),
                    "doc_type": (rec.get("doc_type") or "").strip(),
                }
            )

    out_summary = Path(args.output_summary_json).resolve()
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "input": str(args.input_jsonl),
        "root": str(args.root),
        "counts": dict(ctr),
        "issues_truncated": len(issues) >= args.max_issues,
        "max_issues": args.max_issues,
    }
    out_summary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    out_issues = Path(args.output_issues_tsv).resolve()
    write_tsv(
        out_issues,
        [
            "record_id",
            "source_file",
            "source_char_start",
            "source_char_end",
            "span_sha1",
            "raw_sha1",
            "span_len",
            "raw_len",
            "doc_type",
        ],
        issues,
    )

    print(f"Wrote: {out_summary}")
    print(f"Wrote: {out_issues} ({len(issues)} issues; mismatches={ctr.get('mismatch',0)})")


if __name__ == "__main__":
    main()

