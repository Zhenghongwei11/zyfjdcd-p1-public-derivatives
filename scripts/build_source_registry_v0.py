#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


FORMULA_TYPES = {
    "FORMULA_ENTRY_FULL": "full_records",
    "FORMULA_ENTRY_NOISY": "noisy_records",
    "FORMULA_ENTRY_REDIRECT": "redirect_records",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def coarse_doc_signal(total: int, full: int, noisy: int, redirect: int, mixed: int, html: int, images: int) -> str:
    if total <= 0:
        return "empty"

    # Heuristic: mixed/frontmatter-heavy when most records are non-formula or there is heavy HTML.
    if mixed >= int(0.7 * total) or html >= 50:
        return "mixed_frontmatter_toc_noise"

    suffix = ""
    if html > 0:
        suffix = "_with_html_noise"
    elif images > 0:
        suffix = "_with_media_noise"
    else:
        suffix = "_with_noise" if noisy > 0 else ""

    base = "formula_entry_heavy"
    if (full + noisy + redirect) <= 0:
        base = "nonformula_heavy"
    return base + suffix


def priority_review(html: int, images: int, joined: int, field_heading: int) -> str:
    if html > 0 or images > 0 or joined >= 250 or field_heading >= 500:
        return "yes"
    return "no"


def join_notes(html: int, images: int, joined: int, field_heading: int) -> str:
    notes = []
    if html > 0:
        notes.append("html")
    if images > 0:
        notes.append("image")
    if joined >= 250:
        notes.append("joined_entries")
    if field_heading >= 500:
        notes.append("field_heading_noise")
    return ";".join(notes)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build file-level source registry + anomaly priority table from corpus profile + structured JSONL."
    )
    parser.add_argument("--corpus-profile-json", required=True, help="results/corpus/corpus_profile.json")
    parser.add_argument("--structured-jsonl", required=True, help="data/structured/formulas_v14.jsonl")
    parser.add_argument("--output-source-registry-tsv", required=True, help="results/corpus/source_registry.tsv")
    parser.add_argument("--output-source-anomalies-tsv", required=True, help="results/corpus/source_anomalies.tsv")
    parser.add_argument("--notes", default="file_level_summary_from_record_counts")
    args = parser.parse_args()

    profile = read_json(Path(args.corpus_profile_json).resolve())
    files_profile: dict = profile.get("files") or {}

    per_file_counts = defaultdict(lambda: Counter())
    for rec in iter_jsonl(Path(args.structured_jsonl).resolve()):
        src = (rec.get("source_file") or "").strip()
        name = Path(src).name if src else ""
        if not name:
            continue
        per_file_counts[name]["parsed_records"] += 1
        dt = (rec.get("doc_type") or "").strip()
        if dt in FORMULA_TYPES:
            per_file_counts[name][FORMULA_TYPES[dt]] += 1
        else:
            per_file_counts[name]["mixed_records"] += 1

    # Build source_registry.tsv
    registry_rows = []
    for name in sorted(files_profile.keys()):
        stats = files_profile.get(name) or {}
        c = per_file_counts.get(name, Counter())

        total = int(c.get("parsed_records", 0))
        full = int(c.get("full_records", 0))
        noisy = int(c.get("noisy_records", 0))
        redirect = int(c.get("redirect_records", 0))
        mixed = int(c.get("mixed_records", 0))
        html = int(stats.get("html_blocks", 0) or 0)
        images = int(stats.get("image_links", 0) or 0)

        signal = coarse_doc_signal(total, full, noisy, redirect, mixed, html, images)
        eligibility = "mixed_requires_segment_classification" if signal.startswith("mixed_") else "segment_classification_required"

        registry_rows.append(
            {
                "source_file": name,
                "parsed_records": str(total),
                "full_records": str(full),
                "noisy_records": str(noisy),
                "redirect_records": str(redirect),
                "mixed_records": str(mixed),
                "html_blocks": str(html),
                "image_links": str(images),
                "coarse_doc_signal": signal,
                "eligibility_status": eligibility,
                "needs_segment_review": "yes",
                "notes": args.notes,
            }
        )

    write_tsv(
        Path(args.output_source_registry_tsv).resolve(),
        [
            "source_file",
            "parsed_records",
            "full_records",
            "noisy_records",
            "redirect_records",
            "mixed_records",
            "html_blocks",
            "image_links",
            "coarse_doc_signal",
            "eligibility_status",
            "needs_segment_review",
            "notes",
        ],
        registry_rows,
    )

    # Build source_anomalies.tsv
    anomaly_rows = []
    for name in sorted(files_profile.keys()):
        stats = files_profile.get(name) or {}
        html = int(stats.get("html_blocks", 0) or 0)
        images = int(stats.get("image_links", 0) or 0)
        joined = int(stats.get("suspicious_entry_join", 0) or 0)
        field_heading = int(stats.get("suspicious_field_heading", 0) or 0)
        anomaly_rows.append(
            {
                "source_file": name,
                "lines": str(int(stats.get("lines", 0) or 0)),
                "html_blocks": str(html),
                "image_links": str(images),
                "suspicious_entry_join": str(joined),
                "suspicious_field_heading": str(field_heading),
                "priority_review": priority_review(html, images, joined, field_heading),
                "notes": join_notes(html, images, joined, field_heading),
            }
        )

    # Put highest priority at top, then sort by join/heading noise.
    anomaly_rows.sort(
        key=lambda r: (
            0 if r["priority_review"] == "yes" else 1,
            -int(r["suspicious_entry_join"]),
            -int(r["suspicious_field_heading"]),
            r["source_file"],
        )
    )

    write_tsv(
        Path(args.output_source_anomalies_tsv).resolve(),
        [
            "source_file",
            "lines",
            "html_blocks",
            "image_links",
            "suspicious_entry_join",
            "suspicious_field_heading",
            "priority_review",
            "notes",
        ],
        anomaly_rows,
    )

    print(f"Wrote: {Path(args.output_source_registry_tsv).resolve()} ({len(registry_rows)} rows)")
    print(f"Wrote: {Path(args.output_source_anomalies_tsv).resolve()} ({len(anomaly_rows)} rows)")


if __name__ == "__main__":
    main()
