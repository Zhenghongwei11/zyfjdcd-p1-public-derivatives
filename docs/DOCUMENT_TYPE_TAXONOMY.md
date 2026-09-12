# Document-type taxonomy

Document types distinguish formula records from non-entry and structurally ambiguous material in the OCR-derived corpus.

| Code | Operational definition |
| --- | --- |
| `FRONT_TITLE` | Title, volume, editor, or publisher matter from a title page. |
| `BIB_RIGHTS` | Bibliographic, ISBN, edition, pricing, or copyright information. |
| `EDITORIAL_PARATEXT` | Prefaces, editorial notes, committee lists, or compilation notes. |
| `TOC_INDEX` | Contents, indexes, lookup lists, or page-number listings. |
| `TABLE_HTML` | Residual HTML table structure produced during conversion. |
| `IMAGE_PLACEHOLDER` | A segment containing only an image marker or image link. |
| `FORMULA_ENTRY_FULL` | A formula record with an identifiable headword or identifier and one or more standard fields. |
| `FORMULA_ENTRY_REDIRECT` | A self-contained alias or cross-reference record directing the reader to another formula. |
| `FORMULA_ENTRY_NOISY` | An identifiable formula record affected by merged lines, displaced headings, or other structural noise. |
| `OCR_NOISE` | Fragmentary OCR output without a stable document function. |
| `MIXED_UNKNOWN` | A segment combining multiple functions or remaining ambiguous after inspection. |

The taxonomy is applied at segment level. A source file may contain several document types.
