#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


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
    fig.savefig(png, dpi=220, bbox_inches="tight")


def set_style() -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "figure.dpi": 120,
            "savefig.dpi": 220,
        }
    )


def ascii_source_label(source_file: str) -> str:
    """
    Keep figure text ASCII-only to avoid non-portable font dependencies.
    Example: "第12册3.md" -> "vol12_03.md"
    """
    s = (source_file or "").strip()
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
    return "source.md"


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


def fig1_source_registry(root: Path, outdir: Path) -> None:
    rows = read_tsv(root / "results/corpus/source_registry.tsv")
    # Sort by parsed records desc
    def as_int(v: str) -> int:
        try:
            return int((v or "0").strip())
        except Exception:
            return 0

    rows.sort(key=lambda r: -as_int(r.get("parsed_records", "0")))
    labels = [ascii_source_label(r["source_file"]) for r in rows]
    full = [as_int(r.get("full_records", "0")) for r in rows]
    noisy = [as_int(r.get("noisy_records", "0")) for r in rows]
    redir = [as_int(r.get("redirect_records", "0")) for r in rows]
    other = [as_int(r.get("mixed_records", "0")) for r in rows]

    y = list(range(len(rows)))
    fig, ax = plt.subplots(figsize=(9.2, max(6.0, 0.22 * len(rows))))
    ax.barh(y, full, label="Full entries", color="#2E86AB")
    ax.barh(y, noisy, left=full, label="Noisy entries", color="#F6AE2D")
    left2 = [a + b for a, b in zip(full, noisy)]
    ax.barh(y, redir, left=left2, label="Redirect entries", color="#A23E48")
    left3 = [a + b for a, b in zip(left2, redir)]
    ax.barh(y, other, left=left3, label="Index/Mixed/Other", color="#9BAEBC")

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Parsed records (stacked)")
    ax.set_title("Figure 1. File-level parsed record composition")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="lower right", frameon=True)
    save_fig(fig, outdir, "fig1_source_registry")
    plt.close(fig)


