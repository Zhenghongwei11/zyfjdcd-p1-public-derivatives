# Statistical Decision Rules (P1)

This document freezes the minimal evaluation rules used in the P1 resource/benchmark paper track.

## 1. Metrics and Conventions

- Classification labels are normalized to `yes` / `no`.
- Unless stated otherwise, values are reported with 4 decimal places.
- For boundary evaluation tables, `no` is treated as the positive class (detecting boundary problems is the "positive" event).

## 2. Entry Segmentation (Boundary OK)

### Labels

- `boundary_ok_gold`: gold label in `data/benchmarks/items_gold_v2.tsv`
- `boundary_ok_eval`: evaluation label column used by scripts

### Models

- `baseline_inline_formula_id`: predicts `no` when `noise_flags` contains `inline_formula_id`, else `yes`
- `rule_md_span_v1`: rule-based baseline that inspects the source text span for embedded new-entry cues

### Reported Metrics

- `accuracy`
- `no_precision`, `no_recall`, `no_f1`
- Confusion counts: `tp_no`, `fp_no`, `fn_no`

## 3. Field Heading Robustness (Presence)

### Truth Definition

- "Truth" is the relaxed heading detector (`^\\s*#?\\s*【字段】`), evaluated on the same source span.

### Models

- `field_presence_strict_heading`: strict detector (`^【字段】`)
- `field_presence_relaxed_heading`: relaxed detector (matches the truth by construction; used as a sanity baseline)

### Reported Metrics

- Per-field precision/recall/F1 for `组成`, `用法`, `功用`, `主治`

## 4. Field Extraction Robustness (Value)

This is a proxy task that treats a relaxed heading-based value parser as the "truth" definition, and evaluates stricter parsers against it.

### Models

- `field_value_strict_heading_v0`: strict heading parser (only headings at line start)
- `field_value_relaxed_heading_v0`: relaxed heading value parser (sanity baseline; matches the truth definition)

### Reported Metrics

- Per-field exact-match precision/recall/F1 for `组成`, `用法`, `功用`, `主治` (after whitespace normalization)

## 4. Split and Contamination Assessment

- Train/dev/test are assigned by split policy described in [SPLIT_POLICY.md](SPLIT_POLICY.md).
- `results/benchmarks/split_audit.tsv` is treated as a required artifact for any benchmark claim.
