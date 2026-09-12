#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import random
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binomtest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.svm import LinearSVC

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_boundary_models_v1 import baseline_inline_formula_id, load_md_span, rule_md_span_v1


MODEL_LABELS = {
    "inline_identifier_heuristic": "Inline-identifier heuristic",
    "span_rule_v1": "Span-based rule",
    "char_tfidf_svm_v1": "Character TF-IDF linear SVM",
    "bge_small_zh_logreg_v1": "Chinese transformer embedding + logistic regression",
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def normalize_label(value: str) -> int | None:
    value = (value or "").strip().lower()
    if value == "no":
        return 1
    if value == "yes":
        return 0
    return None


def prepare_text(text: str, max_chars: int = 1800) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n[SEGMENT_MIDDLE_OMITTED]\n" + text[-half:]


def load_items(root: Path, items_path: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for row in read_tsv(items_path):
        label = normalize_label(row.get("boundary_ok_gold", ""))
        if label is None:
            continue
        start = int(row.get("source_line_start", "0") or 0)
        end = int(row.get("source_line_end", "0") or 0)
        text = load_md_span(root, row.get("source_file", ""), start, end)
        items.append(
            {
                "item_id": row.get("item_id", ""),
                "split": row.get("split", ""),
                "noise_flags": row.get("noise_flags", ""),
                "label": label,
                "raw_text": text,
                "model_text": prepare_text(text),
            }
        )
    return items


def binary_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float | int]:
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", pos_label=1, zero_division=0
    )
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
    }


def bootstrap_intervals(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    seed: int,
    iterations: int,
) -> dict[str, tuple[float, float]]:
    rng = np.random.default_rng(seed)
    values = {key: [] for key in ("accuracy", "precision", "recall", "f1")}
    n = len(y_true)
    for _ in range(iterations):
        idx = rng.integers(0, n, size=n)
        metrics = binary_metrics(y_true[idx], y_pred[idx])
        for key in values:
            values[key].append(float(metrics[key]))
    return {
        key: (float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975)))
        for key, vals in values.items()
    }


def select_svm(train_texts: list[str], train_y: np.ndarray, dev_texts: list[str], dev_y: np.ndarray):
    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 5),
        min_df=1,
        max_features=100000,
        sublinear_tf=True,
    )
    train_x = vectorizer.fit_transform(train_texts)
    dev_x = vectorizer.transform(dev_texts)
    candidates: list[tuple[float, float, float, LinearSVC]] = []
    for c_value in (0.1, 0.3, 1.0, 3.0):
        model = LinearSVC(C=c_value, class_weight="balanced", random_state=20260825)
        model.fit(train_x, train_y)
        pred = model.predict(dev_x)
        metrics = binary_metrics(dev_y, pred)
        candidates.append((float(metrics["f1"]), float(metrics["accuracy"]), -c_value, model))
    _, _, negative_c, _ = max(candidates, key=lambda item: item[:3])
    return vectorizer, -negative_c


