# RAG 问答链路设计

## 主链路

```text
用户提问
-> 鉴权
-> 加载系统设置
-> 意图分类
-> 混合检索
-> 重排序
-> 歧义审计
-> 合并临时文档
-> 渲染 Prompt
-> LLM 流式生成
-> 推荐问题
-> 写入消息与会话
-> 记录 Trace
```

用户问答的 LLM 调用默认沿用 DashScope OpenAI 兼容配置；当 `DEEPSEEK_BASE_URL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL` 同时配置时，主回答、推荐问题和会话标题生成会切换到 DeepSeek OpenAI 兼容接口。

## 意图分类

意图分类由 `backend/app/service/intent_engine.py` 负责。当前会从启用的意图树节点中选择最匹配项，并保留关键词兜底逻辑。

当前限制：

- 系统意图和 MCP 意图的工具函数已存在。
- 主聊天链路仍统一走知识库检索，尚未真正按 `INTENT_KIND_SYSTEM`、`INTENT_KIND_MCP` 分流。

## 检索与重排序

检索链路包含 BM25 文本检索、KNN 向量检索和模型重排序。

关键点：

- Query 先做分词、权重、同义词扩展。
- 向量模型使用 DashScope Embedding。
- 首轮召回后再通过 rerank 模型排序。
- 当前存在检索权重口径不一致问题，见 [技术债跟踪](../exec-plans/tech-debt-tracker.md)。

## 歧义审计与追问

歧义审计由 `backend/app/service/ambiguity_service.py` 负责。

设计目标：

- 不直接回答缺少关键参数的问题。
- 追问数量控制在用户可以一次性回答的范围内。
- 用户补充后合并成更完整的问题，再进入检索和回答。

## 临时文档合并

快速解析文档存储在 Redis 中，并在回答前合并到参考内容里。

注意事项：

- 临时文档不进入正式知识库。
- 过期后不可复用。
- 适合短期问答，不适合长期知识沉淀。

## Trace 观测

Trace 目标是解释一次问答的关键决策。

当前重点节点：

- `IntentClassify`
- `VectorRetrieve`
- `LLMCall`

期望详情页展示：

- 节点耗时。
- 输入 JSON。
- 输出 JSON。
- 错误信息。
- 意图命中与置信度。
- 检索结果和引用关系。
