# 系统架构

更新时间：2026-06-15

## 项目概览

`rag_platform` 是一个智能文档问答系统，采用前后端分离架构。前端提供用户问答界面、知识库文件管理和后台管理控制台；后端负责鉴权、文档解析、向量检索、意图分类、歧义追问、LLM 流式生成、Trace 记录和管理端 API。

整体链路：

```text
React/Vite 前端 -> FastAPI 后端 -> PostgreSQL / Elasticsearch / Redis -> DashScope OpenAI 兼容接口
```

## 技术栈

- 前端：React 18、TypeScript、Vite 6、Ant Design 5、Tailwind CSS 4、shadcn/ui、Radix UI、Zustand、Valtio、Axios。
- 后端：FastAPI、SQLAlchemy、PostgreSQL 15、Elasticsearch 8.11.3、Redis 7、Alembic。
- 文档解析：PDF、DOCX、TXT、Excel、PPT、HTML、Markdown、JSON；复杂 PDF 使用 DeepDOC 流程。
- 大模型：通过 DashScope 的 OpenAI 兼容协议调用聊天、意图分类、推荐问题、Embedding 与重排序模型。

## 目录结构

```text
.
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
├── backend/
│   ├── docker-compose.yml
│   ├── init.sql
│   └── app/
│       ├── app_main.py
│       ├── router/
│       ├── service/
│       ├── models/
│       ├── schemas/
│       ├── alembic/
│       └── tests/
├── frontend/
│   ├── package.json
│   └── src/
│       ├── pages/
│       ├── components/
│       ├── services/
│       ├── api/
│       ├── router/
│       ├── store/
│       └── stores/
├── docs/
│   ├── DESIGN.md
│   ├── PLANS.md
│   ├── design-docs/
│   └── exec-plans/
└── plan/
```

## 前端结构

- `frontend/src/router/`：前台与管理端路由，包含管理员路由守卫。
- `frontend/src/pages/chat/`：主问答页，负责消息渲染、引用展示、追问卡片、文档抽屉和流式输出承接。
- `frontend/src/pages/repository/`：普通用户知识库文件管理。
- `frontend/src/pages/admin/`：管理控制台。
  - `dashboard/`：运营指标。
  - `intent-tree/`：动态意图树配置。
  - `knowledge/`：管理端知识库、文档、Chunk 下钻。
  - `ingestion/`：入库流水线与任务监控。
  - `traces/`：RAG Trace 列表、详情和会话维度追踪。
  - `users/`：用户与角色状态管理。
  - `settings/`：系统配置、RAG Prompt、模型参数。
  - `query-term-mapping/`：查询词映射。
  - `sample-questions/`：样例问题。
- `frontend/src/services/`：前端服务层，封装管理端和业务 API。
- `frontend/src/api/request/`：Axios 请求封装与鉴权、错误、加载、重复请求插件。

## 后端结构

- `backend/app/app_main.py`：FastAPI 入口，注册前台路由和 `/api/ragent` 管理端兼容前缀。
- `backend/app/router/`：HTTP API。
  - `chat_rt.py`：聊天、上传、快速解析、追问流程。
  - `user_rt.py`：注册、登录、STS Token。
  - `history_rt.py`：会话历史。
  - `intent_rt.py`：意图树配置。
  - `settings_rt.py`：系统设置。
  - `knowledge_admin_rt.py`：管理端知识库。
  - `ingestion_rt.py`：入库任务。
  - `trace_rt.py`：链路 Trace。
  - `dashboard_rt.py`：运营指标。
  - `user_admin_rt.py`：后台用户管理。
- `backend/app/service/`：业务逻辑。
  - `core/chat.py`：Prompt 渲染、临时文档合并、LLM 流式生成、推荐问题、会话写库。
  - `core/retrieval.py`、`core/retrieval2.py`：检索入口。
  - `core/file_parse.py`：正式入库解析管道。
  - `core/rag/`：分词、同义词、词权重、搜索、ES 连接、Embedding。
  - `core/deepdoc/`：文档解析器和 OCR/布局识别相关能力。
  - `intent_engine.py`：意图分类与系统/MCP 意图能力。
  - `ambiguity_service.py`：歧义审计和追问合并。
  - `trace_service.py`：Trace run/node 记录。
  - `quick_parse_service.py`：单会话临时文档解析和 Redis 缓存。
  - `settings_service.py`：系统配置加载与默认 RAG Prompt。
  - `knowledge_sync.py`：旧知识库数据同步到管理端结构。
