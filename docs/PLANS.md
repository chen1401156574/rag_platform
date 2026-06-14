# 当前计划

本文件是执行计划总入口。详细计划按状态放在 `docs/exec-plans/`，历史材料仍保留在 `plan/` 目录。

## 当前活跃计划

| 计划 | 状态 | 说明 |
| --- | --- | --- |
| [Trace 可观测性全链路优化](exec-plans/active/trace-observability-optimization.md) | 进行中 | 围绕 Trace 列表、详情、节点输入输出、Session 维度追踪做管理端排障增强。 |
| [知识库 Chunk 查看与相似度测试第一阶段](exec-plans/active/chunk-similarity-phase1.md) | 待实施/待核验 | 面向管理端知识库 Chunk 下钻、检索相似度测试和召回质量诊断。 |

## 已完成或阶段性归档

| 记录 | 状态 | 说明 |
| --- | --- | --- |
| [2026-06-14 Trace 与 Prompt 阶段记录](exec-plans/completed/2026-06-14-trace-prompt-update.md) | 阶段完成 | 汇总 2026-06-14 的 Trace 展示、Prompt 相关性约束和歧义审计变化。 |

## 技术债

- [技术债跟踪](exec-plans/tech-debt-tracker.md)

## 历史计划资料

以下文件来自原 `plan/` 目录，后续新文档优先沉淀到 `docs/`：

- [链路分析](../plan/链路分析.md)
- [问答链路流程图](../plan/问答链路流程图.md)
- [链路跟踪页面全链路优化实施计划](../plan/链路跟踪页面全链路优化实施计划.md)
- [知识库Chunk查看与相似度测试第一阶段方案问答](../plan/知识库Chunk查看与相似度测试第一阶段方案问答.md)
- [项目提示词清单](../plan/项目提示词清单.md)
- [CHANGELOG_2026-06-14](../plan/CHANGELOG_2026-06-14.md)

## 执行计划模板

新增计划建议包含：

```markdown
# 计划名称

## 背景

## 目标

## 范围

## 非目标

## 实施步骤

## 验收标准

## 风险与回滚
```