def fig2_noise_and_audits(root: Path, outdir: Path) -> None:
    anomalies = read_tsv(root / "results/corpus/source_anomalies.tsv")
    sf = read_json(root / "results/corpus/span_fidelity_summary_v0.json").get("counts") or {}
    fs = read_json(root / "results/corpus/field_selfcheck_summary_v0.json").get("counts") or {}

    def as_int(v: str) -> int:
        try:
            return int((v or "0").strip())
        except Exception:
            return 0

    xs = [as_int(r.get("suspicious_entry_join", "0")) for r in anomalies]
    ys = [as_int(r.get("suspicious_field_heading", "0")) for r in anomalies]
    sizes = [60 + 240 * (as_int(r.get("html_blocks", "0")) + as_int(r.get("image_links", "0"))) for r in anomalies]
    names = [ascii_source_label(r.get("source_file", "")) for r in anomalies]

    fig = plt.figure(figsize=(9.2, 4.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[3.0, 1.2])
    ax = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    ax.scatter(xs, ys, s=sizes, alpha=0.55, color="#2E86AB", edgecolors="none")
    ax.set_xlabel("Suspicious joined-entry signals (per file)")
    ax.set_ylabel("Suspicious field-heading noise signals (per file)")
    ax.set_title("Figure 2. Noise landscape + auditable quality gates")
    ax.grid(alpha=0.25)

    # Label top outliers
    idx = sorted(range(len(xs)), key=lambda i: xs[i] + ys[i], reverse=True)[:6]
    for i in idx:
        ax.annotate(names[i], (xs[i], ys[i]), xytext=(4, 3), textcoords="offset points", fontsize=8)

    ax2.axis("off")
    ax2.text(
        0.0,
        0.95,
        "Audit summary",
        fontsize=11,
        fontweight="bold",
        va="top",
        ha="left",
    )
    ax2.text(
        0.0,
        0.78,
        f"Span fidelity:\n  ok {sf.get('ok','?')} / {sf.get('records','?')}",
        fontsize=10,
        va="top",
        ha="left",
    )
    ax2.text(
        0.0,
        0.58,
        f"Field self-check:\n  empty-heading cases {fs.get('issue_heading_but_empty','?')}",
        fontsize=10,
        va="top",
        ha="left",
    )
    ax2.text(
        0.0,
        0.38,
        "Note: source text is private;\npublic package is derived-only.",
        fontsize=9,
        va="top",
        ha="left",
        color="#555555",
    )

    save_fig(fig, outdir, "fig2_noise_and_audits")
    plt.close(fig)


def fig3_pipeline_diagram(root: Path, outdir: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 3.8))
    ax.axis("off")

    def box(x, y, w, h, text, fc, ec="#333333"):
        b = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.02",
            linewidth=1.1,
            facecolor=fc,
            edgecolor=ec,
        )
        ax.add_patch(b)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=10)

    def arrow(x1, y1, x2, y2):
        a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12, linewidth=1.0, color="#333333")
        ax.add_patch(a)

    ax.set_title("Figure 3. Rights-aware pipeline and release tiers", pad=12)

    # Coordinates in axes fraction
    # Private source
    box(0.02, 0.55, 0.22, 0.28, "T0 Private source\nOCR-derived Markdown\n(cidian/)", fc="#F2F2F2")
    # Structured (private)
    box(0.30, 0.55, 0.24, 0.28, "T2 Structured (private)\nJSONL with spans\n(+ raw_text)", fc="#E8F1F8")
    # Derived (public)
    box(0.60, 0.62, 0.18, 0.21, "T3 Derived (public)\nSchema + audits\n+ benchmarks", fc="#EAF5EA")
    box(0.80, 0.62, 0.18, 0.21, "Public repro repo\n(staged)", fc="#EAF5EA")

    # Evaluation + figures
    box(0.60, 0.20, 0.38, 0.28, "Eval tables + figure provenance\n(results/ + docs/)\n(no full text)", fc="#FFF6E6")

    arrow(0.24, 0.69, 0.30, 0.69)
    arrow(0.54, 0.69, 0.60, 0.72)
    arrow(0.78, 0.72, 0.80, 0.72)
    arrow(0.72, 0.62, 0.72, 0.48)
    ax.text(0.44, 0.86, "scripts/reproduce_one_click.sh", fontsize=9, ha="center", color="#444444")

    save_fig(fig, outdir, "fig3_pipeline_diagram")
    plt.close(fig)


def fig4_benchmark_composition(root: Path, outdir: Path) -> None:
    items = read_tsv(root / "data/benchmarks/items_gold_v2.tsv")

    def norm(v: str) -> str:
        v = (v or "").strip().lower()
        if v in {"yes", "y", "true", "1"}:
            return "yes"
        if v in {"no", "n", "false", "0"}:
            return "no"
        return ""

    splits = ["train", "dev", "test"]
    split_counts = {s: 0 for s in splits}
    labeled_counts = {s: 0 for s in splits}
    doc_type_counts = {s: Counter() for s in splits}
    noise_counts = {s: Counter() for s in splits}

    for r in items:
        s = (r.get("split") or "").strip()
        if s not in split_counts:
            continue
        split_counts[s] += 1
        y = norm(r.get("boundary_ok_gold") or "")
        if y in {"yes", "no"}:
            labeled_counts[s] += 1
        dt = (r.get("doc_type_label") or "").strip() or "(none)"
        doc_type_counts[s][dt] += 1
        nf = (r.get("noise_flags") or "").strip() or "(none)"
        noise_counts[s][nf] += 1

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6), gridspec_kw={"width_ratios": [1.2, 1.8]})
    ax1, ax2 = axes
    ax1.set_title("Figure 4. Benchmark split composition")
    ax1.bar(splits, [split_counts[s] for s in splits], color="#2E86AB", alpha=0.8, label="items")
    ax1.bar(splits, [labeled_counts[s] for s in splits], color="#A23E48", alpha=0.85, label="labeled (boundary)")
    ax1.set_ylabel("Count")
    ax1.legend(frameon=True)
    ax1.grid(axis="y", alpha=0.25)

    # Top noise flags across splits
    total_noise = Counter()
    for s in splits:
        total_noise.update(noise_counts[s])
    top = [k for k, _ in total_noise.most_common(6)]

    xs = range(len(top))
    w = 0.25
    for i, s in enumerate(splits):
        ax2.bar([x + (i - 1) * w for x in xs], [noise_counts[s].get(k, 0) for k in top], width=w, label=s)
    ax2.set_xticks(list(xs))
    ax2.set_xticklabels(top, rotation=25, ha="right")
    ax2.set_title("Top noise flags (by split)")
    ax2.set_ylabel("Count")
    ax2.legend(frameon=True)
    ax2.grid(axis="y", alpha=0.25)

    save_fig(fig, outdir, "fig4_benchmark_composition")
    plt.close(fig)


