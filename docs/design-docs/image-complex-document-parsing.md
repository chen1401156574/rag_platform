# 图片与复杂文档解析增强方案

更新时间：2026-06-15

## 背景

当前平台已经具备 PDF、DOCX、TXT、Excel、Markdown、HTML、JSON 等文本型文档解析能力，复杂 PDF 正式入库链路中接入了 DeepDOC OCR、版面识别和表格识别能力。

但现有实现仍有明显边界：

- 独立图片文件（PNG、JPG、JPEG、WEBP 等）不能作为知识库内容直接解析入库。
- 单会话快速解析只支持 PDF、DOCX、TXT，且 PDF 使用 `pdfplumber.extract_text()`，对扫描 PDF 不稳定。
- 正式入库主要生成文本 Chunk，图片块、坐标、图表、表格结构和视觉摘要没有形成统一可追溯数据模型。
- 管理端可以展示图片类型图标，但上传接口多数只是登记元数据，不代表图片内容已被解析。
- 主问答链路只向 LLM 输入文本参考内容，没有把图片或多模态信息纳入 Prompt。

因此，平台需要一条面向企业 RAG 的图片与复杂文档解析增强链路。

## 目标

- 支持图片、扫描 PDF 和复杂版面文档进入知识库。
- 保留 OCR 原文、页码、坐标、块类型、图片路径等可溯源信息。
- 对表格、公式、图表、截图和普通照片提供更适合 RAG 的结构化内容。
- 在不牺牲可核验性的前提下，引入多模态模型补充图片语义理解。
- 与现有 Chunk、Embedding、Elasticsearch、Trace 和管理端入库任务体系兼容。

## 非目标

- 不在第一阶段完全替换现有 DeepDOC 和文本解析链路。
- 不让多模态模型替代 OCR 作为事实来源。
- 不把普通图片理解结果伪装成原文事实。
- 不在同步上传接口中直接执行重型解析任务。

## 总体方案

采用“MinerU 主解析 + 可选 PaddleOCR fallback + 多模态模型语义增强”的分层方案。

```text
文件上传
-> 文件类型识别
-> 简单文本型文档：沿用当前解析器
-> 图片、扫描 PDF、复杂版面文档：调用 MinerU
-> 轻量图片 OCR fallback：可调用 PaddleOCR
-> 图表、截图、照片类块：调用多模态模型生成视觉摘要
-> 标准化 DocumentBlock
-> Chunk 生成
-> Embedding
-> Elasticsearch 入库
-> PostgreSQL 元数据、任务节点、Trace 记录
```

## 组件分工

| 组件 | 定位 | 主要职责 |
| --- | --- | --- |
| 当前解析器 | 保留的基础解析能力 | 处理纯文本 PDF、DOCX、TXT、Markdown、HTML、JSON、Excel 等简单场景 |
| MinerU | 主文档视觉解析引擎 | 处理扫描 PDF、图片、复杂版面、表格、公式、图表，输出 Markdown/JSON/图片资源 |
| PaddleOCR | 可选轻量 OCR fallback | 在只需要图片文字识别、或 MinerU 不适合的轻量场景中兜底 |
| 多模态模型 | 图片语义理解增强 | 对图表、截图、照片、流程图生成视觉摘要和标签 |
| 现有 RAG 入库链路 | 统一入库与检索 | 对标准化后的文本和摘要做 Chunk、Embedding、ES 写入 |

## MinerU 负责什么

MinerU 应作为图片与复杂文档解析的主入口，重点产出可被 RAG 使用的结构化结果：

- OCR 文本。
- 文档阅读顺序。
- 标题、段落、列表、表格、公式、图片、图表等块类型。
- Markdown 或 HTML 表格。
- 公式 LaTeX。
- 页码、bbox、图片裁剪路径。
- 与原始文件的来源关系。

MinerU 的输出不应直接作为最终 ES 文档写入，而应先转换为统一 `DocumentBlock`。

## 多模态模型负责什么

多模态模型只负责 OCR 难以覆盖的视觉语义：

- 图表趋势解释。
- 流程图或架构图的文字化描述。
- 截图界面的功能或状态说明。
- 普通照片中的对象、场景、异常点描述。
- 对图片生成检索标签。

多模态输出必须标记为 `visual_summary` 或 `model_inference`，与 OCR 原文区分。

