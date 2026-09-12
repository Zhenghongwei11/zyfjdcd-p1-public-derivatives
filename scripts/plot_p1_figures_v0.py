#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

COLORS = {
    "blue": "#1f77b4",
    "orange": "#ff7f0e",
    "red": "#d62728",
    "gray": "#8c8c8c",
    "light_gray": "#c7c7c7",
    "ink": "#333333",
}


def read_tsv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_outdir(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)


def save_fig(fig, outdir: Path, stem: str) -> None:
    pdf = outdir / f"{stem}.pdf"
    png = outdir / f"{stem}.png"
    fig.savefig(pdf, bbox_inches="tight")
    # IEEE graphics guidance commonly expects >=300 dpi for color/grayscale raster images.
    fig.savefig(png, dpi=300, bbox_inches="tight")


def set_style() -> None:
    plt.rcParams.update(
        {
            # Publication-first defaults (titles belong in captions, not in-figure).
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 10,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.linewidth": 0.8,
            "grid.linewidth": 0.6,
            "figure.dpi": 120,
            "savefig.dpi": 220,
        }
    )


def ascii_source_label(source_file: str) -> str:
    """
    Keep figure text ASCII-only to avoid non-portable font dependencies.
    Example: "第12册3.md" -> "vol12_03.md"
    """
    s = Path((source_file or "").strip()).name
    try:
        s.encode("ascii")
        return s
    except Exception:
        pass

    import re

    m = re.match(r"^第(\d+)册(\d+)\.md$", s)
    if m:
        vol = int(m.group(1))
        part = int(m.group(2))
        return f"vol{vol:02d}_{part:02d}.md"
    m = re.match(r"^第(\d+)册\.md$", s)
    if m:
        vol = int(m.group(1))
        return f"vol{vol:02d}_00.md"
    return "source.md"


def short_source_id(source_file: str) -> str:
    """
    Short display ID without internal paths.
    Example: "第12册3.md" or "vol12_03.md" -> "V12-03"
    """
    s = ascii_source_label(source_file)
    import re

    m = re.match(r"^vol(\d{2})_(\d{2})\.md$", s)
    if m:
        return f"V{m.group(1)}-{m.group(2)}"
    return "SRC"


def volume_id_from_source(source_file: str) -> str:
    """
    Volume ID for aggregation.
    Example: "第12册3.md" or "vol12_03.md" -> "V12"
    """
    s = ascii_source_label(source_file)
    import re

    m = re.match(r"^vol(\d{2})_\d{2}\.md$", s)
    if m:
        return f"V{m.group(1)}"
    return "V??"


def human_noise_flag(flag: str) -> str:
    f = (flag or "").strip() or "(none)"
    mapping = {
        "(none)": "None",
        "markdown_field_heading": "Field-heading noise",
        "inline_formula_id": "Inline identifier",
        "markdown_field_heading|inline_formula_id": "Heading + identifier",
        "image_contamination": "Image markers",
        "html_contamination": "HTML remnants",
    }
    return mapping.get(f, f.replace("_", " "))


def ascii_field_label(field: str) -> str:
    # Paper figures should be English/ASCII-first for portability.
    mapping = {
        "组成": "composition",
        "用法": "administration",
        "功用": "actions",
        "主治": "indications",
    }
    f = (field or "").strip()
    if f in mapping:
        return mapping[f]
    try:
        f.encode("ascii")
        return f
    except Exception:
        return "field"


