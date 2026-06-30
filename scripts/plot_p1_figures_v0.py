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
    # Aggregate to volume level for readability (file-level bars are QC/engineering-facing).
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

    # Drop non-volume rows to keep the figure manuscript-facing.
    if "V??" in by_vol and len(by_vol) > 1:
        by_vol.pop("V??", None)

    vols = sorted(by_vol.keys())
    full = [by_vol[v]["full"] for v in vols]
    noisy = [by_vol[v]["noisy"] for v in vols]
    redir = [by_vol[v]["redir"] for v in vols]
    other = [by_vol[v]["other"] for v in vols]
    totals = [max(1, f + n + r + o) for f, n, r, o in zip(full, noisy, redir, other)]

    # Use a 100% stacked bar to emphasize composition (more journal-like than a long absolute-count registry).
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

    # Journal-facing alternative to the labeled scatter: show distributions by volume.
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


def fig1_rights_aware_workflow(root: Path, outdir: Path) -> None:
    """Redesigned Fig 1: publication-quality pipeline overview.

    Layout: 2-row x 3-column serpentine flow.
      Top row (L->R): OCR Corpus  ->  Corpus Profiling  ->  Extraction & Provenance
      Bot row (R->L): Quality Verification  <-  Benchmark Design  <-  Evaluation Assets

    Colour coding:
      grey  = rights-restricted input corpus
      blue  = processing / analysis stages
      amber = quality verification
      green = benchmark tasks and evaluation outputs
    """
    fig = plt.figure(figsize=(7.2, 4.1))
    ax = fig.add_axes([0, 0, 1, 1])   # axes fills full figure; 1 unit = 1 inch-equivalent
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ── Palette ─────────────────────────────────────────────────────────────────
    C = dict(
        priv_f="#F4F4F4", priv_e="#787878",      # private / restricted
        proc_f="#EBF3FB", proc_e="#2C7BB6",      # processing / analysis
        qc_f="#FDF8E1",   qc_e="#B7950B",        # quality verification
        pub_f="#E9F5EA",  pub_e="#2E7D32",       # public release
        arr="#2C2C2C",
        t_dark="#1A1A1A", body="#333333", dim="#666666",
    )

    # ── Geometry ─────────────────────────────────────────────────────────────────
    W, H   = 0.296, 0.400    # box width, height (normalised axes units)
    GX     = 0.038           # horizontal gap between columns
    GY     = 0.100           # vertical gap between rows
    ML, MB = 0.018, 0.025    # left/bottom page margin

    CX = [ML + i * (W + GX) for i in range(3)]   # column left-x positions
    RY = [MB, MB + H + GY]                        # row bottom-y positions

    # ── Helper: draw one labelled box ────────────────────────────────────────────
    def draw_box(col, row, title, lines, fc, ec, badge=None, badge_bg=None):
        x, y = CX[col], RY[row]
        ax.add_patch(FancyBboxPatch(
            (x, y), W, H,
            boxstyle="round,pad=0.014",
            linewidth=1.25, facecolor=fc, edgecolor=ec, zorder=2,
        ))
        # Title
        ax.text(x + W / 2, y + H - 0.021, title,
                ha="center", va="top", fontsize=7.8, fontweight="semibold",
                color=C["t_dark"], zorder=3)
        # Thin rule under title
        ax.plot([x + 0.012, x + W - 0.012], [y + H - 0.051, y + H - 0.051],
                color=ec, lw=0.6, alpha=0.6, zorder=3)
        # Content lines
        cy = y + H - 0.062
        for ln in lines:
            ind = ln.startswith("  ")
            ax.text(x + 0.013 + (0.012 if ind else 0), cy, ln.lstrip(),
                    ha="left", va="top",
                    fontsize=6.5 if ind else 7.1,
                    color=C["dim"] if ind else C["body"], zorder=3)
            cy -= 0.032 if ind else 0.036
        # Tier badge (bottom-right corner)
        if badge:
            BW, BH = 0.076, 0.022
            bx = x + W - BW - 0.009
            by = y + 0.008
            ax.add_patch(FancyBboxPatch(
                (bx, by), BW, BH,
                boxstyle="round,pad=0.004",
                facecolor=badge_bg or C["dim"], edgecolor="none", zorder=4,
            ))
            ax.text(bx + BW / 2, by + BH / 2, badge,
                    ha="center", va="center",
                    fontsize=5.8, color="white", fontweight="bold", zorder=5)

    # ── Helper: draw arrow ────────────────────────────────────────────────────────
    def arr(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle="-|>",
            mutation_scale=9, linewidth=0.9, color=C["arr"], zorder=6,
        ))

    # ── Six pipeline boxes ────────────────────────────────────────────────────────

    # TOP-LEFT  : OCR Input
    draw_box(0, 1,
             "OCR-Derived Corpus",
             ["- Zhongyi Fangji Da Cidian, 2nd ed. (2019)",
              "- 48 Markdown files from 9 volumes",
              "- Digitized via MinerU PDF extractor",
              "- 759,186 lines  |  16.6 M characters",
              "- Rights-restricted source text"],
             C["priv_f"], C["priv_e"])

    # TOP-CENTRE: Corpus Profiling
    draw_box(1, 1,
             "Corpus Profiling & Heterogeneity",
             ["- Noise quantified prior to extraction",
              "- 181 HTML table/block remnants",
              "- 18,179 suspected glued-entry signals",
              "- 24,239 field-heading noise signals",
              "- Front matter, indices, image markers"],
             C["proc_f"], C["proc_e"])

    # TOP-RIGHT : Structured Extraction
    draw_box(2, 1,
             "Entry-Level Extraction & Provenance",
             ["- 97,527 parsed records (schema v14)",
              "- Per-record: source file + char/line span",
              "- Doc-type stratification (5 classes):",
              "  clean  |  noisy  |  redirect",
              "  index-like  |  mixed/unknown"],
             C["proc_f"], C["proc_e"])

    # BOT-RIGHT : Quality verification
    draw_box(2, 0,
             "Quality Verification",
             ["Span fidelity (provenance chain):",
              "  97,527 / 97,527 pass (100%)",
              "Field self-check (internal consistency):",
              "  2 flagged; both explainable",
              "- Confirms traceability, not semantics"],
             C["qc_f"], C["qc_e"])

    # BOT-CENTRE: Benchmark Design
    draw_box(1, 0,
             "Benchmark Pack Design",
             ["Task A: Entry segmentation",
              "  300-item human gold (2 annot. + adjud.)",
              "  Silver consensus: agree/disagree split",
              "Task B: Field robustness",
              "  Strict vs. relaxed heading comparison"],
             C["proc_f"], C["proc_e"])

    # BOT-LEFT  : Experimental Evaluation
    draw_box(0, 0,
             "Experimental Evaluation",
             ["Task A: heuristic / rule / 3-gram NB",
              "  noise-stratified performance slicing",
              "Task B: strict vs. relaxed heading parsing",
              "  recall degradation across 4 fields",
              "  Cohen's κ inter-annotator agreement"],
             C["pub_f"], C["pub_e"])

    # ── Arrows ────────────────────────────────────────────────────────────────────
    MID1 = RY[1] + H / 2   # vertical midpoint of top row
    MID0 = RY[0] + H / 2   # vertical midpoint of bottom row

    # Top row: left -> right
    arr(CX[0] + W, MID1, CX[1],     MID1)
    arr(CX[1] + W, MID1, CX[2],     MID1)

    # Turn-down: top-right box -> bottom-right box (down arrow in the gap)
    arr(CX[2] + W / 2, RY[1], CX[2] + W / 2, RY[0] + H)

    # Bottom row: right -> left (serpentine reading direction)
    arr(CX[2],     MID0, CX[1] + W, MID0)
    arr(CX[1],     MID0, CX[0] + W, MID0)

    save_fig(fig, outdir, "fig1_rights_aware_workflow")
    plt.close(fig)


