# 设计规范

本文件是设计文档总入口。具体专题放在 `docs/design-docs/` 下，当前执行计划放在 `docs/PLANS.md`。

## 设计目标

- 让普通用户在不理解 RAG 技术细节的情况下完成文档问答、引用核验和追问补充。
- 让管理员能看见知识库、意图、模型参数、入库任务和问答链路的运行状态。
- 让排障路径可追踪：一次回答必须能回到意图分类、检索结果、Prompt 输入、LLM 输出和最终引用。
- 让系统配置可控：Prompt、模型、top_k、意图树和知识库绑定应由管理端配置，而不是散落在代码里。

## 文档索引

- [设计文档目录](design-docs/index.md)
- [核心设计信念](design-docs/core-beliefs.md)
- [RAG 问答链路设计](design-docs/rag-chain.md)
- [Prompt 地图](design-docs/prompt-map.md)
- [图片与复杂文档解析增强方案](design-docs/image-complex-document-parsing.md)
- [基于公司 Logo 的 UI 优化整体方向](design-docs/logo-driven-ui-optimization.md)
- [系统架构](../ARCHITECTURE.md)
- [当前计划](PLANS.md)

## 产品原则

- 回答必须优先基于参考内容，不把局部相关材料包装成完整答案。
- 引用必须可见、可点击、可追溯。
- 当用户问题缺少关键参数时，系统应先追问，不应猜测。
- 管理端界面服务于排障和运营，优先信息密度、筛选、对比、下钻和复制操作。
- 用户端界面服务于连续问答，优先阅读流畅、引用清楚、追问自然和文档上下文可理解。

## 后端设计约束

- 管理端新增接口必须挂在 `/api/ragent/*` 并受 `require_admin` 保护。
- 管理端接口返回统一业务结构，成功时业务 `code` 为 `"0"`。
- 修改数据库结构时，同步更新 SQLAlchemy 模型、Alembic 迁移和 `backend/init.sql`。
- RAG 主链路中的可观测节点应优先记录输入 JSON、输出 JSON、耗时、错误信息和额外上下文。
- Prompt 模板中至少应明确 `{question}` 和参考内容变量，缺失时由后端补全兜底上下文。

## 前端设计约束

- 管理控制台采用工作台风格，避免营销式首页和装饰性内容。
- 前端视觉升级应对齐公司 Logo 的绿色可信、橙色高效、青色链路、墨蓝专业体系，具体见 [基于公司 Logo 的 UI 优化整体方向](design-docs/logo-driven-ui-optimization.md)。
- 表格页必须提供关键筛选、状态显示、分页、空态和错误态。
- Trace、知识库、入库任务等排障页面应支持从列表进入详情，并保留关键 ID 的复制能力。
- Chat 页面滚动应限制在主内容容器内，避免全局页面滚动影响输入框位置。
- 前端引用格式以 `##N$$` 为后端协议，渲染层负责转成可点击引用徽章。

## 文档维护规则

- 新设计先放到 `docs/design-docs/`，再从本文件补入口。
- 新执行计划放到 `docs/exec-plans/active/`，并在 `docs/PLANS.md` 登记。
- 完成的执行计划移到 `docs/exec-plans/completed/` 或在索引中标记完成。
- 发现跨模块遗留问题时，登记到 `docs/exec-plans/tech-debt-tracker.md`。