## 不同文件类型策略

| 文件类型 | 默认策略 | 说明 |
| --- | --- | --- |
| TXT、MD、HTML、JSON | 当前解析器 | 成本低，结构简单 |
| DOCX | 当前解析器优先，复杂场景可进入 MinerU | 当前解析器已支持文本和部分图片挂载，但未做图片语义理解 |
| XLSX、XLS | 当前 Excel 解析优先 | 后续可补表格结构增强 |
| 普通文本 PDF | 当前解析器或 MinerU | 可按页数、是否扫描件、解析失败率动态选择 |
| 扫描 PDF | MinerU | 需要 OCR、阅读顺序和版面结构 |
| PNG、JPG、JPEG、WEBP、BMP、TIFF | MinerU | 输出 OCR 文本和图片块信息 |
| 图表、流程图、截图、照片 | MinerU + 多模态模型 | OCR 原文和视觉摘要共同入库 |

## 标准化数据模型

建议新增内部标准结构 `DocumentBlock`，作为所有解析器的统一输出。

```json
{
  "block_id": "string",
  "doc_id": "string",
  "source_file": "string",
  "page_idx": 1,
  "block_type": "text | title | table | equation | image | chart | screenshot | photo | visual_summary",
  "text": "可检索文本或 OCR 原文",
  "html": "可选，表格 HTML",
  "markdown": "可选，Markdown 表示",
  "bbox": [0, 0, 100, 100],
  "image_path": "可选，块裁剪图片路径",
  "confidence": 0.98,
  "is_model_inference": false,
  "metadata": {}
}
```

Chunk 生成时保留以下字段：

- `doc_id`
- `docnm`
- `page_num_int`
- `position_int`
- `block_type`
- `image_path`
- `parser_engine`
- `is_model_inference`

## 入库任务设计

图片和复杂文档解析不应放在同步上传请求中执行，建议走异步入库任务。

```text
上传文件
-> 创建 t_ingestion_task
-> 创建 parser 节点：pending
-> 后台 Worker 调 MinerU
-> 创建 normalize 节点
-> 创建 chunk 节点
-> 创建 embedding 节点
-> 创建 index 节点
-> 任务 success / failed
```

管理端入库任务详情需要展示：

- 原文件信息。
- 使用的解析引擎。
- 每个节点耗时。
- 解析后的块数量。
- OCR 失败或低置信度块数量。
- 多模态摘要调用次数。
- 入库 Chunk 数。
- 错误信息和可重试入口。

## 问答与引用设计

问答链路仍以文本检索为主，但引用结果需要支持图片和坐标。

回答引用应至少能展示：

- 文档名。
- 页码。
- Chunk 文本。
- block 类型。
- bbox 坐标。
- 如果有图片块，展示图片裁剪预览。
- 如果引用来自多模态摘要，明确标记“视觉摘要”。

Prompt 中需要区分参考内容来源：

```text
[OCR原文]
...

[表格内容]
...

[视觉摘要，模型推断]
...
```

生成规则：

- OCR 原文和结构化表格优先作为事实依据。
- 视觉摘要只能作为辅助理解。
- 当回答依赖视觉摘要时，应避免使用绝对化表述。

## 前端调整

用户端：

- 上传入口放开图片格式。
- 文件上传提示改为支持文档和图片。
- 解析中状态需要明确展示。
- 引用面板支持图片块预览和页码定位。

管理端：

- 文档列表展示解析引擎、解析状态、块类型统计。
- Chunk 下钻支持按 `block_type` 筛选。
- 入库任务详情展示 MinerU、OCR、多模态摘要节点。
- 低置信度 OCR 块支持人工查看和修订。

## 后端接口调整

建议新增或改造以下能力：

- `POST /api/ragent/ingestion/tasks/upload`：真实创建并触发入库任务。
- `GET /api/ragent/ingestion/tasks/{task_id}/nodes`：返回解析、切块、Embedding、写入节点。
- `GET /api/ragent/knowledge-base/docs/{doc_id}/blocks`：查看标准化解析块。
- `GET /api/ragent/knowledge-base/docs/{doc_id}/preview`：支持 Markdown、PDF 页面和图片块预览。
- `GET /api/ragent/knowledge-base/docs/{doc_id}/chunks`：返回 block metadata。

前台快速解析可新增轻量接口：