def fig4_benchmark_composition(root: Path, outdir: Path) -> None:
    items_path = root / "data/benchmarks/items_gold_v2_dual.tsv"
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

    # Heatmap view of the same information (compact and journal-like).
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
    # Panel A: boundary no_f1 (split=all)
    boundary_path = root / "results/benchmarks/task_eval_models_v2_dual.tsv"
    if not boundary_path.exists():
        boundary_path = root / "results/benchmarks/task_eval_models.tsv"
    boundary = read_tsv(boundary_path)
    b_all = [r for r in boundary if (r.get("split") or "") == "all"]
    b_all.sort(key=lambda r: (r.get("task_id") or "", r.get("model_id") or ""))

    # Panel B: field robustness table (already aggregated)
    field_rows = read_tsv(root / "results/manuscript/table5_field_robustness_all.tsv")

    # Panel C: boundary error slices for baseline_inline
    slices_path = root / "results/error_analysis/error_slices_models_v2_dual.tsv"
    if not slices_path.exists():
        slices_path = root / "results/error_analysis/error_slices_models.tsv"
    slices = read_tsv(slices_path)
    s_base = [r for r in slices if (r.get("model_id") or "") == "baseline_inline_formula_id"]
    # Sort by n_labeled desc, take top 8
    def as_int(v: str) -> int:
        try:
            return int((v or "0").strip())
        except Exception:
            return 0

    s_base.sort(key=lambda r: -as_int(r.get("n_labeled", "0")))
    s_base = s_base[:8]

    # More vertical spacing to prevent xlabel overlap between stacked panels.
    fig = plt.figure(figsize=(9.2, 8.4), constrained_layout=True)
    gs = fig.add_gridspec(3, 1, height_ratios=[1.1, 1.2, 1.2], hspace=0.30)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0])
    ax3 = fig.add_subplot(gs[2, 0])

    ax1.text(0.01, 0.96, "(a)", transform=ax1.transAxes, fontsize=10, fontweight="bold", va="top", ha="left")
    raw_model_ids = [r.get("model_id") for r in b_all]
    model_label = {
        "baseline_inline_formula_id": "Inline-identifier heuristic",
        "rule_md_span_v1": "Span-based rule baseline",
        "nb_char3_v0": "Character 3-gram naive Bayes",
    }
    no_f1 = [float(r.get("no_f1") or 0.0) for r in b_all]
    labeled = [(m or "", model_label.get(m or "", m or ""), f) for m, f in zip(raw_model_ids, no_f1)]
    order = ["baseline_inline_formula_id", "nb_char3_v0", "rule_md_span_v1"]
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

    # Error slices for baseline_inline_formula_id
    slice_names = [r.get("slice_value") for r in s_base]
    slice_f1 = [float(r.get("no_f1") or 0.0) for r in s_base]
    slice_n = [as_int(r.get("n_labeled", "0")) for r in s_base]
    slice_names = [human_noise_flag(n or "") for n in slice_names]
    ax3.text(0.01, 0.96, "(c)", transform=ax3.transAxes, fontsize=10, fontweight="bold", va="top", ha="left")
    y = list(range(len(slice_names)))[::-1]
    for yi, f1 in zip(y, slice_f1):
        ax3.hlines(yi, 0, f1, color=COLORS["light_gray"], linewidth=3.0, alpha=0.95)
        ax3.plot(f1, yi, "o", color=COLORS["blue"], markersize=6)
        if f1 > 0:
            ax3.text(min(1.02, f1 + 0.02), yi, f"{f1:.2f}", va="center", fontsize=9, color="#333333")
    ax3.set_yticks(y)
    ax3.set_yticklabels([f"{n}  {name}" for n, name in zip(slice_n, slice_names)])
    ax3.set_xlabel("F1 for boundary-error detection (inline-identifier baseline), by noise slice")
    ax3.set_xlim(0, 1.05)
    ax3.grid(axis="x", alpha=0.22)

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
    fig1_rights_aware_workflow(root, outdir)
    fig4_benchmark_composition(root, outdir)
    fig5_baselines_and_field_robustness(root, outdir)

    print(f"OK: wrote P1 figures to {outdir}")


if __name__ == "__main__":
    main()
