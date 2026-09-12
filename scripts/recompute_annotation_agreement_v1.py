#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute agreement from item-level paired labels.")
    parser.add_argument("--labels-tsv", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--output-tsv", required=True)
    arguments = parser.parse_args()

    rows = read_tsv(Path(arguments.labels_tsv))
    pairs = [
        ((row.get("annotator_a_label") or "").strip(), (row.get("annotator_b_label") or "").strip())
        for row in rows
    ]
    pairs = [(label_a, label_b) for label_a, label_b in pairs if label_a and label_b]
    if not pairs:
        raise SystemExit("No paired labels found")

    labels = sorted({label for pair in pairs for label in pair})
    count_a = Counter(label_a for label_a, _ in pairs)
    count_b = Counter(label_b for _, label_b in pairs)
    n_joint = len(pairs)
    n_agree = sum(label_a == label_b for label_a, label_b in pairs)
    observed = n_agree / n_joint
    expected = sum((count_a[label] / n_joint) * (count_b[label] / n_joint) for label in labels)
    kappa = (observed - expected) / (1.0 - expected) if expected < 1.0 else 1.0

    output = Path(arguments.output_tsv)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["task_id", "n_joint", "agreement", "cohen_kappa", "n_disagreements"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "task_id": arguments.task_id,
                "n_joint": n_joint,
                "agreement": f"{observed:.4f}",
                "cohen_kappa": f"{kappa:.4f}",
                "n_disagreements": n_joint - n_agree,
            }
        )


if __name__ == "__main__":
    main()
