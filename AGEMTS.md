# Agent Project Notes

## 项目概览

`rag_platform` 是一个前后端分离的智能文档问答系统（RAG 平台）。核心能力包括用户登录注册、知识库文件上传与向量化检索、单会话临时文档解析、基于 RAG 的流式问答、歧义检测与追问机制，以及**后台管理控制台**。管理端提供运营驾驶舱、动态意图树配置与大模型分类调试、用户管控、系统设置调节、全局知识库下钻审计、入库任务吞吐监控、全链路算子 Trace 可观测性，以及查询词映射和样例问题管理。

技术栈：

- 前端：React 18、TypeScript、Vite、Ant Design 5、Tailwind CSS 4、shadcn/ui (Radix UI)、Zustand + Valtio、react-hook-form + zod、Axios。
- 后端：FastAPI、SQLAlchemy、PostgreSQL 15、Elasticsearch 8.11.3、Redis 7、OpenAI 兼容接口（DashScope）。
- 文档处理：PDF/DOCX/TXT/Excel/PPT/HTML/Markdown/JSON 等解析能力在 `backend/app/service/core/deepdoc/parser/` 下，PDF 使用 DeepDOC 流程（OCR + 布局分析 + 表格识别）。
- 大模型：通过 DashScope API（OpenAI 兼容协议）调用，主要模型包括 `deepseek-r1`、`qwen2.5-72b-instruct`、`qwen2.5-7b-instruct`、`text-embedding-v3`（向量嵌入）、`gte-rerank-v2`（重排序）。

## 目录结构

- `frontend/`：前端 Vite 应用。
  - `src/router/routes.tsx`：前台路由（`/`、`/chat`、`/repository`、`/login`）及 `/admin` 管理端路由分支与角色守卫。
  - `src/pages/`：页面组件。
    - `chat/`：聊天主页面，含消息渲染、引用展示、追问卡片、文档抽屉。
    - `admin/`：管理控制台页面。
      - `AdminLayout.tsx`：管理端主布局与侧边栏。
      - `dashboard/DashboardPage.tsx`：运营驾驶舱。
      - `intent-tree/`：意图树配置（IntentTreePage / IntentListPage / IntentEditPage）。
      - `knowledge/`：全局知识库下钻（KnowledgeListPage → KnowledgeDocumentsPage → KnowledgeChunksPage）。
      - `ingestion/IngestionPage.tsx`：入库流水线任务监控。
      - `traces/`：RAG 链路 Trace 追踪（RagTracePage / RagTraceDetailPage）。
      - `users/UserListPage.tsx`：用户管理与角色/状态控制。
      - `settings/SystemSettingsPage.tsx`：系统参数与 RAG 模板可视化配置。
      - `query-term-mapping/QueryTermMappingPage.tsx`：查询词映射管理。
      - `sample-questions/SampleQuestionPage.tsx`：样例问题管理。
    - `login/`：登录页。
    - `repository/`：知识库文件管理页。
  - `src/services/`：管理端 API 服务层（intentTreeService、knowledgeService、ragTraceService 等）。
  - `src/store/` 和 `src/stores/`：状态管理（Valtio + Zustand）。
  - `src/components/ui/`：shadcn/ui 组件（button、dialog、table、form 等）。
  - `src/api/`：Axios 请求封装与插件（auth、error-toast、loading、repeat）。

