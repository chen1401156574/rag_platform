# 前后端框架与实现体系收敛计划

状态：阶段完成，观察中

来源材料：2026-06-16 前后端框架重复排查结论。

## 背景

当前项目主架构仍是前后端分离：前端是 `React + Vite + React Router`，后端是 `FastAPI + Uvicorn`。排查未发现需要把前后端迁移到单一全栈框架的必要性。

真正的问题集中在同一主框架内部的并行体系：

- 前端普通用户侧偏旧体系：Ant Design、Valtio、`src/api/request` 插件式 Axios。
- 前端管理端偏新体系：shadcn/Radix、Tailwind、Zustand、`src/services/api` Axios。
- 后端统一运行在 FastAPI，但存在 `ragent_admin_rt.py` 与专门管理端 router 的接口重叠。
- RAG 检索存在当前主路径 `retrieval.py -> search_v2.py` 与旧实验路径 `retrieval2.py`。

如果继续并行演进，新增功能会面临认证状态、请求错误处理、接口协议、UI 组件和检索参数多处重复维护，排障成本会持续上升。

## 目标

- 保留前后端分离架构，不迁移到单一全栈框架。
- 前端收敛为一套认证状态、一套请求客户端、一套状态管理主路径。
- 前端建立项目级 UI 组件入口，降低 Ant Design 与 shadcn/Radix 混用带来的页面割裂。
- 后端收敛为一套 `/api/ragent/*` 管理端 API 实现，删除或降级重复兼容 router。
- 后端收敛为一条检索主路径，并统一检索权重、top_k、rerank 等配置口径。
- 收敛过程保持线上接口兼容，避免一次性大改影响用户端 Chat 与管理端排障能力。

## 范围

- 前端请求层：`frontend/src/services/api.ts`、`frontend/src/api/request/`、`frontend/src/api/`、`frontend/src/services/`。
- 前端状态层：`frontend/src/stores/`、`frontend/src/store/`、登录态与 Token 存储工具。
- 前端 UI 层：`frontend/src/components/ui/`、`frontend/src/components/common/`、Ant Design 使用集中点、管理端页面与用户端关键组件。
- 后端 API 层：`backend/app/app_main.py`、`backend/app/router/ragent_admin_rt.py`、各专门管理端 router。
- 后端检索层：`backend/app/service/core/retrieval.py`、`backend/app/service/core/retrieval2.py`、`backend/app/service/core/rag/nlp/search_v2.py`、系统设置服务。
- 文档与技术债：`ARCHITECTURE.md`、`docs/DESIGN.md`、`docs/PLANS.md`、`docs/exec-plans/tech-debt-tracker.md` 中相关事实与状态。

## 非目标

- 不把 Python 后端迁移到 Node.js、Next.js、NestJS 或其他全栈/后端框架。
- 不把 RAG、DeepDOC、ONNX、Elasticsearch、文档解析能力迁出 Python 生态。
- 不在第一阶段重写 Chat 主交互。
- 不在第一阶段强行删除所有 Ant Design 或所有 shadcn/Radix 组件。
- 不改变管理端接口必须挂在 `/api/ragent/*` 且受 `require_admin` 保护的约束。

## 实施步骤

### 第一阶段：冻结新增分叉

- 明确新增前端 API 只走一个请求客户端，优先选择 `frontend/src/services/api.ts` 作为统一入口。
- 明确新增认证状态只写入一套存储结构，优先选择 Zustand 作为主状态管理。
- 新增管理端接口只写入专门 router，不再向 `ragent_admin_rt.py` 增加新业务实现。
- 标记 `retrieval2.py` 为旧实验路径，禁止新增业务引用。

### 第二阶段：请求与认证收敛

- 梳理 `frontend/src/api/` 中旧前台接口，迁移到 `frontend/src/services/` 或统一的业务 API 分层。
- 将 `src/api/request` 插件能力中仍有价值的部分合入统一 Axios 客户端：鉴权、错误提示、重复请求控制、响应解包。
- 统一 Token 读写、401 跳转和业务 `code !== "0"` 处理逻辑。
- 将用户端、管理端登录态读取统一到同一套工具和状态源。

### 第三阶段：状态管理收敛

- 将 `frontend/src/store/user.ts` 中的用户登录态迁移到 `frontend/src/stores/authStore.ts`。
- 评估 `session.ts`、`device.ts` 是否继续需要全局状态；确需保留时迁移到 Zustand，否则改为局部状态或工具函数。
- 移除不再使用的 Valtio 持久化封装和相关依赖。

### 第四阶段：UI 体系收敛

