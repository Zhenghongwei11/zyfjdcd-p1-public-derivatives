# Derived-Only Analysis Pack

This repository contains derived artifacts and public-safe analysis scripts for an OCR-derived corpus from the 2nd edition of 《中医方剂大辞典》.

## What Is Included

- Derived benchmark indices, item-level paired annotation labels, held-out model predictions, and per-record binary evaluation outcomes (no source-text excerpts)
- Corpus-scale consensus diagnostics for entry-boundary evaluation, including a large silver agreement subset and disagreement challenge summary
- Provenance tables for figures/tables and a data manifest
- Author-generated parsing, integrity-check, evaluation, statistical-analysis, plotting, and pack-verification scripts
- Archive metadata for public deposit (`CITATION.cff`, `.zenodo.json`)

## What Is Not Included

- The full OCR-derived Markdown source text
- Any structured exports that contain raw text (`raw_text`) that could reconstruct the book content
- Any derived files that contain phrase-level field values or evidence snippets from the book text (these remain private or restricted)

## Quick Start

From repo root:

```bash
scripts/reproduce_one_click_public.sh
```

This verifies the package, recomputes agreement and held-out statistics, rebuilds the manuscript tables, regenerates the data-driven figures, and writes all reconstructed outputs under `results/runs_public/<run_id>/`. See `docs/REPRODUCTION_GUIDE.md` for the boundary between public reconstruction and source-dependent reprocessing.

## Notes on Access

To re-run extraction from source, researchers need lawful access to the underlying 2nd edition and must create or obtain a local OCR-derived text layer. The public prediction and per-record outcome tables are sufficient to reconstruct the reported aggregate evaluation metrics without redistributing the full OCR text.

## Public Deposit

Versioned GitHub releases are archived on Zenodo. This repository corresponds to release `v1.0.7`; the concept DOI `https://doi.org/10.5281/zenodo.20376555` resolves to the latest archived version.
