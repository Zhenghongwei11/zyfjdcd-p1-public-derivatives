# Split Policy (Internal Prototype v0)

本文件定义本项目 **internal prototype** 阶段的 benchmark 切分规则，用于保证评测可复现、可审计，并降低“同源格式泄漏”。

注意：submission-ready benchmark 的 split 政策必须在本文件基础上进一步冻结，并配套 `results/benchmarks/split_audit.tsv`、污染检查与双标裁决流程（详见 `docs/BENCHMARK_READINESS.md`）。

## 1. 切分单元

当前以 `source_file`（一个 OCR Markdown 文件）作为分组单元，保证同一文件内的样本不会跨 split，减少模板/邻近条目带来的泄漏。

## 2. Split 集合与比例

- `train`: 约 70%
- `dev`: 约 15%
- `test`: 约 15%

在样本规模较小时（例如当前 100 级别），比例会有轻微波动，但切分算法保持确定性。

## 3. 确定性切分算法

对每个 `source_file` 计算 `sha1(source_file)`，取其十六进制整数的 `mod 100` 作为 `bucket`：

- `bucket < 70` -> `train`
- `70 <= bucket < 85` -> `dev`
- `bucket >= 85` -> `test`

同一 `source_file` 永远落入同一 split。若后续新增样本来自同一 `source_file`，split 会自动继承且保持稳定。

## 4. 审计与污染检查

每次生成 benchmark items 后，必须生成：

- `results/benchmarks/split_audit.tsv`: split 规模、doc_type 分布、边界标签分布、噪声分布、文件覆盖等。

internal prototype 阶段仅做“分布审计”；submission-ready 阶段需增加：

- 近邻/重复检测（例如 header 重复、组成字段近似重复）
- 模板泄漏检查（同一页/同一小节跨 split）
- 硬例(hard cases)固定 holdout 的显式定义

## 5. 版本与可复现性

本策略对应的生成脚本应把以下信息写入 `split_audit.tsv` 的 `notes`：

- 输入标注包路径（例如 `annotation/silver/silver_v3_ai.tsv`）
- 解析器版本（例如 `data/structured/formulas_v2.jsonl`）
- 脚本版本（git commit 或生成时间戳）

