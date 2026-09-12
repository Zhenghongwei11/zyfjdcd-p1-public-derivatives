# Annotation guidelines

## Entry-boundary task

The annotation unit is one proposed formula-entry span. Annotators assign:

- `yes` when the span contains exactly one complete entry;
- `no` when the span merges two or more entries, truncates the target entry, includes text belonging to an adjacent entry, or otherwise crosses an entry boundary.

Formatting noise alone does not make a boundary incorrect if one complete entry remains identifiable. Redirect records are judged as complete entries when their own redirect statement is intact and no adjacent entry text is included.

## Document-type task

Each segment is assigned one operational type from the taxonomy in `DOCUMENT_TYPE_TAXONOMY.md`. Classification is based on the segment's function and content, not only its formatting.

## Field-review task

For the hard-case field slice, annotators judge whether the relaxed-parser value is acceptable for the named field in the source span. The binary labels are `yes` and `no`. This task evaluates field localization under OCR and Markdown artifacts; it does not evaluate the medical correctness of the source text.

## Independent annotation and adjudication

Two annotators label the same item list independently. Their labels are compared only after both annotation files are complete. Disagreements are resolved by joint review of the source span, and the adjudicated outcome becomes the reference label. The public label files omit source excerpts and free-text adjudication notes.
