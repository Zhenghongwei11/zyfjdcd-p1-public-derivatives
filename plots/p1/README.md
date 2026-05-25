# P1 Figures

This folder contains the manuscript figures for paper `P1` (resource + benchmark).

All files here are **derived-only** (counts, scores, and diagrams). No full text from the private OCR source is included.

## Regenerate

From repo root:

```bash
python3 scripts/plot_p1_figures_v0.py --root . --outdir plots/p1
```

## Files

- `fig1_source_registry.*`: file-level parsed record composition (by source markdown file).
- `fig2_noise_and_audits.*`: noise landscape + audit summaries (span fidelity, field self-check).
- `fig3_pipeline_diagram.*`: rights-aware pipeline + release tiers (private source vs public derived package).
- `fig4_benchmark_composition.*`: benchmark split counts + top noise flags.
- `fig5_baselines_and_robustness.*`: boundary baselines + field robustness + error slices.

