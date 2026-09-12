#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from evaluate_boundary_baselines_v2 import (
    MODEL_LABELS,
    binary_metrics,
    bootstrap_intervals,
    holm_adjust,
    read_tsv,
    write_tsv,
)


def label_to_int(value: str) -> int:
    if value == "no":
        return 1
    if value == "yes":
        return 0
    raise ValueError(f"Unexpected boundary label: {value!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute held-out boundary statistics from public predictions.")
    parser.add_argument("--predictions-tsv", required=True)
    parser.add_argument("--output-summary-tsv", required=True)
    parser.add_argument("--output-comparisons-tsv", required=True)
    parser.add_argument("--bootstrap-iterations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260825)
    args = parser.parse_args()

    rows = read_tsv(Path(args.predictions_tsv).resolve())
    by_model: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
    for row in rows:
        by_model.setdefault(row["model_id"], []).append(row)
    if not by_model:
        raise SystemExit("No prediction rows found.")

    reference_ids: list[str] | None = None
    test_y: np.ndarray | None = None
    predictions: OrderedDict[str, np.ndarray] = OrderedDict()
    for model_id, model_rows in by_model.items():
        item_ids = [row["item_id"] for row in model_rows]
        labels = np.array([label_to_int(row["gold_boundary_ok"]) for row in model_rows])
        model_predictions = np.array([label_to_int(row["predicted_boundary_ok"]) for row in model_rows])
        if reference_ids is None:
            reference_ids = item_ids
            test_y = labels
        elif item_ids != reference_ids or not np.array_equal(labels, test_y):
            raise SystemExit(f"Item order or gold labels differ for model {model_id}.")
        predictions[model_id] = model_predictions

    assert test_y is not None
    summary_rows: list[dict[str, object]] = []
    for model_offset, (model_id, model_predictions) in enumerate(predictions.items()):
        metrics = binary_metrics(test_y, model_predictions)
        intervals = bootstrap_intervals(
            test_y,
            model_predictions,
            args.seed + model_offset,
            args.bootstrap_iterations,
        )
        summary_rows.append(
            {
                "model_id": model_id,
                "model_label": MODEL_LABELS.get(model_id, model_id),
                "split": "test",
                "n": metrics["n"],
                "accuracy": f"{metrics['accuracy']:.4f}",
                "accuracy_ci95": f"{intervals['accuracy'][0]:.4f}-{intervals['accuracy'][1]:.4f}",
                "precision_boundary_error": f"{metrics['precision']:.4f}",
                "precision_ci95": f"{intervals['precision'][0]:.4f}-{intervals['precision'][1]:.4f}",
                "recall_boundary_error": f"{metrics['recall']:.4f}",
                "recall_ci95": f"{intervals['recall'][0]:.4f}-{intervals['recall'][1]:.4f}",
                "f1_boundary_error": f"{metrics['f1']:.4f}",
                "f1_ci95": f"{intervals['f1'][0]:.4f}-{intervals['f1'][1]:.4f}",
                "tp": metrics["tp"],
                "fp": metrics["fp"],
                "fn": metrics["fn"],
                "tn": metrics["tn"],
            }
        )

    comparison_rows: list[dict[str, object]] = []
    p_values: list[float] = []
    model_ids = list(predictions)
    for left_index in range(len(model_ids)):
        for right_index in range(left_index + 1, len(model_ids)):
            left_id = model_ids[left_index]
            right_id = model_ids[right_index]
            left_correct = predictions[left_id] == test_y
            right_correct = predictions[right_id] == test_y
            left_only = int(np.sum(left_correct & ~right_correct))
            right_only = int(np.sum(~left_correct & right_correct))
            discordant = left_only + right_only
            p_value = float(binomtest(min(left_only, right_only), discordant, 0.5).pvalue) if discordant else 1.0
            p_values.append(p_value)
            comparison_rows.append(
                {
                    "model_a": left_id,
                    "model_b": right_id,
                    "a_correct_b_wrong": left_only,
                    "a_wrong_b_correct": right_only,
                    "mcnemar_exact_p": f"{p_value:.6g}",
                }
            )
    for row, adjusted_p in zip(comparison_rows, holm_adjust(p_values)):
        row["holm_adjusted_p"] = f"{adjusted_p:.6g}"

    write_tsv(
        Path(args.output_summary_tsv).resolve(),
        summary_rows,
        [
            "model_id",
            "model_label",
            "split",
            "n",
            "accuracy",
            "accuracy_ci95",
            "precision_boundary_error",
            "precision_ci95",
            "recall_boundary_error",
            "recall_ci95",
            "f1_boundary_error",
            "f1_ci95",
            "tp",
            "fp",
            "fn",
            "tn",
        ],
    )
    write_tsv(
        Path(args.output_comparisons_tsv).resolve(),
        comparison_rows,
        [
            "model_a",
            "model_b",
            "a_correct_b_wrong",
            "a_wrong_b_correct",
            "mcnemar_exact_p",
            "holm_adjusted_p",
        ],
    )


if __name__ == "__main__":
    main()
