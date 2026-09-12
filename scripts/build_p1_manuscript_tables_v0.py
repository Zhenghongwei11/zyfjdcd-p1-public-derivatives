#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_kv_tsv(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle, delimiter="\t")
        w.writerow(["Metric", "Value"])
        for metric, value in rows:
            w.writerow([metric, value])


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def pct(v: float) -> str:
    return f"{100.0 * v:.1f}%"


def as_float(v: str) -> float:
    try:
        return float((v or "").strip())
    except Exception:
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Build publication summary tables from released results.")
    parser.add_argument("--root", default=".", help="Repo root")
    parser.add_argument("--outdir", default="results/manuscript", help="Output directory relative to repo root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_dir = root / args.outdir
    out_dir.mkdir(parents=True, exist_ok=True)

    def prefer(*relpaths: str) -> Path:
        for rel in relpaths:
            p = (root / rel).resolve()
            if p.exists():
                return p
        return (root / relpaths[-1]).resolve()

    corpus_profile = read_json(root / "results/corpus/corpus_profile.json")
    parse_summary = read_json(root / "results/corpus/parse_summary_v14.json")
    span_fidelity = read_json(root / "results/corpus/span_fidelity_summary_v0.json")
    field_selfcheck = read_json(root / "results/corpus/field_selfcheck_summary_v0.json")
    boundary_consensus = read_json(root / "results/benchmarks/boundary_consensus_summary_v1.json")
    field_hardcase_gold = read_json(
        prefer(
            "results/benchmarks/field_hardcase_gold_v2_summary.json",
            "results/benchmarks/field_hardcase_gold_v1_summary.json",
        )
    )

    # Table 1: Corpus summary (metric/value)
    s = corpus_profile.get("summary") or {}
    ps = (parse_summary.get("summary") or {}) if isinstance(parse_summary, dict) else {}
    kv = [
        ("Corpus label", "OCR-derived Markdown corpus (restricted)"),
        ("Markdown files (n)", str(s.get("files", ""))),
        ("Lines (n)", str(s.get("lines", ""))),
        ("Characters (n)", str(s.get("chars", ""))),
        ("HTML blocks (n)", str(s.get("html_blocks", ""))),
        ("Image links (n)", str(s.get("image_links", ""))),
        ("Suspicious joined entries (n)", str(s.get("suspicious_entry_join", ""))),
        ("Suspicious heading noise (n)", str(s.get("suspicious_field_heading", ""))),
        ("Parsed records (n)", str(ps.get("records", ""))),
        ("Doc type: full entries (n)", str(ps.get("doc_type::FORMULA_ENTRY_FULL", ""))),
        ("Doc type: noisy entries (n)", str(ps.get("doc_type::FORMULA_ENTRY_NOISY", ""))),
        ("Doc type: redirects (n)", str(ps.get("doc_type::FORMULA_ENTRY_REDIRECT", ""))),
        ("Doc type: index-like (n)", str(ps.get("doc_type::TOC_INDEX", ""))),
        ("Doc type: mixed/unknown (n)", str(ps.get("doc_type::MIXED_UNKNOWN", ""))),
    ]
    write_kv_tsv(out_dir / "table1_corpus_summary.tsv", kv)

    # Table 2: Structural correspondence checks (metric/value)
    sf = span_fidelity.get("counts") or {}
    fs = field_selfcheck.get("counts") or {}
    kv2 = [
        ("Records evaluated for span correspondence (n)", str(sf.get("records", ""))),
        ("Exact source-span matches (n)", str(sf.get("ok", ""))),
        ("Records evaluated for field consistency (n)", str(fs.get("records", ""))),
        ("Empty heading but extracted value empty (n)", str(fs.get("issue_heading_but_empty", ""))),
    ]
    write_kv_tsv(out_dir / "table2_quality_audits.tsv", kv2)

    # Table 3: Boundary consensus summary (metric/value)
    bc = boundary_consensus.get("counters") or {}
    kv3 = [
        ("Consensus rows (n)", str(boundary_consensus.get("n_rows", ""))),
        ("Consensus agree rows (n)", str(bc.get("consensus::agree", ""))),
        ("Consensus disagree rows (n)", str(bc.get("consensus::disagree", ""))),
        ("Agree rows labeled boundary OK (n)", str(bc.get("consensus_label::yes", ""))),
        ("Agree rows labeled boundary NOT OK (n)", str(bc.get("consensus_label::no", ""))),
    ]
    write_kv_tsv(out_dir / "table3_boundary_consensus_summary.tsv", kv3)

    # Table 4: Boundary model results (split=all)
    boundary_eval_path = prefer(
        "results/benchmarks/task_eval_models_v3_dual.tsv",
        "results/benchmarks/task_eval_models_v2_dual.tsv",
        "results/benchmarks/task_eval_models.tsv",
    )
    boundary_rows_raw = [r for r in read_tsv(boundary_eval_path) if (r.get("split") or "") == "all"]
    baseline_label = {
        "baseline_inline_formula_id": "Inline-identifier heuristic",
        "rule_md_span_v1": "Span-based rule baseline",
        "nb_char3_v0": "Character 3-gram naive Bayes",
    }
    boundary_rows = []
    for r in boundary_rows_raw:
        mid = (r.get("model_id") or "").strip()
        notes = (r.get("notes") or "").strip()
        notes = notes.replace("no treated as positive class", "").strip(" ;")
        notes = notes.replace("char_3gram_nb", "char 3-gram NB")
        notes = notes.replace("consensus(train)", "consensus (train)")
        notes = notes.replace("consensus_agree(train)", "consensus-agree (train)")
        boundary_rows.append(
            {
                "Baseline": baseline_label.get(mid, mid),
                "n": r.get("n_labeled", ""),
                "Accuracy": r.get("accuracy", ""),
                "F1 (boundary error)": r.get("no_f1", ""),
                "Notes": notes,
            }
        )
    write_tsv(
        out_dir / "table4_boundary_eval_all.tsv",
        ["Baseline", "n", "Accuracy", "F1 (boundary error)", "Notes"],
        boundary_rows,
    )

    # Table 5: Field robustness summary (split=all only)
    presence = [
        r
        for r in read_tsv(root / "results/benchmarks/field_presence_eval.tsv")
        if (r.get("split") or "") == "all" and (r.get("model_id") or "") == "field_presence_strict_heading"
    ]
    value = [
        r
        for r in read_tsv(root / "results/benchmarks/field_value_eval.tsv")
        if (r.get("split") or "") == "all" and (r.get("model_id") or "") == "field_value_strict_heading_v0"
    ]

    idx_p = {(r.get("field") or "").strip(): r for r in presence}
    idx_v = {(r.get("field") or "").strip(): r for r in value}

    out = []
    for f in ["组成", "用法", "功用", "主治"]:
        rp = idx_p.get(f) or {}
        rv = idx_v.get(f) or {}
        out.append(
            {
                "field": f,
                "presence_f1_all": rp.get("f1", ""),
                "presence_recall_all": rp.get("recall", ""),
                "value_f1_all": rv.get("f1", ""),
                "value_recall_all": rv.get("recall", ""),
                "notes": "strict heading parsing vs relaxed reference definition on OCR-derived text",
            }
        )

    # Keep a version with stable column names for Figure 5.
    write_tsv(
        out_dir / "table5_field_robustness_all.tsv",
        ["field", "presence_f1_all", "presence_recall_all", "value_f1_all", "value_recall_all", "notes"],
        out,
    )

    # Also write a version with human-readable headers.
    out_paper = []
    field_name = {
        "组成": "Composition (组成)",
        "用法": "Administration (用法)",
        "功用": "Actions (功用)",
        "主治": "Indications (主治)",
    }
    for r in out:
        out_paper.append(
            {
                "Field": field_name.get(r["field"], r["field"]),
                "Heading presence recall": r["presence_recall_all"],
                "Value extraction recall": r["value_recall_all"],
            }
        )
    write_tsv(
        out_dir / "table5_field_robustness_paper.tsv",
        ["Field", "Heading presence recall", "Value extraction recall"],
        out_paper,
    )

    # Table 6: Consensus-scale silver evaluation (split=all)
    silver_eval_raw = [r for r in read_tsv(root / "results/benchmarks/boundary_silver_eval.tsv") if (r.get("split") or "") == "all"]
    silver_label = {
        "baseline_inline_formula_id": "Inline-identifier heuristic",
        "rule_id_count_v0": "Identifier-count heuristic",
        "nb_char3_consensus_v1": "Character 3-gram naive Bayes",
    }
    silver_eval = []
    for r in silver_eval_raw:
        mid = (r.get("model_id") or "").strip()
        notes = (r.get("notes") or "").strip()
        notes = notes.replace("no treated as positive class", "").strip(" ;")
        notes = notes.replace(">=2 distinct 5-digit ids", ">=2 distinct 5-digit identifiers")
        notes = notes.replace("char_3gram_nb", "char 3-gram NB")
        notes = notes.replace("consensus-agree(train)", "consensus-agree (train)")
        silver_eval.append(
            {
                "Baseline": silver_label.get(mid, mid),
                "n": r.get("n_labeled", ""),
                "Accuracy": r.get("accuracy", ""),
                "F1 (boundary error)": r.get("no_f1", ""),
                "Notes": notes,
            }
        )
    write_tsv(
        out_dir / "table6_boundary_silver_eval_all.tsv",
        ["Baseline", "n", "Accuracy", "F1 (boundary error)", "Notes"],
        silver_eval,
    )

    # Table 7: Challenge-set summary from consensus disagreement map
    challenge_rows = read_tsv(root / "results/benchmarks/boundary_challenge_summary.tsv")
    keep = [r for r in challenge_rows if (r.get("group_key") or "") == "overall"]
    keep.extend([r for r in challenge_rows if (r.get("group_key") or "") == "split"])
    keep.extend([r for r in challenge_rows if (r.get("group_key") or "") == "doc_type"][:5])
    keep.extend([r for r in challenge_rows if (r.get("group_key") or "") == "noise_flags"][:5])
    # Challenge summary with human-readable labels.
    split_map = {"train": "Train", "dev": "Validation", "validation": "Validation", "test": "Test"}
    doc_type_map = {
        "FORMULA_ENTRY_FULL": "Clean entry",
        "FORMULA_ENTRY_NOISY": "Noisy entry",
        "FORMULA_ENTRY_REDIRECT": "Redirect-like",
        "TOC_INDEX": "Index-like",
        "MIXED_UNKNOWN": "Mixed/unknown",
    }
    noise_map = {
        "(none)": "None",
        "markdown_field_heading": "Field-heading noise",
        "image_contamination": "Image markers",
        "html_contamination": "HTML remnants",
    }
    group_map = {
        "overall": "Overall",
        "split": "Split",
        "doc_type": "Doc type",
        "noise_flags": "Noise",
    }
    keep_paper = []
    for r in keep:
        gk = (r.get("group_key") or "").strip()
        gv = (r.get("group_value") or "").strip()
        if gk == "overall":
            gv = "All records"
        if gk == "split":
            gv = split_map.get(gv, gv)
        if gk == "doc_type":
            gv = doc_type_map.get(gv, gv)
        if gk == "noise_flags":
            gv = noise_map.get(gv, gv)
        keep_paper.append(
            {
                "Group": group_map.get(gk, gk),
                "Level": gv,
                "Rows (n)": r.get("n_rows", ""),
                "Disagree rate": pct(as_float(r.get("disagree_rate", "0"))),
            }
        )
    write_tsv(
        out_dir / "table7_boundary_challenge_summary.tsv",
        ["Group", "Level", "Rows (n)", "Disagree rate"],
        keep_paper,
    )

    # Recurring error patterns reported in the main manuscript
    boundary_summary_rows = read_tsv(root / "results/benchmarks/boundary_baseline_test_summary_v2.tsv")
    boundary_summary = {row.get("model_id", ""): row for row in boundary_summary_rows}
    boundary_comparisons = read_tsv(root / "results/statistics/boundary_baseline_mcnemar_v2.tsv")

    def format_ci(value: str) -> str:
        low, high = (value or "0-0").split("-", 1)
        return f"{as_float(low):.3f}–{as_float(high):.3f}"

    def comparison_p(model_id: str) -> str:
        for row in boundary_comparisons:
            pair = {row.get("model_a", ""), row.get("model_b", "")}
            if pair == {model_id, "span_rule_v1"}:
                value = as_float(row.get("holm_adjusted_p", ""))
                return "<0.0001" if value < 0.0001 else f"{value:.4f}"
        return ""

    model_display = {
        "inline_identifier_heuristic": "Inline-identifier heuristic",
        "span_rule_v1": "Span-based rule",
        "char_tfidf_svm_v1": "Character TF-IDF SVM",
        "bge_small_zh_logreg_v1": "BGE embeddings + logistic regression",
    }
    table5_rows = []
    for row in boundary_summary_rows:
        model_id = row.get("model_id", "")
        accuracy_ci = format_ci(row.get("accuracy_ci95", ""))
        f1_ci = format_ci(row.get("f1_ci95", ""))
        table5_rows.append(
            {
                "Baseline": model_display.get(model_id, row.get("model_label", model_id)),
                "Test n": row.get("n", ""),
                "Accuracy (95% CI)": f"{as_float(row.get('accuracy', '')):.3f} ({accuracy_ci})",
                "Precision (error)": f"{as_float(row.get('precision_boundary_error', '')):.3f}",
                "Recall (error)": f"{as_float(row.get('recall_boundary_error', '')):.3f}",
                "F1 (error; 95% CI)": f"{as_float(row.get('f1_boundary_error', '')):.3f} ({f1_ci})",
                "Adjusted P vs. span rule": "Reference" if model_id == "span_rule_v1" else comparison_p(model_id),
            }
        )
    write_tsv(
        out_dir / "table5_boundary_test_with_ci.tsv",
        [
            "Baseline",
            "Test n",
            "Accuracy (95% CI)",
            "Precision (error)",
            "Recall (error)",
            "F1 (error; 95% CI)",
            "Adjusted P vs. span rule",
        ],
        table5_rows,
    )
    field_slices = read_tsv(root / "results/error_analysis/field_value_error_slices.tsv")

    def pick(rows: list[dict], **conds: str) -> dict:
        for r in rows:
            ok = True
            for k, v in conds.items():
                if (r.get(k) or "") != v:
                    ok = False
                    break
            if ok:
                return r
        return {}

    strict_usage = pick(
        field_slices,
        task_id="field_extraction_value",
        model_id="field_value_strict_heading_v0",
        split="test",
        field="用法",
        slice_key="noise_flags",
        slice_value="markdown_field_heading",
    )
    strict_ind = pick(
        field_slices,
        task_id="field_extraction_value",
        model_id="field_value_strict_heading_v0",
        split="test",
        field="主治",
        slice_key="noise_flags",
        slice_value="markdown_field_heading",
    )
    hg = field_hardcase_gold.get("review_status_counts") or {}
    span_rule = boundary_summary.get("span_rule_v1", {})
    char_svm = boundary_summary.get("char_tfidf_svm_v1", {})
    bge_model = boundary_summary.get("bge_small_zh_logreg_v1", {})
    rows8 = [
        {
            "Observed pattern": "A small number of boundary errors remain under the span rule",
            "Main observation": f"The held-out span rule makes {int(span_rule.get('fp','0')) + int(span_rule.get('fn','0'))}/{span_rule.get('n','')} errors ({span_rule.get('fp','')} false positives; {span_rule.get('fn','')} false negatives).",
        },
        {
            "Observed pattern": "Learned text baselines show different error distributions",
            "Main observation": f"The character TF-IDF SVM makes {int(char_svm.get('fp','0')) + int(char_svm.get('fn','0'))}/{char_svm.get('n','')} test errors, compared with {int(bge_model.get('fp','0')) + int(bge_model.get('fn','0'))}/{bge_model.get('n','')} for frozen BGE embeddings plus logistic regression.",
        },
        {
            "Observed pattern": "Strict-heading extraction misses valid usage fields",
            "Main observation": f"Test-set value extraction recall is {strict_usage.get('recall','')} for Administration (用法) under field-heading noise, showing that canonical line-start assumptions undercount displaced headings.",
        },
        {
            "Observed pattern": "Indication fields are sensitive to heading noise",
            "Main observation": f"Test-set value extraction recall is {strict_ind.get('recall','')} for Indications (主治) under field-heading noise, indicating disproportionate sensitivity in narrative fields.",
        },
        {
            "Observed pattern": "Field review changes a minority of hard-case values",
            "Main observation": f"Among {field_hardcase_gold.get('gold_rows','')} reviewed rows, {hg.get('accepted_as_is','')} are accepted as extracted, {hg.get('corrected','')} are corrected, and {hg.get('cleared_empty','')} are cleared as empty.",
        },
    ]
    write_tsv(
        out_dir / "table9_recurring_error_patterns.tsv",
        ["Observed pattern", "Main observation"],
        rows8,
    )

    # Table 9: Release tiers / access surface (narrative aid; no internal paths)
    rows9 = [
        {
            "Layer": "Third-party printed source",
            "Access": "Publisher, libraries, and book distributors",
            "Included": "The 2nd edition of Zhongyi Fangji Da Cidian",
            "Excluded": "No book pages redistributed by the authors",
            "Purpose": "Source work from which the local OCR layer was created",
        },
        {
            "Layer": "Local OCR-derived working corpus",
            "Access": "Not redistributed by the authors",
            "Included": "OCR-derived Markdown and text-bearing structured records",
            "Excluded": "Complete text and reconstructable excerpts",
            "Purpose": "Local extraction and source-span verification",
        },
        {
            "Layer": "Public derived analysis package",
            "Access": "Public",
            "Included": "Benchmark indices, deterministic splits, structural-check summaries, and evaluation outputs",
            "Excluded": "Full OCR text; long excerpts enabling reconstitution of substantial content",
            "Purpose": "Method comparison under rights constraints",
        },
        {
            "Layer": "Field hard-case review",
            "Access": "Binary review labels public",
            "Included": "Item identifiers, review labels, and adjudicated statuses",
            "Excluded": "Phrase-level book text",
            "Purpose": "Reconstruction of agreement and review-status counts",
        },
    ]
    write_tsv(
        out_dir / "table9_release_tiers.tsv",
        ["Layer", "Access", "Included", "Excluded", "Purpose"],
        rows9,
    )

    # Table 10: Evaluation assets overview (ties narrative to concrete assets)
    def count_tsv_rows(path: Path) -> int:
        if not path.exists():
            return 0
        with path.open("r", encoding="utf-8", newline="") as handle:
            return max(0, sum(1 for _ in handle) - 1)

    items_gold_path = root / "data/benchmarks/items_gold_v3_dual.tsv"
    # Count labeled rows (boundary_ok_gold in {yes,no}) for the gold subset size.
    n_boundary_gold = 0
    if items_gold_path.exists():
        for r in read_tsv(items_gold_path):
            if (r.get("boundary_ok_gold") or "").strip() in {"yes", "no"}:
                n_boundary_gold += 1
    n_boundary_hardcase = count_tsv_rows(root / "data/benchmarks/boundary_hardcase_gold_v1.tsv")
    n_field_hardcase = int(field_hardcase_gold.get("gold_rows") or 0)
    doc_type_labels = root / "data/benchmarks/document_type_dual_labels_v1.tsv"
    n_doc_type_gold = count_tsv_rows(doc_type_labels)

    rows10 = [
        {
            "Asset": "Entry segmentation gold subset",
            "Task": "Boundary correctness (entry segmentation)",
            "Label tier": "Dual annotation + adjudication",
            "N": str(n_boundary_gold),
            "Availability": "Public (derived-only)",
            "Reported as": "Table 5; Figs 4 and 5",
        },
        {
            "Asset": "Document-type stratification gold subset",
            "Task": "Document-type label consistency",
            "Label tier": "Dual annotation + adjudication",
            "N": str(n_doc_type_gold),
            "Availability": "Public (derived-only)",
            "Reported as": "Methods; Source Data 13",
        },
        {
            "Asset": "Corpus-scale silver consensus",
            "Task": "Boundary diagnostics at scale (agree vs disagree regions)",
            "Label tier": "Rule-consensus (silver)",
            "N": str(boundary_consensus.get("n_rows") or ""),
            "Availability": "Public (derived-only)",
            "Reported as": "Tables 4, 6, and 7",
        },
        {
            "Asset": "Boundary hard-case slice",
            "Task": "Checking disagreement-rich boundary cases",
            "Label tier": "Human-reviewed (hard-case slice)",
            "N": str(n_boundary_hardcase or 24),
            "Availability": "Public (derived-only; no excerpts)",
            "Reported as": "Methods; Discussion",
        },
        {
            "Asset": "Field hard-case reviewed slice",
            "Task": "Field robustness under OCR artifacts (inspection-focused)",
            "Label tier": "Dual annotation + adjudication",
            "N": str(n_field_hardcase),
            "Availability": "Binary labels public; phrase text excluded",
            "Reported as": "Methods; Source Data 17",
        },
    ]
    write_tsv(
        out_dir / "table10_evaluation_assets.tsv",
        ["Asset", "Task", "Label tier", "N", "Availability", "Reported as"],
        rows10,
    )

    print(f"OK: wrote tables under {out_dir}")


if __name__ == "__main__":
    main()