def fig2_volume_composition(root: Path, outdir: Path) -> None:
    rows = read_tsv(root / "results/corpus/source_registry.tsv")
    # Aggregate to volume level for readability.
    def as_int(v: str) -> int:
        try:
            return int((v or "0").strip())
        except Exception:
            return 0

    by_vol: dict[str, dict[str, int]] = {}
    for r in rows:
        v = volume_id_from_source(r.get("source_file", ""))
        bucket = by_vol.setdefault(v, {"full": 0, "noisy": 0, "redir": 0, "other": 0, "parsed": 0})
        bucket["full"] += as_int(r.get("full_records", "0"))
        bucket["noisy"] += as_int(r.get("noisy_records", "0"))
        bucket["redir"] += as_int(r.get("redirect_records", "0"))
        bucket["other"] += as_int(r.get("mixed_records", "0"))
        bucket["parsed"] += as_int(r.get("parsed_records", "0"))

    # Drop non-volume rows from the volume comparison.
    if "V??" in by_vol and len(by_vol) > 1:
        by_vol.pop("V??", None)

    vols = sorted(by_vol.keys())
    full = [by_vol[v]["full"] for v in vols]
    noisy = [by_vol[v]["noisy"] for v in vols]
    redir = [by_vol[v]["redir"] for v in vols]
    other = [by_vol[v]["other"] for v in vols]
    totals = [max(1, f + n + r + o) for f, n, r, o in zip(full, noisy, redir, other)]

    # Use a 100% stacked bar to compare composition across volumes.
    full_p = [f / t for f, t in zip(full, totals)]
    noisy_p = [n / t for n, t in zip(noisy, totals)]
    redir_p = [r / t for r, t in zip(redir, totals)]
    other_p = [o / t for o, t in zip(other, totals)]

    x = list(range(len(vols)))
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.bar(x, full_p, label="Clean entries", color=COLORS["blue"], alpha=0.9)
    ax.bar(x, noisy_p, bottom=full_p, label="Noisy entries", color=COLORS["orange"], alpha=0.9)
    bottom2 = [a + b for a, b in zip(full_p, noisy_p)]
    ax.bar(x, redir_p, bottom=bottom2, label="Redirect-like", color=COLORS["red"], alpha=0.85)
    bottom3 = [a + b for a, b in zip(bottom2, redir_p)]
    ax.bar(x, other_p, bottom=bottom3, label="Index/Mixed/Other", color=COLORS["light_gray"], alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels(vols)
    ax.set_ylabel("Share of records")
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.grid(axis="y", alpha=0.22)
    ax.legend(ncols=2, frameon=True, loc="upper right")
    save_fig(fig, outdir, "fig2_volume_composition")
    plt.close(fig)


def fig3_heterogeneity_distributions(root: Path, outdir: Path) -> None:
    anomalies = read_tsv(root / "results/corpus/source_anomalies.tsv")

    def as_int(v: str) -> int:
        try:
            return int((v or "0").strip())
        except Exception:
            return 0

    # Show file-level distributions by volume.
    vols = [f"V{n:02d}" for n in range(1, 10)]
    join_by_vol = {v: [] for v in vols}
    head_by_vol = {v: [] for v in vols}
    for r in anomalies:
        v = volume_id_from_source(r.get("source_file", ""))
        if v not in join_by_vol:
            continue
        join_by_vol[v].append(as_int(r.get("suspicious_entry_join", "0")))
        head_by_vol[v].append(as_int(r.get("suspicious_field_heading", "0")))

    join_data = [join_by_vol[v] for v in vols]
    head_data = [head_by_vol[v] for v in vols]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.0, 3.6), sharex=True)

    def violin(ax, data, ylabel, panel):
        vp = ax.violinplot(data, showmeans=False, showmedians=True, showextrema=False)
        for body in vp["bodies"]:
            body.set_facecolor(COLORS["blue"])
            body.set_edgecolor(COLORS["blue"])
            body.set_alpha(0.25)
        vp["cmedians"].set_color(COLORS["blue"])
        vp["cmedians"].set_linewidth(1.2)
        ax.set_xticks(list(range(1, len(vols) + 1)))
        ax.set_xticklabels(vols, rotation=0)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.22)
        ax.text(0.01, 0.96, panel, transform=ax.transAxes, fontsize=10, fontweight="bold", va="top", ha="left")

    violin(ax1, join_data, "Joined-entry signals (per file)", "(a)")
    violin(ax2, head_data, "Field-heading noise signals (per file)", "(b)")

    save_fig(fig, outdir, "fig3_heterogeneity_distributions")
    plt.close(fig)


