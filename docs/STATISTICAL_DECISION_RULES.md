# Statistical analysis

## Entry-boundary outcomes

Boundary error (`boundary_ok = no`) is the positive class. Reported measures are accuracy, positive-class precision, recall, F1, and the corresponding confusion counts.

The four held-out baselines are:

- an inline-identifier heuristic;
- a span-based structural rule;
- character 2–5-gram TF-IDF with a class-balanced linear support-vector classifier;
- frozen `BAAI/bge-small-zh-v1.5` representations with class-balanced logistic regression.

Hyperparameters for learned models are selected on the development partition. Each selected model is refitted on training plus development data and evaluated once on the held-out test partition.

Pointwise 95% confidence intervals are percentile intervals from 10,000 nonparametric bootstrap resamples of held-out items. Pairwise differences in correctness use exact McNemar tests. The six pairwise P values are adjusted by the Holm procedure.

## Field robustness

The relaxed reference recognizes a bracketed field marker after optional whitespace or a Markdown heading marker. The strict parser requires a canonical line-start field marker. Heading-presence recall is the fraction of relaxed-reference headings recovered by the strict parser. Value-extraction recall is the fraction of relaxed-reference values exactly recovered after whitespace normalization.

Field robustness is reported separately for composition (`组成`), administration (`用法`), actions (`功用`), and indications (`主治`). These measures characterize sensitivity to text-formatting artifacts and are not semantic assessments of medical content.