def fig5_baselines_and_field_robustness(root: Path, outdir: Path) -> None:
    # Panel A: boundary no_f1 (split=all)
    boundary = read_tsv(root / "results/benchmarks/task_eval_models.tsv")
    b_all = [r for r in boundary if (r.get("split") or "") == "all"]
    b_all.sort(key=lambda r: (r.get("task_id") or "", r.get("model_id") or ""))

    # Panel B: field robustness table (already aggregated)
    field_rows = read_tsv(root / "results/manuscript/table5_field_robustness_all.tsv")

    # Panel C: boundary error slices for baseline_inline
    slices = read_tsv(root / "results/error_analysis/error_slices_models.tsv")
    s_base = [r for r in slices if (r.get("model_id") or "") == "baseline_inline_formula_id"]
    # Sort by n_labeled desc, take top 8
    def as_int(v: str) -> int:
        try:
            return int((v or "0").strip())
        except Exception:
            return 0

    s_base.sort(key=lambda r: -as_int(r.get("n_labeled", "0")))
    s_base = s_base[:8]

    fig = plt.figure(figsize=(9.2, 7.4))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.1, 1.2, 1.2])

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0])
    ax3 = fig.add_subplot(gs[2, 0])

    ax1.set_title("Figure 5. Baselines and robustness under OCR noise")
    model_ids = [r.get("model_id") for r in b_all]
    no_f1 = [float(r.get("no_f1") or 0.0) for r in b_all]
    ax1.bar(model_ids, no_f1, color="#2E86AB", alpha=0.85)
    ax1.set_ylabel("no_f1 (split=all)")
    ax1.set_ylim(0, 1.05)
    ax1.grid(axis="y", alpha=0.25)
    ax1.tick_params(axis="x", rotation=20)

    # Field robustness (recall)
    fields = [ascii_field_label(r["field"]) for r in field_rows]
    pres_recall = [float(r["presence_recall_all"]) for r in field_rows]
    val_recall = [float(r["value_recall_all"]) for r in field_rows]
    x = list(range(len(fields)))
    w = 0.35
    ax2.bar([i - w / 2 for i in x], pres_recall, width=w, label="Heading presence recall", color="#F6AE2D", alpha=0.9)
    ax2.bar([i + w / 2 for i in x], val_recall, width=w, label="Value extraction recall", color="#A23E48", alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels(fields)
    ax2.set_ylabel("Recall (strict vs relaxed truth)")
    ax2.set_ylim(0, 1.05)
    ax2.grid(axis="y", alpha=0.25)
    ax2.legend(frameon=True)

    # Error slices for baseline_inline_formula_id
    slice_names = [r.get("slice_value") for r in s_base]
    slice_f1 = [float(r.get("no_f1") or 0.0) for r in s_base]
    slice_n = [as_int(r.get("n_labeled", "0")) for r in s_base]
    ax3.barh(list(range(len(slice_names))), slice_f1, color="#9BAEBC", alpha=0.9)
    ax3.set_yticks(list(range(len(slice_names))))
    ax3.set_yticklabels([f"{n}  {name}" for n, name in zip(slice_n, slice_names)])
    ax3.invert_yaxis()
    ax3.set_xlabel("no_f1 (baseline_inline_formula_id)")
    ax3.set_xlim(0, 1.05)
    ax3.grid(axis="x", alpha=0.25)

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

    fig1_source_registry(root, outdir)
    fig2_noise_and_audits(root, outdir)
    fig3_pipeline_diagram(root, outdir)
    fig4_benchmark_composition(root, outdir)
    fig5_baselines_and_field_robustness(root, outdir)

    print(f"OK: wrote P1 figures to {outdir}")


if __name__ == "__main__":
    main()