def fig4_benchmark_composition(root: Path, outdir: Path) -> None:
    items_path = root / "data/benchmarks/items_gold_v3_dual.tsv"
    if not items_path.exists():
        items_path = root / "data/benchmarks/items_gold_v2.tsv"
    items = read_tsv(items_path)

    def norm(v: str) -> str:
        v = (v or "").strip().lower()
        if v in {"yes", "y", "true", "1"}:
            return "yes"
        if v in {"no", "n", "false", "0"}:
            return "no"
        return ""

    split_map = {"train": "train", "dev": "validation", "validation": "validation", "test": "test"}
    splits = ["train", "validation", "test"]
    split_labels = {"train": "Train", "validation": "Validation", "test": "Test"}
    ok_counts = {s: 0 for s in splits}
    error_counts = {s: 0 for s in splits}
    doc_type_counts = {s: Counter() for s in splits}
    noise_counts = {s: Counter() for s in splits}

    for r in items:
        y = norm(r.get("boundary_ok_gold") or "")
        if y not in {"yes", "no"}:
            continue
        s_raw = (r.get("split") or "").strip()
        s = split_map.get(s_raw, "")
        if s not in ok_counts:
            continue
        if y == "yes":
            ok_counts[s] += 1
        else:
            error_counts[s] += 1
        dt = (r.get("doc_type_label") or "").strip() or "(none)"
        doc_type_counts[s][dt] += 1
        nf = (r.get("noise_flags") or "").strip() or "(none)"
        noise_counts[s][nf] += 1

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6), gridspec_kw={"width_ratios": [1.1, 1.9]})
    ax1, ax2 = axes
    ax1.text(0.01, 0.96, "(a)", transform=ax1.transAxes, fontsize=10, fontweight="bold", va="top", ha="left")

    # Gold-only split composition by boundary label.
    y = list(range(len(splits)))[::-1]
    ok = [ok_counts[s] for s in splits]
    err = [error_counts[s] for s in splits]
    totals = [a + b for a, b in zip(ok, err)]
    ax1.barh(y, ok, color=COLORS["blue"], alpha=0.88, label="Boundary OK")
    ax1.barh(y, err, left=ok, color=COLORS["red"], alpha=0.82, label="Boundary NOT OK")
    for yi, total in zip(y, totals):
        ax1.text(total + 2, yi, f"n={total}", va="center", fontsize=9, color="#444444")
    ax1.set_yticks(y)
    ax1.set_yticklabels([split_labels.get(s, s) for s in splits])
    ax1.set_xlabel("Adjudicated boundary items")
    ax1.set_xlim(0, max(totals) + 10)
    ax1.grid(axis="x", alpha=0.22)
    ax1.legend(frameon=True, loc="lower right", fontsize=8)

    # Top noise flags across splits
    total_noise = Counter()
    for s in splits:
        total_noise.update(noise_counts[s])
    top = [k for k, _ in total_noise.most_common(6)]
    top_labels = [human_noise_flag(k) for k in top]

    # Show the same information as a compact heatmap.
    ax2.text(0.01, 0.96, "(b)", transform=ax2.transAxes, fontsize=10, fontweight="bold", va="top", ha="left")
    mat = [[noise_counts[s].get(k, 0) for s in splits] for k in top]
    im = ax2.imshow(mat, aspect="auto", cmap="Blues")
    ax2.set_yticks(list(range(len(top_labels))))
    ax2.set_yticklabels(top_labels)
    ax2.set_xticks(list(range(len(splits))))
    ax2.set_xticklabels([split_labels.get(s, s) for s in splits])
    ax2.set_title("Top noise indicators (counts)")
    # Increase spacing so y tick labels do not collide with panel (a).
    ax2.tick_params(axis="y", pad=2)

    for i in range(len(top)):
        for j in range(len(splits)):
            v = mat[i][j]
            ax2.text(j, i, str(v), ha="center", va="center", fontsize=9, color="#1a1a1a")

    cbar = fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)
    cbar.ax.set_ylabel("Count", rotation=90)

    # Extra space between panels to avoid label collisions in tight bounding.
    fig.subplots_adjust(wspace=0.55)

    save_fig(fig, outdir, "fig4_benchmark_composition")
    plt.close(fig)


