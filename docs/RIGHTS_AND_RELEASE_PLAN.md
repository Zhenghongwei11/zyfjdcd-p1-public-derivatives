# 权利与发布分级计划

## 1. 当前默认立场

`cidian/` 下 Markdown 为纸质《中医方剂大辞典》第 2 版的 OCR 衍生文本。除非后续取得明确授权或出版方许可，本项目默认不把整本 OCR 文本视为可公开再分发内容。

## 2. 发布分级

| tier | 名称 | 默认可见范围 | 当前默认状态 | 典型内容 |
| --- | --- | --- | --- | --- |
| `T0_PRIVATE_SOURCE` | 私有源文本 | 项目内部 | 允许 | `cidian/*.md`、原始截图、长文本片段 |
| `T1_REVIEWER_LIMITED` | 受限审稿材料 | 审稿或编辑部按需 | 条件允许 | 少量必要片段、困难样本截图、局部证据页 |
| `T2_PRIVATE_DERIVED` | 私有派生层 | 项目内部 | 允许 | 中间结构化 JSONL、未审校标签、内部索引 |
| `T3_PUBLIC_DERIVED` | 公开派生层 | 公开 | 优先准备 | schema、task registry、标注规则、split manifest、指标表、匿名化或去原文派生标签、代码 |
| `T4_PUBLIC_TEXT` | 公开原文层 | 公开 | 默认禁止 | 全量 OCR 文本、连续大段原文、整条全文公开样本 |

## 3. 当前建议的公开策略

第一篇论文默认只承诺 `T3_PUBLIC_DERIVED`：

- `ENTRY_SCHEMA`
- `TASK_REGISTRY.tsv`
- `ANNOTATION_GUIDELINES`
- `ANNOTATION_PLAN.tsv`
- `NORMALIZATION_POLICY`
- benchmark manifest
- split audit
- baseline 和 error-slice 结果表
- 代码与重建脚本
- （若涉及规范化/归并/字段值层）优先公开**计数/分布/错误切片等 summary**，而不是可读的短语级字段值导出

默认不承诺：

- 全量 Markdown 原文
- 大段连续条目原文
- 能直接重构整册内容的完整文本导出

## 4. 审稿材料策略

若期刊或审稿人确需查看源文本，应按最小必要原则准备：

- 仅提供少量代表性片段
- 只提供与版次核验、困难样本说明、标注争议相关的必要证据
- 优先提供截图或局部片段，而不是整册文本
- 所有 reviewer-only 材料在 release manifest 中单列

## 5. 公开资源的推荐内容

优先公开以下不依赖全文再分发的产物：

- 文档类型标签
- 条目资格标签
- 片段定位索引
- JSONL schema
- 字段标签与规范化规则（policy）与 summary（counts / error slices）
- benchmark split 和 evaluation manifest
- baseline 输出表
- 错误切片统计

## 6. 高风险点

1. Data Descriptor 类期刊往往要求更强开放度。
2. 若公开文本片段过长，可能接近实质性再分发。
3. 若结构化导出可逆推出大部分原文，也可能带来权利风险。

## 7. 当前投稿含义

- `Journal of Biomedical Informatics` 类方法/benchmark 期刊：当前更匹配
- `Scientific Data` 类数据开放期刊：只有在权利与开放策略足够清晰时再考虑

## 8. 更新触发条件

以下任一条件出现时，本文件必须更新：

- 获得出版社或权利方明确授权
- 决定公开金标准文本片段
- 期刊要求提交 reviewer-only 数据包
- 结构化数据字段设计发生变化，导致可逆性上升
