# Split policy

The entry-boundary benchmark is partitioned by OCR source file so that records from the same file cannot occur in both model-development and test data.

For each source file, the hexadecimal SHA-1 digest of its relative identifier is converted to an integer and reduced modulo 100. Buckets below 70 are assigned to training, buckets 70–84 to development, and buckets 85–99 to test. The procedure is deterministic and preserves the assignment when new records from an existing source file are added.

The 600-item adjudicated reference spans 46 source files and contains:

| Split | Items | Source files |
| --- | ---: | ---: |
| Training | 389 | 30 |
| Development | 103 | 8 |
| Test | 108 | 8 |

The held-out test partition is not used for hyperparameter selection. The released benchmark index records each item's split, source-file identifier, noise indicators, and adjudicated boundary label.
