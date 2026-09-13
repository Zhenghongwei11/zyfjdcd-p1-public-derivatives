#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the labeled entry-boundary benchmark index.")
    parser.add_argument("--input-tsv", required=True)
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--label-column", default="boundary_ok_gold")
    args = parser.parse_args()

    input_path = Path(args.input_tsv).resolve()
    output_path = Path(args.output_tsv).resolve()
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        rows = [
            row
            for row in reader
            if (row.get(args.label_column) or "").strip().lower() in {"yes", "no"}
        ]

    if not fieldnames or args.label_column not in fieldnames:
        raise SystemExit(f"Missing label column: {args.label_column}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote: {output_path} ({len(rows)} labeled rows)")


if __name__ == "__main__":
    main()