- `backend/`：后端服务与 Docker Compose 编排目录。
  - `docker-compose.yml`：编排 swxy_api、es01、gsk_pg、redis、init_intents 服务。
  - `init.sql`：数据库初始化 DDL（14 张表）。
  - `app/app_main.py`：FastAPI 入口，注册前台与后台管理子路由，包含 `/api/ragent` 统一前缀兼容。
  - `app/router/`：HTTP API 路由。
    - `chat_rt.py`：聊天问答、知识库上传、快速解析、追问流程接口。
    - `user_rt.py`：注册、登录、STS Token。
    - `history_rt.py`：会话历史。
    - `intent_rt.py`：意图树配置 API。
    - `user_admin_rt.py`：后台用户管理 API。
    - `ragent_admin_rt.py`、`settings_rt.py`、`knowledge_admin_rt.py`、`ingestion_rt.py`、`trace_rt.py`、`dashboard_rt.py`：管理端各模块 API。
  - `app/service/`：业务逻辑层。
    - `core/`：核心 RAG 引擎。
      - `chat.py`：SSE 流式生成、Prompt 渲染、对话入库。
      - `retrieval.py` 和 `retrieval2.py`：检索入口封装。
      - `file_parse.py`：文件解析与入库管道。
      - `rag/`：RAG 底层（分词器、搜索、ES 连接、同义词、词权重、Embedding 批量生成）。
      - `deepdoc/`：文档解析器（PDF OCR、DOCX、Excel、PPT、HTML、Markdown、JSON 等）。
      - `session.py`：会话管理。
    - `auth.py`：JWT 鉴权、角色/状态验证、`require_admin` 依赖。
    - `intent_engine.py`：动态意图分类器（LLM 主路径 + 关键词兜底）。
    - `ambiguity_service.py`：歧义检测与追问生成（信息审计模式）。
    - `trace_service.py`：全链路 Trace 追踪（TraceTracker）。
    - `quick_parse_service.py`：快速解析服务（Redis 缓存）。
    - `settings_service.py`：系统设置加载。
    - `knowledge_sync.py`：旧知识库数据桥接同步。
  - `app/models/`：SQLAlchemy 模型（user、message、session、knowledgebase、intent、user_admin、trace、ingestion、system_config 等）。
  - `app/schemas/`：Pydantic 请求/响应模型。
  - `app/alembic/`：数据库迁移脚本。
  - `app/tests/`：单元测试（auth_admin、intent_engine、user_admin、settings 等）。

## 启动方式

后端：

```bash
cd backend
# 步骤1：修改 .env 文件中 DASHSCOPE_API_KEY
docker compose up -d --build
docker compose logs -f swxy_api
```

> [!WARNING]
> 请勿使用 `docker compose down -v`，该命令会删除 `pg_data` 卷，导致意图数据（`t_intent_node` 表）丢失。保持卷不被删除后，后续使用 `docker restart` 或 `docker compose restart` 即可保持数据持久化。

后端服务默认暴露：

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

前端：

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

前端默认访问 `http://localhost:5181/`。需要配置 `frontend/.env`，至少包含：

```env
VITE_API_BASE=http://localhost:8000
```

后端需要配置 `backend/.env`，可参考 `backend/.env.example`。关键变量：

- `DASHSCOPE_API_KEY`
- `DASHSCOPE_BASE_URL`
- `DATABASE_URL`
- `ES_HOST`
- `ELASTIC_PASSWORD`
- `MEM_LIMIT`
- `TIMEZONE`

Docker Compose 默认服务：

- `swxy_api`：FastAPI，端口 `8000`
- `gsk_pg`：PostgreSQL 15，数据库 `gsk`
- `gsk-es-01`：Elasticsearch 8.11.3
- `gsk_redis`：Redis 7

## 核心后端接口

### 1. 认证与基本功能

- `POST /register`：注册普通用户（默认 role=user, status=1）。
- `POST /login`：登录并返回 JWT（携带 user_id、role、status）。
- `POST /sts-token`：字节语音 STS 接口转发。
- `POST /create_session`：创建 16 位问答会话。
- `POST /chat_on_docs?session_id=...`：RAG 流式问答（SSE），包含意图分类、向量检索、歧义检测、追问、推荐问题。
- `GET /get_sessions`：获取当前用户会话列表。
- `POST /quick_parse?session_id=...`：单会话临时文档解析（内容写入 Redis，2 小时 TTL）。

### 2. 后台管理专用接口（受 `Depends(require_admin)` 权限保护）

