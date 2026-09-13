# Corpus scope

## Source layer

The working source layer comprises 48 OCR-derived Markdown files generated from a photographed physical copy of the 2nd edition of *Zhongyi Fangji Da Cidian*. The nine printed volumes were converted into multiple digital segments. The complete Markdown layer is retained locally because it substantially reproduces a copyrighted third-party work.

## Corpus profile

The source layer contains 759,186 lines and 16,640,727 characters. The corpus profile records 18,179 joined-entry signals, 24,239 malformed-heading signals, 181 HTML table or block remnants, and 10 image links. These counts are pattern-based indicators of structural heterogeneity, not human error labels.

The derived parser output contains 97,527 record spans:

- 62,778 clean formula-entry records;
- 21,821 noisy formula-entry records;
- 11,803 redirect-like records; and
- 1,125 index-like or mixed/unknown records.

The complete machine-readable profile is provided in `results/corpus/corpus_profile.json`.

## Included material

The working corpus retains formula entries together with front matter, publication information, tables of contents, indexes, embedded tables, image markers, and OCR or Markdown artifacts. These non-entry regions are classified rather than discarded so that corpus accounting and error analysis include the heterogeneous source structure.

## Public boundary

The public package contains derived indices, binary labels and outcomes, model predictions, aggregate tables, and analysis code. It does not contain the photographed pages, PDFs, complete OCR-derived Markdown, raw record text, or phrase-level extracted field values.
