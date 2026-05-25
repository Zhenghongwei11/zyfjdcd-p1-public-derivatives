# Reproducibility Pack (Derived Only)

This repository contains a reproducible pipeline and derived artifacts for an OCR-derived corpus from the 2nd edition of 《中医方剂大辞典》.

## What Is Included

- Derived benchmark indices and evaluation tables (no long text excerpts)
- Corpus-scale consensus diagnostics for entry-boundary evaluation, including a large silver agreement subset and disagreement challenge summary
- Public-safe normalization *summaries* (counts only; no phrase-level text exports)
- Provenance tables for figures/tables and a data manifest
- Scripts to verify the pack integrity
- Archive metadata for public deposit (`CITATION.cff`, `.zenodo.json`)

## What Is Not Included

- The full OCR-derived Markdown source under `cidian/`
- Any structured exports that contain raw text (`raw_text`) that could reconstruct the book content
- Any derived files that contain phrase-level field values or evidence snippets from the book text (these remain private or reviewer-limited)

## Quick Start

From repo root:

```bash
scripts/reproduce_one_click_public.sh
```

This performs integrity checks and writes a run log under `results/runs_public/<run_id>/`.

## Notes on Access

To fully re-run the end-to-end extraction pipeline from OCR source, you need legitimate access to the underlying book material. This pack is designed so that core benchmark tables and derived artifacts can be inspected without redistributing the full OCR text.

## Public Deposit

Zenodo DOI (versioned): `10.5281/zenodo.20376556`
