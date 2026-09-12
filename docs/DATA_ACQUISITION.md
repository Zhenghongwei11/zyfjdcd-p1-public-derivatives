# 数据获取与 OCR/抽取链路（方法说明）

本节说明本地受限 OCR Markdown 源文本的来源与生成路径。

## 1. 原始来源

- 数据来源：纸质《中医方剂大辞典》第 2 版（实体书）
- 数字化方式：逐页拍照，汇总为 PDF

## 2. OCR / PDF-to-Markdown 抽取

### 2.1 使用工具

- MinerU（通过 OpenDataLab 的在线 PDF Extractor 使用）

在线工具入口：

```text
https://opendatalab.com/OpenSourceTools/Extractor/PDF
```

### 2.2 产物落盘

- OCR/抽取后的 Markdown 文件保存为本地受限源文本层。
- 说明：该源文本层属于 OCR 衍生文本，默认不公开再分发（见 `docs/RIGHTS_AND_RELEASE_PLAN.md`）。

## 3. 可复现性与权利边界

- 本项目对外发布以“派生层优先”为原则：公开 schema、评测表、split summary、脚本与派生结构化/规范化产物；不默认公开整本 OCR 原文。
- 公开分析包提供不含原文的标签、预测、统计结果和图表数据；完整 OCR 文本不随包分发。