- `backend/app/models/`：SQLAlchemy 模型。
- `backend/app/schemas/`：Pydantic 请求/响应模型。
- `backend/app/alembic/`：数据库迁移。
- `backend/app/tests/`：后端单元测试。

## 核心链路

### 知识库正式上传

```text
文件上传 -> 保存磁盘 -> execute_insert_process()
-> 解析 -> 切块 -> 分词/词权重/同义词 -> Embedding
-> Elasticsearch 写入 -> PostgreSQL 元数据写入
```

关键点：

- 入口主要在 `backend/app/router/chat_rt.py`。
- DeepDOC PDF 流程包含 OCR、布局分析、表格识别和文本合并。
- Elasticsearch 索引按用户或会话维度隔离。
- 管理端知识库结构通过同步逻辑补齐。

### 单会话快速解析

```text
文件上传 -> QuickParseService -> Redis(session_id, 2 小时 TTL)
```

约束：

- 支持 PDF、DOCX、TXT。
- PDF 默认限制页数，DOCX/TXT 默认限制字符数。
- 不写入 Elasticsearch，不进入正式知识库。
- `/chat_on_docs` 生成回答时会合并该会话 Redis 中的临时文档内容。

### 问答链路

```text
用户问题
-> 鉴权与加载系统设置
-> 意图分类
-> 向量/文本混合检索
-> 重排序
-> 歧义审计与追问
-> 合并临时文档
-> Prompt 渲染
-> LLM SSE 流式生成
-> 推荐问题
-> 会话与消息入库
-> Trace 记录
```

当前 Trace 主要记录 `IntentClassify`、`VectorRetrieve`、`LLMCall` 节点。歧义命中时，run 状态会标记为 `clarify_needed`。

## 关键接口

前台接口：

- `POST /register`
- `POST /login`
- `POST /sts-token`
- `POST /create_session`
- `GET /get_sessions`
- `POST /upload_files`
- `POST /quick_parse?session_id=...`
- `POST /chat_on_docs?session_id=...`

管理端接口统一挂在 `/api/ragent/*`，并通过 `Depends(require_admin)` 保护：

- `/api/ragent/intent-tree/*`
- `/api/ragent/users/*`
- `/api/ragent/rag/settings`
- `/api/ragent/admin/dashboard/overview`
- `/api/ragent/knowledge-base/*`
- `/api/ragent/ingestion/*`
- `/api/ragent/rag/traces/*`

## 数据存储

- PostgreSQL：用户、会话、消息、知识库元数据、管理端知识库、意图树、系统配置、入库任务、Trace run/node。
- Elasticsearch：知识库 Chunk、向量、分词字段和检索元数据。
- Redis：快速解析文档临时内容和部分运行时缓存。

主要表：

| 表名 | 用途 |
| --- | --- |
| `users` | 前台用户 |
| `sessions` | 会话 |
| `messages` | 对话消息 |
| `knowledgebases` | 前台知识库文件元数据 |
| `document_uploads` | 单会话临时文档上传记录 |
| `t_user` | 旧版后台用户兼容表 |
| `t_intent_node` | 动态意图树节点 |
| `t_system_config` | 系统配置 |
| `t_knowledge_base` | 管理端知识库 |
| `t_knowledge_document` | 管理端知识库文档 |
| `t_ingestion_pipeline` | 入库流水线定义 |
| `t_ingestion_task` | 入库任务 |
| `t_ingestion_task_node` | 入库任务节点记录 |
| `t_knowledge_document_chunk_log` | 文档切块日志 |
| `t_rag_trace_run` | RAG Trace 运行记录 |
| `t_rag_trace_node` | RAG Trace 节点记录 |

## 当前实现约束

- `IntentRouter.decide()` 当前仍统一返回知识库检索路线，系统意图和 MCP 意图的流式响应能力已存在但尚未接入主聊天链路。
- `retrieval.py` 的向量权重参数与 `search_v2.py` 内部融合权重存在不一致，需要统一口径。
- DeepDOC PDF 解析精度较高但本地推理成本较大。
- 快速解析文档仅在 Redis 中保留 2 小时，不可跨会话复用。
- 前端启用了严格 TypeScript 校验，提交前需要处理未使用 import 和类型问题。

## 启动方式

后端：

```bash
cd backend
docker compose up -d --build
docker compose logs -f swxy_api
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认访问：

- 前端：`http://localhost:5181/`
- 后端 API：`http://localhost:8000`
- Swagger：`http://localhost:8000/docs`

## 验证命令

后端单元测试：

```bash
cd backend
python -m unittest discover -s app/tests
```

前端：

```bash
cd frontend
npm run lint
npm run build
```