- 建立项目级组件使用规则：页面优先从 `components/ui`、`components/common` 或业务组件入口取用，不直接散落引用多个基础库。
- 对管理端保留工作台风格，优先信息密度、筛选、对比、下钻和复制操作。
- 对用户端 Chat 保留阅读流畅、引用清楚、追问自然的体验约束。
- 在组件迁移稳定后，再决定底层长期统一到 Ant Design 还是 shadcn/Radix；未决定前不做大规模视觉重写。

### 第五阶段：后端 API 收敛

- 对比 `ragent_admin_rt.py` 与 `knowledge_admin_rt.py`、`dashboard_rt.py`、`ingestion_rt.py`、`trace_rt.py`、`settings_rt.py` 的重复路径。
- 保留专门 router 中更完整、更接近真实业务表结构的实现。
- 对需要兼容的旧路径增加薄转发或明确弃用说明，避免同一路径双实现。
- 删除无调用的占位接口或简化实现，确保 `/api/ragent/*` 权限保护不回退。

### 第六阶段：RAG 检索路径收敛

- 确认聊天主链路只通过 `retrieval.py -> search_v2.py` 进入检索。
- 删除或归档 `retrieval2.py`，同时清理其中的默认敏感值风险。
- 将 `vector_similarity_weight`、融合权重、top_k、similarity threshold、rerank 开关接入统一系统配置。
- 在 Trace 中记录最终生效的检索参数，便于召回质量排查。

## 验收标准

- 前端只保留一套主请求客户端，普通用户侧和管理端错误处理、鉴权、响应解包一致。
- 前端登录态只保留一套主状态源，不再同时维护 Valtio 用户态和 Zustand 用户态。
- 新增业务页面不直接引入多套基础组件库，而是通过项目级组件入口使用。
- `ragent_admin_rt.py` 不再承载与专门 router 重叠的真实业务实现。
- 管理端接口仍统一挂在 `/api/ragent/*`，并通过 `require_admin` 保护。
- RAG 主链路只有一条检索入口，旧检索实验文件不再参与运行。
- 检索参数在系统配置、检索执行和 Trace 展示中的口径一致。
- 前端 `npm run build` 通过。
- 后端 `PYTHONPATH=app python -m unittest discover -s app/tests` 通过。

## 2026-06-16 实施结果

- 前端请求层已收敛到 `frontend/src/services/api.ts`：统一处理鉴权、401 跳转、业务 `code !== "0"`、旧 `status !== "success"`、错误提示、重复请求取消和可选全屏 loading。
- `frontend/src/api/` 已降级为兼容门面，前台登录、知识库、会话、语音 Token 的实际实现迁移到 `frontend/src/services/`；旧 `frontend/src/api/request/` 插件式 Axios 已移除。
- 用户登录态已迁移到 `frontend/src/stores/authStore.ts`，登录页、路由守卫和基础侧边栏用户区不再读取 `frontend/src/store/user.ts`；旧 Valtio 用户态和持久化封装已移除。
- 保留 `session.ts`、`device.ts` 和 Chat 内局部 Valtio 状态作为页面/交互状态，后续若需要可再逐步迁移到 Zustand 或局部 React 状态。
- `ragent_admin_rt.py` 已收缩为兼容薄层，只保留暂未拆出专门 router 的映射、样例问题、会话兼容、停止和反馈端点；dashboard、knowledge、ingestion、trace、settings 等真实业务路径由专门 router 承载。
- `retrieval2.py` 已改为旧实验路径哨兵，禁止直接运行和业务引用，并清理默认敏感值风险。
- 检索参数已统一纳入系统配置：`topK`、`vectorSimilarityWeight`、`similarityThreshold`、`candidateTop`、`rerankEnabled`；Chat 主链路、管理端文档相似度测试和 Trace 记录使用同一口径。
- 管理端系统配置页已补充向量权重、相似度阈值、候选召回上限和模型重排开关控件，保持工作台式配置体验。
- 已补充后端单元测试，覆盖检索配置校验和旧兼容 router 不再重复承载专门管理路径。

验证结果：

- `frontend`：`npm run build` 通过。
- `backend`：`PYTHONPATH=app python -m unittest discover -s app/tests` 通过，61 个测试成功。

## 风险与回滚

- 前端认证和请求层收敛会影响登录、文件上传、流式问答和管理端接口调用，需要按页面分批迁移。
- UI 体系收敛若一次性替换组件，容易引入交互回归；应先统一入口，再逐页替换。
- 删除后端兼容 router 前，需要确认前端和历史调用方是否仍依赖旧路径。
- 检索参数统一可能改变召回排序，需要结合 Chunk 相似度测试和 Trace 验证。
- 回滚策略是保留阶段性兼容层，按请求层、状态层、router、检索入口分批提交，出现问题时回退单一阶段。
