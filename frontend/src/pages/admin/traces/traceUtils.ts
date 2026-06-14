import type { RagTraceNode } from "@/services/ragTraceService";

export const PAGE_SIZE = 10;

export type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

export type TraceStatus = "" | "success" | "failed" | "running";

export type TraceFilters = {
  traceId: string;
  conversationId: string;
  taskId: string;
  status: TraceStatus;
};

export type TimelineNode = RagTraceNode & {
  depthValue: number;
  resolvedDurationMs: number;
  offsetMs: number;
  leftPercent: number;
  widthPercent: number;
};

export const DEFAULT_FILTERS: TraceFilters = {
  traceId: "",
  conversationId: "",
  taskId: "",
  status: ""
};

export const STATUS_OPTIONS: { value: TraceStatus; label: string }[] = [
  { value: "", label: "全部状态" },
  { value: "running", label: "运行中" },
  { value: "success", label: "成功" },
  { value: "failed", label: "失败" }
];

export const normalizeStatus = (status?: string | null): string => (status || "").trim().toLowerCase();

export const statusLabel = (status?: string | null): string => {
  const normalized = normalizeStatus(status);
  if (!normalized) return "UNKNOWN";
  if (normalized === "success") return "SUCCESS";
  if (normalized === "failed") return "FAILED";
  if (normalized === "running") return "RUNNING";
  if (normalized === "timeout") return "TIMEOUT";
  return normalized.toUpperCase();
};

export const statusBadgeVariant = (status?: string | null): BadgeVariant => {
  const normalized = normalizeStatus(status);
  if (normalized === "failed" || normalized === "timeout") return "destructive";
  if (normalized === "running") return "secondary";
  if (normalized === "success") return "default";
  return "outline";
};

export const toTimestamp = (value?: string | number | null): number | null => {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const parsedByDate = new Date(value).getTime();
  if (!Number.isNaN(parsedByDate)) return parsedByDate;
  const asNumber = Number(value);
  if (!Number.isFinite(asNumber)) return null;
  return asNumber;
};

export const formatDateTime = (value?: string | number | null): string => {
  const timestamp = toTimestamp(value);
  if (timestamp === null) return "-";
  return new Date(timestamp).toLocaleString("zh-CN");
};

export const formatDuration = (value?: number | null): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  if (value < 1000) return `${Math.round(value)}ms`;
  if (value < 60_000) return `${(value / 1000).toFixed(2)}s`;
  const minute = Math.floor(value / 60_000);
  const second = ((value % 60_000) / 1000).toFixed(1);
  return `${minute}m ${second}s`;
};

export const percentile = (values: number[], ratio: number): number => {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.max(0, Math.min(sorted.length - 1, Math.ceil(sorted.length * ratio) - 1));
  return sorted[index];
};

export const clamp = (value: number, min: number, max: number): number => {
  return Math.min(max, Math.max(min, value));
};

export const nodeTypeChipClass = (type?: string | null): string => {
  const normalized = (type || "").trim().toUpperCase();
  if (normalized === "ROOT") return "bg-indigo-100 text-indigo-700";
  if (normalized === "USER_TTFT") return "bg-rose-100 text-rose-700";
  if (normalized === "LLM_TTFT") return "bg-emerald-100 text-emerald-700";
  if (normalized === "LLM_PROVIDER") return "bg-orange-100 text-orange-700";
  if (normalized === "LLM_ROUTING") return "bg-amber-100 text-amber-700";
  if (normalized === "GUIDANCE") return "bg-violet-100 text-violet-700";
  if (normalized === "INTENT" || normalized === "INTENTCLASSIFY") return "bg-sky-100 text-sky-700";
  if (normalized === "REWRITE") return "bg-teal-100 text-teal-700";
  if (
      normalized === "RETRIEVE" ||
      normalized === "RAG_NODE" ||
      normalized === "VECTORRETRIEVE" ||
      normalized === "RETRIEVALQUERYBUILD" ||
      normalized === "ESHYBRIDSEARCH" ||
      normalized === "RERANKCHUNKS"
  ) return "bg-blue-100 text-blue-700";
  if (
      normalized === "USERQUESTIONRECEIVED" ||
      normalized === "AUTHLOADSETTINGS" ||
      normalized === "CLARIFICATIONMERGE" ||
      normalized === "AMBIGUITYAUDIT" ||
      normalized === "CLARIFYRESPONSE" ||
      normalized === "QUICKPARSELOAD" ||
      normalized === "CONTEXTASSEMBLE"
  ) return "bg-violet-100 text-violet-700";
  if (
      normalized === "PROMPTBUILD" ||
      normalized === "LLMSTREAMSTART" ||
      normalized === "LLMFIRSTTOKEN" ||
      normalized === "LLMANSWERSTREAM" ||
      normalized === "LLMFINALANSWER" ||
      normalized === "RECOMMENDQUESTIONS" ||
      normalized === "LLMCALL"
  ) return "bg-emerald-100 text-emerald-700";
  if (
      normalized === "SSEDOCUMENTSSENT" ||
      normalized === "SSEENDSENT" ||
      normalized === "SSEERRORSENT" ||
      normalized === "PERSISTMESSAGE" ||
      normalized === "SESSIONTITLEUPDATE"
  ) return "bg-stone-100 text-stone-700";
  if (normalized === "TITLE_GEN") return "bg-stone-100 text-stone-700";
  if (normalized.startsWith("MCP")) return "bg-cyan-100 text-cyan-700";
  return "bg-slate-100 text-slate-600";
};

