# P1 Figures

This folder contains the figures for the resource and benchmark study.

All files here are **derived-only** (counts, scores, and diagrams). No full text from the private OCR source is included.

## Regenerate

From repo root:

```bash
python3 scripts/plot_p1_figures_v0.py --root . --outdir plots/p1
```

## Files

- `fig1_pipeline_v2.*`: corpus construction and held-out evaluation overview.
- `fig2_volume_composition.*`: volume-level parsed record composition (100% stacked share).
- `fig3_heterogeneity_distributions.*`: heterogeneity signal distributions by volume (violin plots).
- `fig4_benchmark_composition.*`: benchmark split counts + top noise indicators.
- `fig5_baselines_and_robustness.*`: held-out boundary F1, field robustness, and test errors by document type.