- `POST /quick_parse/image`
- 或扩展现有 `/quick_parse`，按文件类型分发到图片解析服务。

## 配置建议

在系统设置中增加解析配置：

```json
{
  "parsing": {
    "defaultEngine": "auto",
    "complexDocumentEngine": "mineru",
    "ocrFallbackEngine": "paddleocr",
    "enableVisionSummary": true,
    "visionSummaryModel": "qwen-vl",
    "maxImageCountPerDocument": 50,
    "minOcrConfidence": 0.6
  }
}
```

自动选择策略：

- 小文本文件走当前解析器。
- 图片和扫描 PDF 走 MinerU。
- MinerU 失败时可按配置降级到 PaddleOCR。
- 大文件或图片过多时限制多模态摘要数量。

## 分阶段落地

### 阶段一：图片和扫描 PDF 可入库

- 新增解析器抽象接口。
- 接入 MinerU CLI 或独立服务。
- 支持图片和扫描 PDF 解析为 `DocumentBlock`。
- 将 OCR 文本写入现有 Chunk 与 ES。
- 管理端能看到解析任务状态。

验收标准：

- PNG/JPG 图片中的文字能进入知识库并被问答召回。
- 扫描 PDF 能解析出可检索文本。
- 引用中能看到来源文件和页码或图片块信息。

### 阶段二：结构化文档增强

- 表格、公式、图表块保留结构化内容。
- Chunk metadata 保存 `block_type`、`bbox`、`image_path`。
- 管理端 Chunk 下钻支持块类型筛选。

验收标准：

- 表格内容不被打散成不可读文本。
- 公式以 LaTeX 进入检索内容。
- 图表或图片块可以在引用面板中预览。

### 阶段三：多模态语义增强

- 对 `image/chart/screenshot/photo` 块生成视觉摘要。
- 摘要与 OCR 原文一起入库，但标记 `is_model_inference=true`。
- Prompt 渲染区分 OCR 原文和视觉摘要。

验收标准：

- 用户能询问截图、流程图、图表中的含义。
- 回答能区分原文事实和视觉推断。
- Trace 能看到多模态摘要节点输入输出摘要。

### 阶段四：质量闭环

- 增加低置信度 OCR 审核。
- 增加解析失败重试。
- 增加解析引擎效果统计。
- 将失败样例沉淀到技术债和测试集。

## 风险与控制

| 风险 | 影响 | 控制方式 |
| --- | --- | --- |
| MinerU 本地推理资源消耗高 | 入库慢、占用 GPU/CPU | 独立 Worker 部署，限制并发，任务队列削峰 |
| 多模态摘要幻觉 | 回答混入不可靠推断 | 明确标记 `is_model_inference`，Prompt 中降低其事实优先级 |
| OCR 低置信度 | 检索和回答质量下降 | 保存 confidence，低于阈值时提示复核 |
| 表格结构解析错误 | 数字和字段错位 | 表格保留 HTML/Markdown，同时允许预览原图 |
| 文件类型复杂 | 解析分发不稳定 | 建立 parser registry 和统一错误码 |
| 引用体验变复杂 | 用户难以核验 | 引用面板按“原文、表格、图片块、视觉摘要”分区展示 |

## 与当前实现的关系

当前实现不需要立即废弃：

- `quick_parse_service.py` 可继续服务短文本临时问答。
- `file_parse.py` 和 `naive.chunk()` 可继续处理简单文本型文档。
- DeepDOC PDF 解析可作为现有兼容路径保留。
- 新方案优先接入图片、扫描 PDF 和复杂文档。

推荐最终形态：

```text
简单文本文件 -> 当前解析器
复杂 PDF / 扫描件 / 图片 -> MinerU
只需轻量 OCR 的图片 -> PaddleOCR fallback
图表 / 截图 / 照片 -> MinerU OCR + 多模态摘要
统一 DocumentBlock -> Chunk -> Embedding -> ES
```

## 后续执行建议

如果进入实施，应在 `docs/exec-plans/active/` 新增执行计划，并在 `docs/PLANS.md` 登记。

建议执行计划拆成四个任务：

1. 解析器抽象与 MinerU 服务接入。
2. 图片和扫描 PDF 入库链路。
3. 管理端任务状态与 Chunk metadata 展示。
4. 多模态视觉摘要与引用面板增强。
