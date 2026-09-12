#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


FIELD_RX = re.compile(r"【(?P<field>异名|组成|用法|功用|主治|宜忌|加减|方论选录|临床报道|现代研究|备考)】")

FIELD_KEY_MAP = {
    "异名": "alias_raw",
    "组成": "composition_raw",
    "用法": "usage_raw",
    "功用": "efficacy_raw",
    "主治": "indication_raw",
    "宜忌": "contraindication_raw",
    "加减": "modification_raw",
    "方论选录": "commentary_raw",
    "临床报道": "clinical_report_raw",
    "现代研究": "modern_research_raw",
    "备考": "notes_raw",
}


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
    # Mirror the parser's normalization for OCR bracket variants.
    text = re.sub(r"【(?P<f>[^】》〗〕\]」』]{1,20})(?P<c>[】》〗〕\]」』])", r"【\g<f>】", text)
    text = re.sub(
        r"【(?P<f>异名|组成|用法|功用|主治|宜忌|加减|方论选录|临床报道|现代研究|备考)[厂」』]",
        r"【\g<f>】",
        text,
    )
    return text


def strip_html_simple(text: str) -> str:
    # Conservative tag stripper for self-checking (do not aim for perfect HTML parsing).
    return re.sub(r"<[^>]+>", "", text)

def norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Self-consistency checks for extracted fields vs raw_text.")
    parser.add_argument("--input-jsonl", required=True, help="data/structured/formulas_v14.jsonl")
    parser.add_argument("--output-summary-json", required=True, help="results/corpus/field_selfcheck_summary_v0.json")
    parser.add_argument("--output-issues-tsv", required=True, help="results/corpus/field_selfcheck_issues_v0.tsv")
    parser.add_argument("--max-issues", type=int, default=2000)
    args = parser.parse_args()

    ctr = Counter()
    issues = []
    by_field = defaultdict(Counter)  # field -> counts

    for rec in iter_jsonl(Path(args.input_jsonl).resolve()):
        ctr["records"] += 1
        rid = (rec.get("record_id") or "").strip()
        raw = (rec.get("raw_text") or "").strip()
        dt = (rec.get("doc_type") or "").strip()

        raw_norm = normalize_heading_variants(raw)
        if "<html" in raw_norm or "</table>" in raw_norm:
            raw_norm = strip_html_simple(raw_norm)

        present = set()
        for m in FIELD_RX.finditer(raw_norm):
            present.add((m.group("field") or "").strip())

        for field_name, key in FIELD_KEY_MAP.items():
            v = (rec.get(key) or "").strip()
            has_heading = field_name in present
            has_value = bool(v)

            if has_heading and not has_value:
                ctr["issue_heading_but_empty"] += 1
                by_field[field_name]["heading_but_empty"] += 1
                if len(issues) < args.max_issues:
                    issues.append(
                        {
                            "record_id": rid,
                            "doc_type": dt,
                            "field": field_name,
                            "issue": "heading_but_empty",
                            "source_file": (rec.get("source_file") or "").strip(),
                            "source_line_start": str(rec.get("source_line_start") or ""),
                            "source_line_end": str(rec.get("source_line_end") or ""),
                        }
                    )

            if (not has_heading) and has_value:
                ctr["issue_value_but_no_heading"] += 1
                by_field[field_name]["value_but_no_heading"] += 1
                if len(issues) < args.max_issues:
                    issues.append(
                        {
                            "record_id": rid,
                            "doc_type": dt,
                            "field": field_name,
                            "issue": "value_but_no_heading",
                            "source_file": (rec.get("source_file") or "").strip(),
                            "source_line_start": str(rec.get("source_line_start") or ""),
                            "source_line_end": str(rec.get("source_line_end") or ""),
                        }
                    )

            if has_value and v not in raw_norm:
                # Tolerate whitespace differences introduced by OCR cleanup / HTML stripping.
                if norm_ws(v) and norm_ws(v) in norm_ws(raw_norm):
                    continue
                # Strong signal of extraction corruption (should be rare).
                ctr["issue_value_not_substring"] += 1
                by_field[field_name]["value_not_substring"] += 1
                if len(issues) < args.max_issues:
                    issues.append(
                        {
                            "record_id": rid,
                            "doc_type": dt,
                            "field": field_name,
                            "issue": "value_not_substring",
                            "source_file": (rec.get("source_file") or "").strip(),
                            "source_line_start": str(rec.get("source_line_start") or ""),
                            "source_line_end": str(rec.get("source_line_end") or ""),
                        }
                    )

    out_summary = Path(args.output_summary_json).resolve()
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "input": str(args.input_jsonl),
        "counts": dict(ctr),
        "by_field": {k: dict(v) for k, v in sorted(by_field.items())},
        "issues_truncated": len(issues) >= args.max_issues,
        "max_issues": args.max_issues,
    }
    out_summary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    write_tsv(
        Path(args.output_issues_tsv).resolve(),
        ["record_id", "doc_type", "field", "issue", "source_file", "source_line_start", "source_line_end"],
        issues,
    )

    print(f"Wrote: {out_summary}")
    print(f"Wrote: {Path(args.output_issues_tsv).resolve()} ({len(issues)} issues)")


if __name__ == "__main__":
    main()