- `GET /api/ragent/intent-tree/trees`：获取树形意图配置。
- `POST /api/ragent/intent-tree`：新增意图节点（Domain / Category / Topic 层级）。
- `PUT /api/ragent/intent-tree/{id}`：修改意图节点。
- `POST /api/ragent/intent-tree/batch/enable`：批量启用意图节点。
- `POST /api/ragent/intent-tree/batch/disable`：批量停用意图节点（含级联子树校验）。
- `GET /api/ragent/users`：分页获取用户列表。
- `POST /api/ragent/users`：管理员创建用户（bcrypt 密码哈希）。
- `PUT /api/ragent/users/{id}`：修改用户属性与 role。
- `DELETE /api/ragent/users/{id}`：逻辑删除用户（admin 账号禁止删除）。
- `GET /api/ragent/rag/settings`：获取 RAG 模型与系统配置。
- `GET /api/ragent/admin/dashboard/overview`：运营指标总览（用户数、会话/消息增长等）。
- `GET /api/ragent/knowledge-base`：全局知识库分页列表。
- `GET /api/ragent/knowledge-base/{kb_id}/docs`：知识库下文档列表与状态。
- `GET /api/ragent/knowledge-base/docs/{doc_id}/chunks`：文档 ES Chunk 分块详情。
- `DELETE /api/ragent/knowledge-base/docs/{doc_id}`：物理删除文档。
- `GET /api/ragent/rag/traces/runs`：分页获取 Trace 运行历史。
- `GET /api/ragent/rag/traces/runs/{trace_id}`：单次 Trace 的节点耗时与 JSON 输入输出。

## 数据流

### 知识库上传流程

1. 前端调用 `POST /upload_files`。
2. 后端保存文件到 `storage/file/{user_id}/`。
3. `execute_insert_process()` 解析 → 切块 → 分词 → 词权重 → 同义词扩展 → Embedding（text-embedding-v3，1024 维）。
4. 数据写入 Elasticsearch，索引名为 `user_id`。
5. 文件元信息写入 PostgreSQL `knowledgebases` 表。

### 临时文档解析流程（快速解析）

1. 前端聊天输入区上传文件，调用 `POST /quick_parse`。
2. 仅支持 `docx`、`pdf`、`txt`。
3. PDF 默认限制 4 页；TXT/DOCX 默认限制 4000 字符。
4. 使用轻量解析器（pdfplumber / python-docx），结果写入 Redis（key=session_id，2 小时 TTL）。
5. `/chat_on_docs` 自动将 Redis 中该会话的临时文档内容加入 prompt。

### 聊天与意图路由流程

1. 前端发起对 `/chat_on_docs` 的 SSE 流式请求。
2. 后端鉴权后加载系统设置（prompt 模板、top_k、模型选择）。
3. 若 `deepThinking=true`，切换为深度思考模型。
4. `IntentRouter.decide()`：用 `qwen2.5-7b-instruct` 对问题做意图匹配（最多 80 个候选意图），失败时用关键词兜底。
5. 向量检索：`retrieve_content()` → `Dealer.retrieval()` 混合检索（BM25 文本 + KNN 向量，向量权重 60%），top 128 → `gte-rerank-v2` 重排序 → 取 top_k 条。
6. 歧义检测：`check_draft_and_clarify()` 信息审计模式——先列必需参数，再对比用户已提供信息，缺失参数时生成追问（最多 3 个）通过 SSE `clarify` 事件推送给前端。
7. 追问流程：用户填写追问答案后携带 `clarifications` + `original_question` 再次请求，`merge_clarifications()` 合并后重新检索并跳过歧义检测。
8. 合并 Redis 临时文档内容，渲染 Prompt 模板，调用 LLM 流式生成。
9. SSE 事件类型：`message`（含 content/thinking/documents/recommended_questions）、`clarify`、`end`、`error`。
10. 回答完成后生成推荐问题（`qwen2.5-7b-instruct`），首次对话生成会话名，写入 `messages` 表。

### 管理员鉴权与越权拦截

1. 管理员登录后 JWT 包含 `role: "admin"`。
2. 前端路由守卫 `AdminRoute` 检查 `authStore` 的 role，非 admin 重定向至首页。
3. 后端管理接口 `/api/ragent/*` 使用 `Depends(require_admin)` 依赖，校验 status=1 且 role=admin。
4. 不满足条件返回 403 Forbidden。

## 数据库表

