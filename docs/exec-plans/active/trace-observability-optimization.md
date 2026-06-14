# Trace 可观测性全链路优化

状态：进行中

来源材料：[链路跟踪页面全链路优化实施计划](../../../plan/链路跟踪页面全链路优化实施计划.md)

## 背景

当前 RAG 平台已经记录 Trace run/node，但管理端仍需要更完整地解释一次回答的过程，包括意图分类结果、检索结果、LLM 输入输出、Session 维度上下文和节点错误。

## 目标

- Trace 列表能快速判断一次问答的状态、耗时、会话和意图命中。
- Trace 详情能展示节点输入 JSON、输出 JSON、额外数据和错误信息。
- 管理端能从会话维度查看多次运行记录。
- 关键 ID 支持复制，便于排障和日志关联。

## 范围

- 后端：`trace_rt.py`、`trace_service.py`、相关模型和序列化字段。
- 前端：`frontend/src/pages/admin/traces/`、`frontend/src/services/ragTraceService.ts`。
- 样式：管理端 Trace 页面相关 CSS。

## 非目标

- 不在本计划内重构整个 RAG 运行引擎。
- 不改变用户端 Chat 主交互。
- 不引入新的外部可观测平台。

## 验收标准

- Trace 列表包含 Session Id、意图编码、意图名称、置信度、耗时和状态。
- Trace 详情能查看每个节点的输入输出 JSON。
- 歧义追问场景能显示 `clarify_needed` 状态。
- 前端 `npm run build` 无 TypeScript 未使用 import 或类型错误。
- 后端相关单元测试通过。

## 风险

- 节点 JSON 可能较大，需要前端折叠展示。
- 历史 Trace 数据可能缺少新字段，前端需要兼容空值。
- Trace 字段命名应避免和已有 API 返回冲突。