const NODE_NAME_DISPLAY: Record<string, string> = {
  "rag-stream-chat": "RAG 流式对话",
  "user-first-packet": "用户感知首包",
  "llm-first-packet": "LLM 首包",
  "llm-chat-routing": "LLM 路由调度",
  "bailian-chat": "百炼 · 同步",
  "bailian-stream-chat": "百炼 · 流式",
  "ollama-chat": "Ollama · 同步",
  "ollama-stream-chat": "Ollama · 流式",
  "siliconflow-chat": "硅基流动 · 同步",
  "siliconflow-stream-chat": "硅基流动 · 流式",
  "aihubmix-chat": "AIHubMix · 同步",
  "aihubmix-stream-chat": "AIHubMix · 流式",
  "query-rewrite-and-split": "问题改写与拆分",
  "intent-resolve": "意图识别",
  "guidance-detect": "歧义引导",
  "retrieval-engine": "知识库检索",
  "multi-channel-retrieval": "多路召回",
  "context-build": "上下文组装",
  "prompt-render": "Prompt 渲染",
  "conversation-title-gen": "会话标题生成",
  "llm-stream-routing": "LLM 流式路由",
  "User Question Received": "用户问题接收",
  "Auth And Settings": "鉴权与配置",
  "Retrieval Query Build": "检索查询构建",
  "ES Hybrid Search": "ES 混合检索",
  "Rerank Chunks": "检索结果重排",
  "Vector Retrieval": "向量检索",
  "Vector Retrieval After Clarification": "追问后二次检索",
  "Clarification Merge": "追问信息合并",
  "Ambiguity Audit": "歧义审计",
  "Ambiguity Audit Skipped": "跳过歧义审计",
  "Clarify SSE Response": "追问响应",
  "Quick Parse Load": "快速解析读取",
  "Context Assemble": "上下文组装",
  "Prompt Build": "Prompt 构建",
  "LLM Stream Start": "LLM 流式开始",
  "LLM First Token": "LLM 首包",
  "LLM Answer Stream": "LLM 回答流",
  "LLM Final Answer": "模型最终回答",
  "Recommend Questions": "推荐问题",
  "SSE Documents Sent": "SSE 引用发送",
  "SSE End Sent": "SSE 结束",
  "SSE Error Sent": "SSE 错误",
  "Persist Message": "消息落库",
  "Session Title Update": "会话标题更新",
  "Large Language Model Call": "LLM 调用"
};

const toTitleCase = (raw: string): string =>
    raw
        .split(/[-_\s]+/)
        .filter(Boolean)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");

export const prettifyNodeName = (name?: string | null): string => {
  if (!name) return "-";
  const trimmed = name.trim();
  if (!trimmed) return "-";
  const mapped = NODE_NAME_DISPLAY[trimmed];
  if (mapped) return mapped;
  return toTitleCase(trimmed);
};

export const resolveNodeDuration = (node: RagTraceNode): number => {
  const durationMs = Number(node.durationMs ?? 0);
  if (Number.isFinite(durationMs) && durationMs > 0) return durationMs;
  const start = toTimestamp(node.startTime);
  const end = toTimestamp(node.endTime);
  if (start !== null && end !== null && end >= start) return end - start;
  return 0;
};