def transformer_embeddings(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "Transformer baseline dependencies are missing. Run with torch and transformers installed."
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    if torch.backends.mps.is_available():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    model.to(device)
    model.eval()

    all_embeddings: list[np.ndarray] = []
    with torch.inference_mode():
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encoded = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            output = model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).expand(output.size()).float()
            pooled = (output * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            all_embeddings.append(pooled.float().cpu().numpy())
    embeddings = np.asarray(np.vstack(all_embeddings), dtype=np.float64)
    if not np.isfinite(embeddings).all():
        raise SystemExit("Transformer embeddings contain non-finite values.")
    return embeddings


def predict_logreg(model: LogisticRegression, features: np.ndarray) -> np.ndarray:
    scores = np.einsum("ij,j->i", features, model.coef_[0]) + model.intercept_[0]
    return np.where(scores > 0, model.classes_[1], model.classes_[0])


def select_logreg(train_x: np.ndarray, train_y: np.ndarray, dev_x: np.ndarray, dev_y: np.ndarray) -> float:
    candidates: list[tuple[float, float, float]] = []
    for c_value in (0.1, 0.3, 1.0, 3.0, 10.0):
        model = LogisticRegression(
            C=c_value,
            class_weight="balanced",
            max_iter=5000,
            random_state=20260825,
            solver="liblinear",
        )
        model.fit(train_x, train_y)
        metrics = binary_metrics(dev_y, predict_logreg(model, dev_x))
        candidates.append((float(metrics["f1"]), float(metrics["accuracy"]), -c_value))
    _, _, negative_c = max(candidates)
    return -negative_c


def holm_adjust(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=lambda index: p_values[index])
    adjusted = [1.0] * len(p_values)
    running = 0.0
    total = len(p_values)
    for rank, index in enumerate(order):
        value = min(1.0, (total - rank) * p_values[index])
        running = max(running, value)
        adjusted[index] = running
    return adjusted


def main() -> None:
    parser = argparse.ArgumentParser(description="Leakage-controlled entry-boundary baseline evaluation.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--items-tsv", default="data/benchmarks/items_gold_v3_dual.tsv")
    parser.add_argument("--transformer-model", default="BAAI/bge-small-zh-v1.5")
    parser.add_argument("--transformer-model-id", default="BAAI/bge-small-zh-v1.5")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--bootstrap-iterations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--output-predictions-tsv", required=True)
    parser.add_argument("--output-summary-tsv", required=True)
    parser.add_argument("--output-comparisons-tsv", required=True)
    parser.add_argument("--output-metadata-json", required=True)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    root = Path(args.root).resolve()
    items = load_items(root, (root / args.items_tsv).resolve())
    split_items = {split: [item for item in items if item["split"] == split] for split in ("train", "dev", "test")}
    if any(not split_items[split] for split in split_items):
        raise SystemExit("The benchmark must contain non-empty train, dev, and test partitions.")

    train_texts = [str(item["model_text"]) for item in split_items["train"]]
    dev_texts = [str(item["model_text"]) for item in split_items["dev"]]
    test_texts = [str(item["model_text"]) for item in split_items["test"]]
    train_y = np.array([int(item["label"]) for item in split_items["train"]])
    dev_y = np.array([int(item["label"]) for item in split_items["dev"]])
    test_y = np.array([int(item["label"]) for item in split_items["test"]])

    predictions: dict[str, np.ndarray] = {}
    predictions["inline_identifier_heuristic"] = np.array(
        [1 if baseline_inline_formula_id(str(item["noise_flags"])) == "no" else 0 for item in split_items["test"]]
    )
    predictions["span_rule_v1"] = np.array(
        [1 if rule_md_span_v1(str(item["raw_text"])) == "no" else 0 for item in split_items["test"]]
    )

    svm_vectorizer, svm_c = select_svm(train_texts, train_y, dev_texts, dev_y)
    combined_texts = train_texts + dev_texts
    combined_y = np.concatenate([train_y, dev_y])
    combined_x = svm_vectorizer.fit_transform(combined_texts)
    test_x = svm_vectorizer.transform(test_texts)
    svm_model = LinearSVC(C=svm_c, class_weight="balanced", random_state=args.seed)
    svm_model.fit(combined_x, combined_y)
    predictions["char_tfidf_svm_v1"] = svm_model.predict(test_x)

    all_texts = train_texts + dev_texts + test_texts
    embeddings = transformer_embeddings(all_texts, args.transformer_model, args.batch_size)
    train_end = len(train_texts)
    dev_end = train_end + len(dev_texts)
    transformer_c = select_logreg(embeddings[:train_end], train_y, embeddings[train_end:dev_end], dev_y)
    transformer_model = LogisticRegression(
        C=transformer_c,
        class_weight="balanced",
        max_iter=5000,
        random_state=args.seed,
        solver="liblinear",
    )
    transformer_model.fit(embeddings[:dev_end], combined_y)
    predictions["bge_small_zh_logreg_v1"] = predict_logreg(transformer_model, embeddings[dev_end:])

    prediction_rows: list[dict[str, object]] = []
    for index, item in enumerate(split_items["test"]):
        for model_id, model_predictions in predictions.items():
            prediction_rows.append(
                {
                    "item_id": item["item_id"],
                    "split": "test",
                    "noise_flags": item["noise_flags"],
                    "gold_boundary_ok": "no" if test_y[index] == 1 else "yes",
                    "predicted_boundary_ok": "no" if model_predictions[index] == 1 else "yes",
                    "model_id": model_id,
                }
            )

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
                "model_label": MODEL_LABELS[model_id],
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

    model_ids = list(predictions)
    raw_comparisons: list[dict[str, object]] = []
    p_values: list[float] = []
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
            raw_comparisons.append(
                {
                    "model_a": left_id,
                    "model_b": right_id,
                    "a_correct_b_wrong": left_only,
                    "a_wrong_b_correct": right_only,
                    "mcnemar_exact_p": f"{p_value:.6g}",
                }
            )
    adjusted = holm_adjust(p_values)
    for row, adjusted_p in zip(raw_comparisons, adjusted):
        row["holm_adjusted_p"] = f"{adjusted_p:.6g}"

    write_tsv(
        Path(args.output_predictions_tsv).resolve(),
        prediction_rows,
        ["item_id", "split", "noise_flags", "gold_boundary_ok", "predicted_boundary_ok", "model_id"],
    )
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
        raw_comparisons,
        [
            "model_a",
            "model_b",
            "a_correct_b_wrong",
            "a_wrong_b_correct",
            "mcnemar_exact_p",
            "holm_adjusted_p",
        ],
    )
    metadata = {
        "seed": args.seed,
        "bootstrap_iterations": args.bootstrap_iterations,
        "positive_class": "boundary error (boundary_ok=no)",
        "split_policy": "file-level predefined train/dev/test; hyperparameters selected on dev; final metrics reported on test",
        "transformer_model": args.transformer_model_id,
        "transformer_classifier": "frozen mean-pooled embeddings with class-balanced liblinear logistic regression",
        "svm_c_selected": svm_c,
        "transformer_c_selected": transformer_c,
        "n_train": len(train_y),
        "n_dev": len(dev_y),
        "n_test": len(test_y),
        "software_versions": {
            package: importlib.metadata.version(package)
            for package in ("numpy", "scipy", "scikit-learn", "torch", "transformers")
        },
    }
    metadata_path = Path(args.output_metadata_json).resolve()
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
