# 技术债跟踪

更新时间：2026-06-16

| 编号 | 问题 | 影响 | 状态 | 相关位置 |
| --- | --- | --- | --- | --- |
| TD-001 | 意图路由尚未真正分流 `INTENT_KIND_SYSTEM` 和 `INTENT_KIND_MCP` | 闲聊、系统操作和工具调用仍可能走知识库检索，回答链路不够准确 | 待处理 | `backend/app/service/intent_engine.py`、`backend/app/router/chat_rt.py` |
| TD-002 | 检索融合权重口径不一致 | 排查召回质量时难以解释分数和排序 | 已处理 | `backend/app/service/settings_service.py`、`backend/app/service/core/retrieval.py`、`backend/app/service/core/rag/nlp/search_v2.py` |
| TD-003 | DeepDOC PDF 本地推理成本高 | 大 PDF 入库速度慢，资源占用高 | 观察中 | `backend/app/service/core/deepdoc/` |
| TD-004 | 快速解析文档只存 Redis 2 小时 | 会话结束或缓存过期后不能复用临时文档 | 已知限制 | `backend/app/service/quick_parse_service.py` |
| TD-005 | 管理端入库流水线 Prompt 字段后端执行链路待核验 | 前端可配置字段可能未真正参与模型调用 | 待核验 | `frontend/src/pages/admin/ingestion/IngestionPage.tsx`、`backend/app/router/ingestion_rt.py` |
| TD-006 | 历史 Prompt 扫描发现未定义 `prompt` 变量 | 若相关函数被调用可能运行时报错 | 待核验 | `backend/app/service/core/rag/nlp/model.py` |
| TD-007 | Trace 节点 JSON 可能过大 | 管理端详情页可读性和性能可能受影响 | 待优化 | `frontend/src/pages/admin/traces/` |
| TD-008 | 前端 UI、状态和请求层存在新旧体系并行 | Token、错误处理、响应解包和组件规范容易分叉，新增页面选型不稳定 | 阶段处理 | `frontend/src/services/api.ts`、`frontend/src/services/`、`frontend/src/stores/authStore.ts`、`frontend/src/components/ui/` |
| TD-009 | `ragent_admin_rt.py` 与专门管理端 router 存在重复接口 | 同一路径可能出现简化实现和真实实现并存，排查接口行为时不够清晰 | 已处理 | `backend/app/router/ragent_admin_rt.py`、`backend/app/router/knowledge_admin_rt.py`、`backend/app/router/dashboard_rt.py`、`backend/app/app_main.py` |
| TD-010 | 检索层存在旧实验路径 `retrieval2.py` | 旧代码可能误用且含默认敏感值风险，检索入口不够单一 | 已处理 | `backend/app/service/core/retrieval.py`、`backend/app/service/core/retrieval2.py`、`backend/app/service/core/rag/nlp/search_v2.py` |

## 处理规则

- 修复技术债时，在本表更新状态并补充对应执行计划或 PR 说明。
- 与数据库结构相关的问题必须同时检查模型、迁移和 `init.sql`。
- 与 Prompt 相关的问题同步更新 [Prompt 地图](../design-docs/prompt-map.md)。
