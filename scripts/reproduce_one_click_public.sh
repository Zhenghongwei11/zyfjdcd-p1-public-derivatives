#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$ROOT/results/runs_public/$RUN_ID"
LOG="$RUN_DIR/run.log"

mkdir -p "$RUN_DIR"

{
  echo "run_id=$RUN_ID"
  echo "root=$ROOT"
  echo "date=$(date +\"%Y-%m-%dT%H:%M:%S%z\")"
  echo "python=$(python3 -V 2>&1 | tr -d '\n')"
  echo "uname=$(uname -a)"
} > "$RUN_DIR/run.env.txt"

exec > >(tee "$LOG") 2>&1

echo "[1/5] Verify pack layout (derived-only)"
python3 "$ROOT/scripts/verify_public_pack_v0.py" --root "$ROOT"

echo "[2/5] Recompute annotation agreement"
mkdir -p "$RUN_DIR/iaa"
python3 "$ROOT/scripts/recompute_annotation_agreement_v1.py" \
  --labels-tsv "$ROOT/data/benchmarks/entry_segmentation_dual_labels_v1.tsv" \
  --task-id entry_segmentation \
  --output-tsv "$RUN_DIR/iaa/entry_segmentation_iaa.tsv"
python3 "$ROOT/scripts/recompute_annotation_agreement_v1.py" \
  --labels-tsv "$ROOT/data/benchmarks/document_type_dual_labels_v1.tsv" \
  --task-id doc_type_classification \
  --output-tsv "$RUN_DIR/iaa/doc_type_classification_iaa.tsv"

echo "[3/5] Recompute held-out statistics"
mkdir -p "$RUN_DIR/statistics"
python3 "$ROOT/scripts/recompute_boundary_baseline_statistics_v2.py" \
  --predictions-tsv "$ROOT/results/benchmarks/boundary_baseline_test_predictions_v2.tsv" \
  --output-summary-tsv "$RUN_DIR/statistics/boundary_baseline_summary.tsv" \
  --output-comparisons-tsv "$RUN_DIR/statistics/boundary_baseline_pairwise.tsv"

echo "[4/5] Rebuild manuscript tables and data-driven figures"
python3 "$ROOT/scripts/build_p1_manuscript_tables_v0.py" \
  --root "$ROOT" \
  --outdir "${RUN_DIR#$ROOT/}/tables"
python3 "$ROOT/scripts/plot_p1_figures_v0.py" \
  --root "$ROOT" \
  --outdir "${RUN_DIR#$ROOT/}/figures"
cp "$ROOT/plots/p1/fig1_pipeline_v2.svg" "$RUN_DIR/figures/fig1_pipeline_v2.svg"
if command -v rsvg-convert >/dev/null 2>&1; then
  rsvg-convert -f pdf -o "$RUN_DIR/figures/fig1_pipeline_v2.pdf" "$RUN_DIR/figures/fig1_pipeline_v2.svg"
  rsvg-convert -f png -w 1920 -o "$RUN_DIR/figures/fig1_pipeline_v2.png" "$RUN_DIR/figures/fig1_pipeline_v2.svg"
else
  cp "$ROOT/plots/p1/fig1_pipeline_v2.pdf" "$RUN_DIR/figures/fig1_pipeline_v2.pdf"
  cp "$ROOT/plots/p1/fig1_pipeline_v2.png" "$RUN_DIR/figures/fig1_pipeline_v2.png"
fi
cp "$ROOT/results/manuscript/table1_benchmark_comparison.tsv" "$RUN_DIR/tables/table1_benchmark_comparison.tsv"

echo "[5/5] Checksums for key artifacts"
CHECKSUMS="$RUN_DIR/CHECKSUMS.sha256"
: > "$CHECKSUMS"

checksum_file() {
  local f="$1"
  if [[ -f "$f" ]]; then
    (cd "$ROOT" && shasum -a 256 "${f#$ROOT/}") >> "$CHECKSUMS"
  else
    echo "MISSING  ${f#$ROOT/}" >> "$CHECKSUMS"
  fi
}

checksum_file "$ROOT/docs/DATA_MANIFEST.tsv"
checksum_file "$ROOT/docs/FIGURE_PROVENANCE.tsv"
checksum_file "$ROOT/data/benchmarks/entry_segmentation_gold_index_v1.tsv"
checksum_file "$ROOT/results/benchmarks/field_presence_item_outcomes_v1.tsv"
checksum_file "$ROOT/results/benchmarks/task_eval_models_v3_dual.tsv"
checksum_file "$ROOT/results/error_analysis/error_slices_models_v3_dual.tsv"
checksum_file "$ROOT/results/iaa/field_extraction_hardcase_iaa_v2.tsv"
checksum_file "$ROOT/results/benchmarks/field_hardcase_gold_v2_summary.json"
checksum_file "$ROOT/results/benchmarks/field_value_item_outcomes_v1.tsv"
checksum_file "$ROOT/results/benchmarks/boundary_baseline_test_predictions_v2.tsv"
checksum_file "$ROOT/results/benchmarks/boundary_baseline_test_summary_v2.tsv"
checksum_file "$ROOT/results/statistics/boundary_baseline_mcnemar_v2.tsv"
checksum_file "$ROOT/results/metadata/boundary_baseline_eval_v2.json"
checksum_file "$ROOT/plots/p1/fig1_pipeline_v2.pdf"
checksum_file "$ROOT/plots/p1/fig2_volume_composition.pdf"
checksum_file "$ROOT/plots/p1/fig3_heterogeneity_distributions.pdf"
checksum_file "$ROOT/plots/p1/fig4_benchmark_composition.pdf"
checksum_file "$ROOT/plots/p1/fig5_baselines_and_robustness.pdf"

echo "OK: run bundle written to $RUN_DIR"
