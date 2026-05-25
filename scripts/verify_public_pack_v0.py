#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_PATHS = [
    "docs/DATA_MANIFEST.tsv",
    "docs/FIGURE_PROVENANCE.tsv",
    "docs/STATISTICAL_DECISION_RULES.md",
    "docs/RIGHTS_AND_RELEASE_PLAN.md",
    "data/benchmarks/manifest.tsv",
    "results/benchmarks/split_audit.tsv",
    "results/benchmarks/task_eval_models.tsv",
    "results/benchmarks/boundary_silver_eval.tsv",
    "results/benchmarks/boundary_challenge_summary.tsv",
    "results/error_analysis/error_slices_models.tsv",
    "results/error_analysis/boundary_silver_error_slices.tsv",
    "results/benchmarks/field_value_eval.tsv",
    "results/manuscript/table6_boundary_silver_eval_all.tsv",
    "results/manuscript/table7_boundary_challenge_summary.tsv",
    "plots/p1/fig1_source_registry.pdf",
    "plots/p1/fig2_noise_and_audits.pdf",
    "plots/p1/fig3_pipeline_diagram.pdf",
    "plots/p1/fig4_benchmark_composition.pdf",
    "plots/p1/fig5_baselines_and_robustness.pdf",
]


FORBIDDEN_PATHS = [
    "cidian",
    "openspec",
    "annotation",
    "docs/submissions",
    "docs/manuscript",
    "conductor",
]

FORBIDDEN_FILES = [
    # Reconstructable / phrase-level text exports (keep out of derived-only public pack).
    "data/normalized/composition_items_v0.jsonl",
    "data/normalized/alias_links_v0.tsv",
    "data/benchmarks/field_hardcase_gold_v1.tsv",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a derived-only public reproducibility pack.")
    parser.add_argument("--root", default=".", help="Repo root (default: .)")
    args = parser.parse_args()

    root = Path(args.root).resolve()

    for p in FORBIDDEN_PATHS:
        if (root / p).exists():
            raise SystemExit(f"FAIL: forbidden path present: {p}")

    for rel in FORBIDDEN_FILES:
        if (root / rel).exists():
            raise SystemExit(f"FAIL: forbidden file present: {rel}")

    missing = []
    for rel in REQUIRED_PATHS:
        if not (root / rel).is_file():
            missing.append(rel)
    if missing:
        raise SystemExit("FAIL: missing required files:\n" + "\n".join(missing))

    print("OK: public pack verification passed")


if __name__ == "__main__":
    main()