| 表名 | 描述 |
| :--- | :--- |
| `users` | 前台用户表，含 role（默认 `user`）、status（1 启用/0 禁用）、deleted 字段 |
| `sessions` | 前台会话表（session_id、session_name、user_id） |
| `messages` | 对话消息表（question、answer、documents、recommended_questions、think） |
| `knowledgebases` | 知识库文件元数据表 |
| `document_uploads` | 单会话临时文档上传记录表 |
| `t_user` | 旧版后台用户表（兼容保留） |
| `t_intent_node` | 动态意图树节点配置表（层级、kb 绑定、MCP 工具 ID、启用状态、prompt 模板等） |
| `t_system_config` | 系统配置键值表（prompt 模板、模型参数、top_k 等） |
| `t_knowledge_base` | 管理端知识库表 |
| `t_knowledge_document` | 管理端知识库文档表（状态、chunk 策略、调度配置） |
| `t_ingestion_pipeline` | 入库流水线定义表（nodes_json） |
| `t_ingestion_task` | 入库任务表（状态、错误信息、chunk 数量） |
| `t_ingestion_task_node` | 入库任务节点执行记录表 |
| `t_knowledge_document_chunk_log` | 文档切块日志表（各阶段耗时统计） |
| `t_rag_trace_run` | RAG 链路 Trace 运行表（trace_id、状态、TTFT、耗时） |
| `t_rag_trace_node` | RAG 链路 Trace 节点表（节点类型、输入输出 JSON、耗时） |

> [!NOTE]
> `init.sql` 与 Alembic 迁移同时存在。修改表结构时须同步更新 Alembic 迁移脚本和 `init.sql`，确保全新容器部署时表结构对齐。

## 开发注意事项

- 根目录是 Git 仓库；改动前先执行 `git status --short`。
- `frontend/node_modules/` 已存在，搜索文件时排除依赖目录。
- 后端 `.env` 可能含真实密钥，不要把密钥写入文档、日志或提交。
- 管理后台新增接口必须使用统一响应实体 `Result<T>`（`utils.response.success_result` 封装），HTTP code 200，JSON 内 `code: "0"` 表示业务成功。
- 意图节点停用/删除等批量操作时须校验子树节点状态，避免父级停用导致子节点成为启用孤儿节点。
- 管理控制台与 Chat 聊天主界面样式做了模块化 CSS 隔离。
- 部署新数据库或新增迁移后，运行 `docker compose exec swxy_api alembic upgrade head`。
- **聊天主界面滚动**：主内容区域采用独立容器级高度滚动（`height: 100vh; overflow: hidden;`），不再随全局 window 滚动。
- **聊天输入框**：`Enter` 发送、`Shift + Enter` 换行。
- **前端引用格式**：后端拼接 `##N$$ content`，前端正则匹配 `##N$$` 渲染为可点击引用徽章。

## 常用验证

后端单元测试：

```bash
cd backend
python -m unittest discover -s app/tests
```

后端服务状态与日志：

```bash
cd backend
docker compose ps
docker compose logs -f swxy_api
curl http://localhost:8000/docs
```

前端：

```bash
cd frontend
npm run lint
npm run build
```

## 核心文档

- [链路分析.md](./链路分析.md)：RAG 平台文档解析与问答全链路技术分析。
- [问答链路流程图.md](./问答链路流程图.md)：Mermaid 流程图形式的问答链路详解，含歧义检测与追问机制。

## 待优化项

1. PDF 中图片识别与文字内容提取。
2. 知识库的增量更新与过期淘汰机制。
3. RAG 知识库跨用户的细粒度文件权限管理。
4. 意图路由层未使用 `INTENT_KIND_SYSTEM` 和 `INTENT_KIND_MCP` 分支，所有意图目前统一走知识库检索。
5. `retrieval.py` 的 `vector_similarity_weight=0.6` 与 `search_v2.py` 内部 `weights="0.05, 0.95"` 存在不一致。
6. PDF DeepDOC 流程使用 ONNX Runtime 本地推理，适合高精度场景但速度较慢。
7. 快速解析的文档仅存 Redis 2 小时，不入知识库，会话结束后不可复用。
