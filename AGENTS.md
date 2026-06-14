# AGENTS.md

本文件是项目协作入口。进入仓库后先读这里，再按当前任务跳转到具体文档，不要一次性加载全部材料。

## 产品定位

`rag_platform` 是一个前后端分离的企业知识问答与 RAG 管理平台。

面向普通用户，它提供登录、知识库文件上传、单会话临时文档解析、流式问答、引用溯源、歧义追问和推荐问题能力。

面向管理员，它提供运营驾驶舱、动态意图树、系统 Prompt 与模型参数配置、用户管理、知识库与文档下钻、入库任务监控、全链路 Trace 可观测、查询词映射和样例问题管理。

## 总体设计

- 系统架构 -> [ARCHITECTURE.md](ARCHITECTURE.md)
- 当前计划 -> [docs/PLANS.md](docs/PLANS.md)
- 设计规范 -> [docs/DESIGN.md](docs/DESIGN.md)

## 详细文档

- 设计文档目录 -> [docs/design-docs/](docs/design-docs/index.md)
- 执行计划目录 -> [docs/exec-plans/](docs/PLANS.md)
- 技术债跟踪 -> [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md)
- 历史计划资料 -> [plan/](plan/)

## 使用规则

- 先确认任务类型，再读取相关文档：
  - 架构、模块边界、数据流：读 [ARCHITECTURE.md](ARCHITECTURE.md)。
  - 产品原则、交互规范、Prompt 设计：读 [docs/DESIGN.md](docs/DESIGN.md) 和 [docs/design-docs/](docs/design-docs/index.md)。
  - 当前实施、排期、验收：读 [docs/PLANS.md](docs/PLANS.md)。
  - 已知问题、遗留风险：读 [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md)。
- 信息冲突时，以更具体、更接近实现的材料为准：代码 > 当前执行计划 > 设计文档 > 总览文档。
- 涉及数据库表结构时，同时检查 `backend/init.sql`、`backend/app/models/` 和 `backend/app/alembic/`。
- 后端管理接口必须保持 `/api/ragent/*` 权限保护，并使用统一响应结构。
- 不要把 `.env`、真实密钥、访问令牌或日志中的敏感值写入文档。
- 文档更新后，入口关系必须保持清楚：`AGENTS.md` 负责导航，`ARCHITECTURE.md` 负责系统事实，`docs/DESIGN.md` 负责设计约束，`docs/PLANS.md` 负责计划状态。

