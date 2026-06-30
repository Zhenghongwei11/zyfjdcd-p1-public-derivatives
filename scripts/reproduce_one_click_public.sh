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

echo "[1/2] Verify pack layout (derived-only)"
python3 "$ROOT/scripts/verify_public_pack_v0.py" --root "$ROOT"

echo "[2/2] Checksums for key artifacts"
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
checksum_file "$ROOT/data/benchmarks/items_gold_v2_dual.tsv"
checksum_file "$ROOT/results/benchmarks/task_eval_models.tsv"
checksum_file "$ROOT/results/error_analysis/error_slices_models.tsv"
checksum_file "$ROOT/results/iaa/field_extraction_hardcase_iaa_v2.tsv"
checksum_file "$ROOT/results/benchmarks/field_hardcase_gold_v2_summary.json"
checksum_file "$ROOT/plots/p1/fig1_pipeline_v2.pdf"
checksum_file "$ROOT/plots/p1/fig2_volume_composition.pdf"
checksum_file "$ROOT/plots/p1/fig3_heterogeneity_distributions.pdf"
checksum_file "$ROOT/plots/p1/fig4_benchmark_composition.pdf"
checksum_file "$ROOT/plots/p1/fig5_baselines_and_robustness.pdf"

echo "OK: run bundle written to $RUN_DIR"
