# Agent Project Notes

## 项目概览

`swxy` 是一个前后端分离的智能文档问答系统。核心能力除了面向用户的登录注册、知识库文件上传与检索、单会话临时文档解析、基于 RAG 的流式问答外，还整合了 **后台管理控制台** 能力。管理端提供可视化运营驾驶舱、多级意图树配置与大模型分类调试、用户管控、系统设置调节、全局知识库下钻审计、入库任务吞吐监控以及全链路算子 Trace 可观测性。

技术栈：

- 前端：React 18、TypeScript、Vite、Ant Design、Valtio、Axios。
- 后端：FastAPI、SQLAlchemy、PostgreSQL、Elasticsearch、Redis、OpenAI 兼容接口。
- 文档处理：PDF/DOCX/TXT/Excel/PPT/HTML/Markdown 等解析能力主要在 `backend/app/service/core` 下。
- 大模型：通过 DashScope 兼容 OpenAI SDK 调用，主要模型包括 `deepseek-r1`、`qwen2.5-72b-instruct`、`qwen2.5-7b-instruct`。

## 目录结构

- `frontend/`：前端 Vite 应用。
  - [routes.tsx](file:///d:/03_Projects/ai_agent/s2/swxy/frontend/src/router/routes.tsx)：包含前台路由及 `/admin` 分支路由定义与角色守卫。
  - `frontend/src/pages/admin/`：管理控制台各个功能页。
    - `AdminLayout.tsx`：管理端主布局与侧边栏。
    - `dashboard/`：运营驾驶舱，宏观 KPI 与趋势监控。
    - `intent-tree/`：动态意图树配置界面（Domain -> Category -> Topic 节点增删改查及批量启用/禁用）。
    - `knowledge/`：全局知识库下钻（全系统知识库 -> 文档列表 -> 物理分块 Chunk 审计）。
    - `ingestion/`：文件上传解析流水线性能看板与任务队列监控。
    - `traces/`：分布式 RAG 链路算子执行耗时与 JSON 输入输出的追踪分析。
    - `users/`：系统用户表格及状态控制、批量禁启用。
    - `settings/`：系统全局参数、大模型温度及 RAG 模板的可视化配置。
- `backend/`：后端服务与 Docker Compose 编排目录。
  - [app_main.py](file:///d:/03_Projects/ai_agent/s2/swxy/backend/app/app_main.py)：FastAPI 服务入口，注册并拦截后台管理相关的子路由，包含 `/api/ragent` 统一前缀路由兼容。
  - `backend/app/router/`：HTTP API 路由。
    - [user_admin_rt.py](file:///d:/03_Projects/ai_agent/s2/swxy/backend/app/router/user_admin_rt.py)：后台用户管理 API 路由，面向管理端用户表。
    - [intent_rt.py](file:///d:/03_Projects/ai_agent/s2/swxy/backend/app/router/intent_rt.py)：后台动态意图树配置 API 路由。
    - [ragent_admin_rt.py](file:///d:/03_Projects/ai_agent/s2/swxy/backend/app/router/ragent_admin_rt.py)：系统设置、仪表盘性能、全局知识库详情、追踪等管理 API 路由。
  - `backend/app/service/`：业务逻辑实现。
    - [auth.py](file:///d:/03_Projects/ai_agent/s2/swxy/backend/app/service/auth.py)：支持将 `role` 与 `status` 写入 JWT，并提供管理员拦截依赖项 `require_admin`。
    - [intent_engine.py](file:///d:/03_Projects/ai_agent/s2/swxy/backend/app/service/intent_engine.py)：加载动态意图数据，调用 LLM 对用户请求进行意图匹配打分的分类器实现。
  - `backend/app/models/`：SQLAlchemy 模型。
    - [user.py](file:///d:/03_Projects/ai_agent/s2/swxy/backend/app/models/user.py)：包含前台 `User` 模型，新增角色 `role` 与状态 `status` 字段。
    - [user_admin.py](file:///d:/03_Projects/ai_agent/s2/swxy/backend/app/models/user_admin.py)：管理后台 `UserAdmin` 用户库模型。
    - [intent.py](file:///d:/03_Projects/ai_agent/s2/swxy/backend/app/models/intent.py)：意图节点数据库模型 `IntentNode`。
  - `backend/app/alembic/`：包含新字段及新表升级的数据库迁移脚本。

## 启动方式

后端：

```bash
cd backend
docker compose up -d --build
docker compose logs -f swxy_api
```
> [!WARNING]
> 请勿使用 `docker-compose down -v`，该命令会删除 `pg_data` 卷，导致意图数据（`t_intent_node` 表）丢失。保持卷不被删除后，后续使用 `docker restart` 或 `docker-compose restart` 即可保持数据持久化。
```

后端服务默认暴露：

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

前端：

```bash
cd frontend
npm install
npm run dev
```

前端默认访问：

- `http://localhost:5181/`

前端需要配置 `frontend/.env`，至少包含：

```env
VITE_API_BASE=http://localhost:8000
```

后端需要配置 `backend/.env`，可参考 `backend/.env.example`。关键变量包括：

- `DASHSCOPE_API_KEY`
- `DASHSCOPE_BASE_URL`
- `DATABASE_URL`
- `ES_HOST`
- `ELASTIC_PASSWORD`
- `MEM_LIMIT`
- `TIMEZONE`

Docker Compose 内部默认使用：

- `swxy_api`: FastAPI，端口 `8000`
- `gsk_pg`: PostgreSQL，数据库 `gsk`
- `gsk-es-01`: Elasticsearch 8.11.3
- `gsk_redis`: Redis 7

## 核心后端接口

### 1. 认证与基本功能

- `POST /register`：注册普通用户。
- `POST /login`：登录系统，验证 `status` 字段，并在生成的 JWT Payload 中携带用户 `role`。
- `POST /sts-token`：转发调用字节语音 STS 接口。
- `POST /create_session`：创建 16 位问答会话。
- `POST /chat_on_docs?session_id=...`：文档问答（含意图分类匹配元数据写入，返回 SSE 流）。
- `GET /get_sessions`：获取当前用户会话。
- `POST /quick_parse?session_id=...`：单会话临时解析当前文档（内容写入 Redis）。

### 2. 后台管理专用接口（受 `Depends(require_admin)` 权限验证保护）

- `GET /api/ragent/intent-tree/trees`：获取树形意图配置大盘。
- `POST /api/ragent/intent-tree`：新增意图树节点（支持 Domain, Category, Topic 等层级）。
- `PUT /api/ragent/intent-tree/{id}`：修改意图节点配置。
- `POST /api/ragent/intent-tree/batch/enable`：批量启用意图节点。
- `POST /api/ragent/intent-tree/batch/disable`：批量停用意图节点（包含级联子树节点验证校验）。
- `GET /api/ragent/users`：分页获取管理后台系统的用户。
- `POST /api/ragent/users`：管理员创建用户（密码采用 `bcrypt` 安全哈希）。
- `PUT /api/ragent/users/{id}`：修改用户基本属性和 `role`。
- `DELETE /api/ragent/users/{id}`：逻辑删除用户（内置 `admin` 禁止删除）。
- `GET /api/ragent/rag/settings`：获取系统当前 RAG 模型和配置大盘。
- `GET /api/ragent/admin/dashboard/overview`：获取系统运营指标总览（总用户数、24小时会话增长、消息增长等）。
- `GET /api/ragent/knowledge-base`：全局视角分页获取用户知识库列表。
- `GET /api/ragent/knowledge-base/{kb_id}/docs`：下钻查看某个用户知识库的文档列表与状态。
- `GET /api/ragent/knowledge-base/docs/{doc_id}/chunks`：进一步查看特定文档在 Elasticsearch 中切出的 Chunk 分块与相似度。
- `DELETE /api/ragent/knowledge-base/docs/{doc_id}`：物理删除用户冗余/违规文档。
- `GET /api/ragent/rag/traces/runs`：分页获取 RAG 链路请求分析历史。
- `GET /api/ragent/rag/traces/runs/{trace_id}`：获取单次对话的算子耗时图谱（Jaeger 风格）及具体节点的 JSON 输入输出。

## 数据流

### 知识库上传流程

1. 前端 `repository.upload()` 调用 `/upload_files`。
2. 后端保存文件到 `storage/file/{session_id或user_id}/`。
3. `execute_insert_process()` 解析、切片、生成 embedding。
4. 数据写入 Elasticsearch，索引名通常使用 `user_id` 或 `session_id`。
5. 文件名写入 PostgreSQL `knowledgebases` 表。

### 临时文档解析流程

1. 前端聊天输入区上传文件，调用 `/quick_parse`。
2. 后端仅支持 `docx`、`pdf`、`txt`。
3. PDF 默认限制 4 页；TXT/DOCX 默认限制 4000 字符。
4. 解析结果写入 Redis，key 为 `session_id`，默认过期 2 小时。
5. `/chat_on_docs` 会自动把 Redis 中该会话的临时文档内容加入 prompt。

### 聊天与意图路由流程

1. 前端 `api.session.chat()` 发起对 `/chat_on_docs`（或 `/api/ragent/chat_on_docs`）的 SSE 聊天请求。
2. 后端问答控制器获取用户输入，调用 [intent_engine.py](file:///d:/03_Projects/ai_agent/s2/swxy/backend/app/service/intent_engine.py) 的 `IntentRouter.decide()` 方法。
3. 意图分类器加载数据库中启用且有效的 `t_intent_node` 列表，使用轻量级 LLM 对输入进行打分分类。
4. 获得命中意图的 `intent_code`、置信度得分及分类缘由。若大模型匹配失败，使用关键词等降级兜底逻辑。
5. 结果作为命中元数据（Meta）随 SSE 输出回传前端，并保存至数据库供日志审计，当前版本暂不根据意图改变物理检索执行路径。
6. 后端继续读取 Elasticsearch 知识库和 Redis 会话临时文档，拼装 Prompt 调用 DashScope，通过 SSE 流式推送答案。
7. 对话完成后写入数据库中。

### 管理员鉴权与越权拦截流

1. 管理员通过前端登录页面登录，调用 `/login` 成功后获取 JWT。JWT Token 中包含声明的账号角色 `role: "admin"`。
2. 管理员在主界面点击“管理控制台”，前端 [routes.tsx](file:///d:/03_Projects/ai_agent/s2/swxy/frontend/src/router/routes.tsx) 路由守卫检查本地 `authStore` 的 `role`。若不为 `admin`，则拦截重定向至前台聊天室。
3. 当前端向管理接口 `/api/ragent/*` 发起请求时，后端使用拦截器依赖 [auth.py](file:///d:/03_Projects/ai_agent/s2/swxy/backend/app/service/auth.py) 中的 `require_admin`。
4. 后端解析 JWT，校验该用户在数据库中的 `status` 是否为 1 且 `role` 是否为 `admin`。若不满足，直接返回 403 Forbidden，防止水平和垂直越权。

## 数据库表

| 表名 | 描述 |
| :--- | :--- |
| `users` | 前台用户账号和密码哈希，新增 `role`（权限角色，默认 `user`）和 `status`（账号状态：`1` 启用，`0` 禁用）字段 |
| `t_user` | 后台管理端用户记录表，支持逻辑删除 `deleted` |
| `t_intent_node` | 动态意图树节点配置表，记录树级关联、所绑知识库/分类名称、MCP工具 ID、是否启用、描述及示例等信息 |
| `sessions` | 前台会话记录表，存储会话 ID、用户 ID 和自动生成的会话名 |
| `messages` | 对话消息记录表，包含用户问题、模型回答、来源引用、深度思考内容、推荐问题等 |
| `knowledgebases` | 全局知识库文档元数据表 |
| `document_uploads` | 单个会话中临时文件的上传记录表 |

> [!NOTE]
> `init.sql` 与 Alembic 迁移同时存在。修改任何表结构（例如 `users` 新增字段，新增 `t_intent_node` 表）时，必须同时编写 Alembic 迁移脚本并升级 `init.sql`，以保证单测及全新容器部署时表结构对齐。

## 开发注意事项

- 根目录当前不是 Git 仓库；`backend/` 是独立 Git 仓库，改动前先执行 `git -C backend status --short`。
- `frontend/node_modules/` 已存在，搜索文件时排除依赖目录，优先使用 `rg -g '!**/node_modules/**'`。
- 后端 `.env` 可能含真实密钥，不要把密钥写入文档、日志或提交。
- 现有 README 和部分源码注释在 PowerShell 输出中显示乱码，疑似编码不一致；修改中文文案前确认文件实际编码。
- 管理后台相关的新增接口必须严格使用统一响应实体 `Result<T>` （由 `utils.response.success_result` 封装），确保 HTTP code 为 200，JSON 内 `code: "0"` 表示业务成功。
- 在对意图节点进行停用、删除等批量操作时，应严密校验子树节点状态，避免由于停用父级节点而导致子节点成为启用孤儿节点的异常状态。
- 管理控制台与 Chat 聊天主界面样式做了模块化 CSS 隔离，避免 Tailwind 或三方组件库的样式污染公共聊天主页。
- 部署新数据库或新增迁移时，记得运行 `docker compose exec swxy_api alembic upgrade head`。
- **聊天主界面滚动与输入优化**：
  - 聊天主内容区域（`.com-page-layout__main-content`）采用独立的容器级高度滚动（`height: 100vh; overflow: hidden;`），并在其右侧（与右侧引文/文档面板相接处）提供美化滚动条，不再随全局浏览器 `window` 滚动，消除了多列滚动条交叠及操纵冲突。
  - 聊天输入框 `ComSender` 绑定了键盘监听，只按下 `Enter` 键即可发送问题；使用 `Shift + Enter` 可以正常在输入框中换行输入。

## 常用验证

运行后端鉴权与管理拦截单元测试：

```bash
# 进入后端工作目录，执行单元测试
cd backend
python -m unittest discover -s app/tests
```

后端服务容器状态与日志：

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

# 待优化项
1. pdf 中图片识别 加文字内容提取。
2. 考虑知识库的增量更新与过期淘汰机制，确保知识的时效性。
3. 细化 RAG 知识数据库跨用户的细粒度文件权限管理。