def fig5_baselines_and_field_robustness(root: Path, outdir: Path) -> None:
    # Panel A: held-out boundary performance with leakage-controlled training.
    b_all = read_tsv(root / "results/benchmarks/boundary_baseline_test_summary_v2.tsv")

    # Panel B: field robustness table (already aggregated)
    field_rows = read_tsv(root / "results/manuscript/table5_field_robustness_all.tsv")

    # Panel C: held-out error rates by document type, reconstructed from public predictions.
    predictions = read_tsv(root / "results/benchmarks/boundary_baseline_test_predictions_v2.tsv")
    items_path = root / "data/benchmarks/items_gold_v3_dual.tsv"
    items_by_id = {row["item_id"]: row for row in read_tsv(items_path)}

    def as_int(v: str) -> int:
        try:
            return int((v or "0").strip())
        except Exception:
            return 0

    fig = plt.figure(figsize=(9.2, 8.2), constrained_layout=True)
    gs = fig.add_gridspec(3, 1, height_ratios=[1.1, 1.2, 1.2], hspace=0.30)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0])
    ax3 = fig.add_subplot(gs[2, 0])

    ax1.text(0.01, 0.96, "(a)", transform=ax1.transAxes, fontsize=10, fontweight="bold", va="top", ha="left")
    raw_model_ids = [r.get("model_id") for r in b_all]
    model_label = {
        "inline_identifier_heuristic": "Inline-identifier heuristic",
        "span_rule_v1": "Span-based rule",
        "char_tfidf_svm_v1": "Character TF-IDF SVM",
        "bge_small_zh_logreg_v1": "BGE embeddings + logistic regression",
    }
    compact_model_label = {
        "inline_identifier_heuristic": "Inline heuristic",
        "span_rule_v1": "Span rule",
        "char_tfidf_svm_v1": "Char TF-IDF SVM",
        "bge_small_zh_logreg_v1": "BGE + logistic regression",
    }
    no_f1 = [float(r.get("f1_boundary_error") or 0.0) for r in b_all]
    labeled = [(m or "", model_label.get(m or "", m or ""), f) for m, f in zip(raw_model_ids, no_f1)]
    order = ["inline_identifier_heuristic", "char_tfidf_svm_v1", "bge_small_zh_logreg_v1", "span_rule_v1"]
    labeled.sort(key=lambda t: order.index(t[0]) if t[0] in order else 99)
    model_ids = [t[1] for t in labeled]
    no_f1 = [t[2] for t in labeled]

    # Lollipop-style performance summary (cleaner than solid bars).
    y = list(range(len(model_ids)))[::-1]
    for yi, f1 in zip(y, no_f1):
        ax1.hlines(yi, 0, f1, color=COLORS["light_gray"], linewidth=3.0, alpha=0.95)
        ax1.plot(f1, yi, "o", color=COLORS["blue"], markersize=7)
        ax1.text(min(1.02, f1 + 0.02), yi, f"{f1:.3f}", va="center", fontsize=9, color="#333333")
    ax1.set_yticks(y)
    ax1.set_yticklabels(model_ids)
    ax1.set_xlim(0, 1.05)
    ax1.set_xlabel("F1 (boundary error = positive)")
    ax1.grid(axis="x", alpha=0.22)

    # Field robustness (recall)
    fields = [ascii_field_label(r["field"]) for r in field_rows]
    pres_recall = [float(r["presence_recall_all"]) for r in field_rows]
    val_recall = [float(r["value_recall_all"]) for r in field_rows]
    ax2.text(0.01, 0.96, "(b)", transform=ax2.transAxes, fontsize=10, fontweight="bold", va="top", ha="left")

    # Dumbbell plot: two recall definitions per field.
    y = list(range(len(fields)))[::-1]
    for yi, pr, vr in zip(y, pres_recall, val_recall):
        ax2.plot([pr, vr], [yi, yi], color=COLORS["light_gray"], linewidth=2.0, alpha=0.95)
        ax2.plot(pr, yi, "o", color=COLORS["orange"], markersize=7, label="Heading presence recall" if yi == y[0] else None)
        ax2.plot(vr, yi, "s", color=COLORS["red"], markersize=6, label="Value extraction recall" if yi == y[0] else None)
    ax2.set_yticks(y)
    ax2.set_yticklabels(fields)
    ax2.set_xlim(0, 1.05)
    ax2.set_xlabel("Recall (strict vs relaxed truth)")
    ax2.grid(axis="x", alpha=0.22)
    ax2.legend(frameon=True, loc="upper right")

    doc_types = [
        "FORMULA_ENTRY_FULL",
        "FORMULA_ENTRY_NOISY",
        "FORMULA_ENTRY_REDIRECT",
        "MIXED_UNKNOWN",
    ]
    doc_labels = {
        "FORMULA_ENTRY_FULL": "Clean entries",
        "FORMULA_ENTRY_NOISY": "Noisy entries",
        "FORMULA_ENTRY_REDIRECT": "Redirect-like",
        "MIXED_UNKNOWN": "Mixed/unknown",
    }
    model_ids = order
    counts = {doc_type: sum(1 for item in items_by_id.values() if item.get("split") == "test" and item.get("doc_type_label") == doc_type) for doc_type in doc_types}
    errors = [[0 for _ in model_ids] for _ in doc_types]
    for row in predictions:
        item = items_by_id.get(row.get("item_id", ""), {})
        doc_type = item.get("doc_type_label", "")
        model_id = row.get("model_id", "")
        if doc_type not in doc_types or model_id not in model_ids:
            continue
        if row.get("gold_boundary_ok") != row.get("predicted_boundary_ok"):
            errors[doc_types.index(doc_type)][model_ids.index(model_id)] += 1
    rates = [
        [errors[row_index][column_index] / max(1, counts[doc_type]) for column_index in range(len(model_ids))]
        for row_index, doc_type in enumerate(doc_types)
    ]

    ax3.text(0.01, 0.96, "(c)", transform=ax3.transAxes, fontsize=10, fontweight="bold", va="top", ha="left")
    im = ax3.imshow(rates, aspect="auto", cmap="OrRd", vmin=0, vmax=max(max(row) for row in rates))
    ax3.set_yticks(range(len(doc_types)))
    ax3.set_yticklabels([f"{doc_labels[doc_type]} (n={counts[doc_type]})" for doc_type in doc_types])
    ax3.set_xticks(range(len(model_ids)))
    ax3.set_xticklabels([compact_model_label[model_id] for model_id in model_ids], rotation=12, ha="right")
    ax3.set_xlabel("Held-out prediction errors by document type")
    for row_index, doc_type in enumerate(doc_types):
        for column_index in range(len(model_ids)):
            ax3.text(
                column_index,
                row_index,
                f"{errors[row_index][column_index]}/{counts[doc_type]}",
                ha="center",
                va="center",
                fontsize=9,
                color="#1a1a1a",
            )
    cbar = fig.colorbar(im, ax=ax3, fraction=0.025, pad=0.02)
    cbar.ax.set_ylabel("Error rate", rotation=90)

    save_fig(fig, outdir, "fig5_baselines_and_robustness")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate P1 paper figures (PDF + PNG) from anchor tables.")
    parser.add_argument("--root", default=".", help="Repo root")
    parser.add_argument("--outdir", default="plots/p1", help="Output directory for figures")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    outdir = (root / args.outdir).resolve()
    ensure_outdir(outdir)
    set_style()

    fig2_volume_composition(root, outdir)
    fig3_heterogeneity_distributions(root, outdir)
    fig4_benchmark_composition(root, outdir)
    fig5_baselines_and_field_robustness(root, outdir)

    print(f"OK: wrote P1 figures to {outdir}")


if __name__ == "__main__":
    main()
