# Prompt 地图

本文件记录 Prompt 的主要分布。完整历史扫描见 [项目提示词清单](../../plan/项目提示词清单.md)。

## 运行时 Prompt

| 名称 | 位置 | 用途 |
| --- | --- | --- |
| RAG 默认回答模板 | `backend/app/service/settings_service.py` | 基于参考内容生成最终回答，要求相关性判断和引用标注。 |
| RAG Prompt 补全文案 | `backend/app/service/core/chat.py` | 当配置模板缺少参考内容或问题占位符时自动补齐。 |
| 推荐问题生成 | `backend/app/service/core/chat.py` | 回答结束后生成 3 个相关推荐问题。 |
| 会话标题生成 | `backend/app/service/core/chat.py` | 首轮对话后生成会话名称。 |
| 歧义检测与追问 | `backend/app/service/ambiguity_service.py` | 判断是否缺少关键参数并生成追问。 |
| 追问信息合并 | `backend/app/service/ambiguity_service.py` | 合并原问题和用户补充说明。 |
| 意图分类 | `backend/app/service/intent_engine.py` | 从启用意图节点中选择最匹配意图。 |
| 系统意图兜底回答 | `backend/app/service/intent_engine.py` | 系统/闲聊类意图未配置模板时兜底。 |
| MCP 参数抽取 | `backend/app/service/intent_engine.py` | MCP 工具调用前抽取结构化参数。 |

## 可配置入口

- 管理端系统设置：编辑 RAG Prompt 模板、模型参数、top_k 等。
- 管理端意图树：编辑意图节点 Prompt 片段、完整 Prompt、MCP 参数抽取模板。
- 入库流水线节点：前端已有 `systemPrompt` 和 `userPromptTemplate` 字段，后端执行链路仍需核验。

## 设计要求

- Prompt 必须明确引用规则。
- Prompt 必须明确检索内容不足时的回答方式。
- 对规则计算类问题，Prompt 必须要求逐项核对用户参数。
- 输出 JSON 的 Prompt 必须要求不要包裹 Markdown 代码块。
- 新增 Prompt 后同步更新本文件或历史 Prompt 清单。

