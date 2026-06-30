# 方剂结构化数据 Schema（v0.1 草案）

## 1. 设计目标

结构化层必须同时满足三件事：

1. 保留 OCR 原文证据；
2. 支持条目切分、字段抽取、规范化和异名归并；
3. 不把“纠错后文本”与“原始源文本”混为一层。

## 2. 记录单位

默认记录单位为“formula-level record”，即一条可判定的方剂相关记录：

- 完整方剂正文条目
- 异名/见该条引导条目
- 困难但可界定的噪声条目

## 3. 字段分层

### 3.1 Source layer

用于回溯原文来源，不做语义纠正。

| 字段 | 含义 |
| --- | --- |
| `record_id` | 项目内部唯一记录 ID |
| `formula_id_text` | OCR 中直接观察到的 5 位编号文本 |
| `headword_raw` | 原始方名文本 |
| `source_file` | 来源 Markdown 文件 |
| `source_line_start` | 估计起始行 |
| `source_line_end` | 估计结束行 |
| `doc_type` | 文档类型 |
| `eligibility` | 任务资格 |
| `raw_text` | 原始条目文本 |

### 3.2 Raw extraction layer

用于保存字段抽取结果，不做过度清洗。

| 字段 | 含义 |
| --- | --- |
| `source_citation_raw` | 方源/出处原文 |
| `alias_raw` | `【异名】` 原文 |
| `composition_raw` | `【组成】` 原文 |
| `usage_raw` | `【用法】` 原文 |
| `efficacy_raw` | `【功用】` 原文 |
| `indication_raw` | `【主治】` 原文 |
| `contraindication_raw` | `【宜忌】` 原文 |
| `modification_raw` | `【加减】` 原文 |
| `commentary_raw` | `【方论选录】` 原文 |
| `clinical_report_raw` | `【临床报道】` 原文 |
| `modern_research_raw` | `【现代研究】` 原文 |
| `notes_raw` | `【备考】` 原文 |
| `redirect_target_raw` | 引导条的目标方名或目标说明 |

### 3.3 Normalized layer

用于后续计算与 benchmark，不覆盖原文层。

| 字段 | 含义 |
| --- | --- |
| `headword_norm` | 规范化方名 |
| `alias_list_norm` | 规范化异名列表 |
| `composition_items_norm` | 规范化药物组成列表 |
| `dose_items_norm` | 剂量解析结果 |
| `processing_items_norm` | 炮制/制法修饰信息 |
| `formula_cluster_id` | 同方异名聚类 ID |
| `normalization_status` | 规范化完成状态 |

### 3.4 QA layer

| 字段 | 含义 |
| --- | --- |
| `parse_status` | 解析状态 |
| `noise_flags` | OCR 噪声标签 |
| `review_status` | 是否人工复核 |
| `benchmark_split` | train/dev/test 或 restricted |

## 4. 最小必需字段

第一版 JSONL 至少必须包含：

- `record_id`
- `formula_id_text`
- `headword_raw`
- `source_file`
- `source_line_start`
- `source_line_end`
- `doc_type`
- `eligibility`
- `raw_text`

以及能抽取到的 `composition_raw`、`usage_raw`、`indication_raw`。

## 5. 字段缺失策略

- 缺字段用 `null`，不使用空字符串冒充“已确认无该字段”
- OCR 不确定但可疑似识别的值不直接写进规范化层
- 引导条可以只有 `headword_raw + redirect_target_raw`

## 6. 示例

```json
{
  "record_id": "F0000001",
  "formula_id_text": "00001",
  "headword_raw": "一匕金",
  "source_file": "第1册1.md",
  "source_line_start": 4,
  "source_line_end": 12,
  "doc_type": "FORMULA_ENTRY_FULL",
  "eligibility": "entry_segmentation|field_extraction|herb_normalization|alias_resolution",
  "raw_text": "00001一匕金（《活幼心书》卷下） ...",
  "composition_raw": "穿山甲...各二钱半",
  "usage_raw": "上为末...",
  "indication_raw": "豆疮黑陷...",
  "noise_flags": [],
  "parse_status": "parsed_partial",
  "review_status": "pending"
}
```

## 7. 版本策略

- 当前文档定义 `schema_version = 0.1`
- 一旦字段集合或语义发生改变，必须同步更新 `data/structured/schema_version.json`
