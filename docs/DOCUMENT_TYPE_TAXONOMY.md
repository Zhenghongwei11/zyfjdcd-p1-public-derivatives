# 文档类型分类法

## 1. 目的

本分类法用于把 `cidian/` 中的源文本先分成“是什么”，再决定“能不能进条目抽取与 benchmark”。文件本身不是分类单位，最终分类单位应允许细到片段或连续行块。

## 2. 分类层级

| type_code | 名称 | 定义 | 当前示例 | 默认用途 |
| --- | --- | --- | --- | --- |
| `FRONT_TITLE` | 题名/卷册页 | 书名、卷册、主编、出版社等题名页信息 | [cidian/第9册.md](../cidian/第9册.md) 开头 | 保留为版次证据，不进抽取 |
| `BIB_RIGHTS` | CIP/版权/版次信息 | CIP、ISBN、版次、版权声明、定价等 | [cidian/第9册.md](../cidian/第9册.md) 版权页段 | 保留为书目证据，不进抽取 |
| `EDITORIAL_PARATEXT` | 编委会/前言/说明性文字 | 编委会名单、前言、修订说明、编纂说明 | [cidian/第9册.md](../cidian/第9册.md) `2版前言` 段 | 保留为背景证据，不进抽取 |
| `TOC_INDEX` | 目录/索引/总目 | 总目、字画索引、页码目录、检索列表 | [cidian/第9册.md](../cidian/第9册.md) 中的 HTML 目录表 | 不进字段抽取，可进文档分类任务 |
| `TABLE_HTML` | HTML 表格残留 | OCR/转换后保留的 `<html><body><table>` 结构 | [cidian/第9册.md](../cidian/第9册.md) | 作为噪声层或目录层保留 |
| `IMAGE_PLACEHOLDER` | 图片占位 | `![](...)` 或仅图片链接残留 | [cidian/第9册.md](../cidian/第9册.md) | 不进抽取 |
| `FORMULA_ENTRY_FULL` | 完整方剂正文条目 | 具有方名/编号，且至少包含若干标准字段 | [cidian/第1册1.md](../cidian/第1册1.md) 中 `00001` 等条 | 进入主抽取任务 |
| `FORMULA_ENTRY_REDIRECT` | 异名/见该条引导条目 | 仅说明“为某方异名，见该条” | [cidian/第1册1.md](../cidian/第1册1.md) 中 `00015`、`00016` 类条 | 进入分割和异名任务，不进常规字段抽取 |
| `FORMULA_ENTRY_NOISY` | 可识别但噪声较重的正文条目 | 仍可定位为方剂条目，但存在粘连、误标题、缺换行、字段压扁等问题 | [cidian/第1册1.md](../cidian/第1册1.md) 多处相邻条目 | 进入困难样本层 |
| `OCR_NOISE` | 纯 OCR 噪声或碎片 | 不构成稳定语义单元的乱码、残缺、断裂串 | [cidian/第1册6.md](../cidian/第1册6.md)、[cidian/第5册6.md](../cidian/第5册6.md) 局部 | 不进主任务，可进噪声评测 |
| `MIXED_UNKNOWN` | 混合未决片段 | 同一片段同时含正文、目录、噪声，暂不能自动定类 | 各册尾部过渡片段 | 先人工复核 |

## 3. 当前关键观察

1. [cidian/第9册.md](../cidian/第9册.md) 明确不是“纯条目正文文件”，至少同时包含 `FRONT_TITLE`、`BIB_RIGHTS`、`EDITORIAL_PARATEXT`、`TOC_INDEX`、`TABLE_HTML`、`IMAGE_PLACEHOLDER`。
2. [cidian/第1册1.md](../cidian/第1册1.md) 以 `FORMULA_ENTRY_FULL` 为主，但混入 `FORMULA_ENTRY_NOISY` 与 `FORMULA_ENTRY_REDIRECT`。
3. 尾段文件不能按文件名直接判为“目录”或“附录”，必须逐片段判断。

## 4. 推荐标注单位

- 第一层：文件级粗标签，判断该文件是否“混合文件”
- 第二层：片段级标签，以连续若干行构成的最小可判定片段为单位
- 第三层：条目级标签，仅对 `FORMULA_ENTRY_FULL`、`FORMULA_ENTRY_REDIRECT`、`FORMULA_ENTRY_NOISY` 再做细分

## 5. 与后续任务的关系

- 文档分类任务：使用全部类型
- 条目切分任务：只使用方剂相关类型与困难混合类型
- 字段抽取任务：主用 `FORMULA_ENTRY_FULL`，辅以 `FORMULA_ENTRY_NOISY`
- 异名归并任务：重点使用 `FORMULA_ENTRY_REDIRECT` 与显式 `【异名】` 字段
- 公开 release：优先发布类型标签、片段定位和派生注释，不默认发布大段原文
