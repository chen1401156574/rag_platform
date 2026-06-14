import type { RagTraceConversationQuery } from "@/services/ragTraceService";

export const CONVERSATION_PAGE_SIZE = 10;
export const TRACE_CONVERSATION_FILTER_STORAGE_KEY = "rag_trace_conversation_filters";

export type TraceConversationStatus = "success" | "failed" | "running" | "clarify_needed";

export type TraceConversationFilters = {
  timeRange: [string, string] | null;
  sessionId: string;
  traceId: string;
  userKeyword: string;
  status: TraceConversationStatus[];
  intentCode: string;
  keyword: string;
  minDurationMs?: number;
  maxDurationMs?: number;
  minTtftMs?: number;
  maxTtftMs?: number;
  hasFailedNode?: boolean;
  hasClarify?: boolean;
};

export type TraceConversationFilterKey =
  | "timeRange"
  | "sessionId"
  | "traceId"
  | "userKeyword"
  | "status"
  | "intentCode"
  | "keyword"
  | "duration"
  | "ttft"
  | "hasFailedNode"
  | "hasClarify";

export const CONVERSATION_STATUS_OPTIONS: Array<{ value: TraceConversationStatus; label: string }> = [
  { value: "success", label: "成功" },
  { value: "failed", label: "失败" },
  { value: "running", label: "运行中" },
  { value: "clarify_needed", label: "等待补充" }
];

export const createDefaultConversationFilters = (): TraceConversationFilters => {
  const end = new Date();
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
  return {
    timeRange: [start.toISOString(), end.toISOString()],
    sessionId: "",
    traceId: "",
    userKeyword: "",
    status: [],
    intentCode: "",
    keyword: ""
  };
};

const parseNumber = (value: string | null): number | undefined => {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const parseBool = (value: string | null): boolean | undefined => {
  if (value === "true" || value === "1") return true;
  if (value === "false" || value === "0") return false;
  return undefined;
};

const serializeBool = (value?: boolean): string | undefined => {
  if (value === undefined) return undefined;
  return value ? "true" : "false";
};

const normalizeStatuses = (value: string | null): TraceConversationStatus[] => {
  if (!value) return [];
  const allowed = new Set(CONVERSATION_STATUS_OPTIONS.map((item) => item.value));
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item): item is TraceConversationStatus => allowed.has(item as TraceConversationStatus));
};

export const parseConversationFiltersFromSearch = (
  search: string
): { filters: TraceConversationFilters; page: number } => {
  const defaults = createDefaultConversationFilters();
  const params = new URLSearchParams(search);
  const startTime = params.get("startTime");
  const endTime = params.get("endTime");
  const timeRange = startTime && endTime ? [startTime, endTime] as [string, string] : defaults.timeRange;
  const page = Math.max(Number(params.get("current") || "1") || 1, 1);

  return {
    page,
    filters: {
      ...defaults,
      timeRange,
      sessionId: params.get("sessionId") || "",
      traceId: params.get("traceId") || "",
      userKeyword: params.get("userName") || "",
      status: normalizeStatuses(params.get("status")),
      intentCode: params.get("intentCode") || "",
      keyword: params.get("keyword") || "",
      minDurationMs: parseNumber(params.get("minDurationMs")),
      maxDurationMs: parseNumber(params.get("maxDurationMs")),
      minTtftMs: parseNumber(params.get("minTtftMs")),
      maxTtftMs: parseNumber(params.get("maxTtftMs")),
      hasFailedNode: parseBool(params.get("hasFailedNode")),
      hasClarify: parseBool(params.get("hasClarify"))
    }
  };
};

export const loadStoredConversationFilters = (): TraceConversationFilters | null => {
  try {
    const raw = window.sessionStorage.getItem(TRACE_CONVERSATION_FILTER_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as TraceConversationFilters;
    return {
      ...createDefaultConversationFilters(),
      ...parsed,
      status: Array.isArray(parsed.status) ? parsed.status : []
    };
  } catch {
    return null;
  }
};

export const saveConversationFilters = (filters: TraceConversationFilters) => {
  try {
    window.sessionStorage.setItem(TRACE_CONVERSATION_FILTER_STORAGE_KEY, JSON.stringify(filters));
  } catch {
    // sessionStorage 失败不影响查询主流程。
  }
};

export const conversationFiltersToSearch = (
  filters: TraceConversationFilters,
  current: number
): string => {
  const params = new URLSearchParams();
  params.set("current", String(current));
  if (filters.timeRange?.[0]) params.set("startTime", filters.timeRange[0]);
  if (filters.timeRange?.[1]) params.set("endTime", filters.timeRange[1]);
  if (filters.sessionId.trim()) params.set("sessionId", filters.sessionId.trim());
  if (filters.traceId.trim()) params.set("traceId", filters.traceId.trim());
  if (filters.userKeyword.trim()) params.set("userName", filters.userKeyword.trim());
  if (filters.status.length) params.set("status", filters.status.join(","));
  if (filters.intentCode.trim()) params.set("intentCode", filters.intentCode.trim());
  if (filters.keyword.trim()) params.set("keyword", filters.keyword.trim());
  if (filters.minDurationMs !== undefined) params.set("minDurationMs", String(filters.minDurationMs));
  if (filters.maxDurationMs !== undefined) params.set("maxDurationMs", String(filters.maxDurationMs));
  if (filters.minTtftMs !== undefined) params.set("minTtftMs", String(filters.minTtftMs));
  if (filters.maxTtftMs !== undefined) params.set("maxTtftMs", String(filters.maxTtftMs));
  const failedNode = serializeBool(filters.hasFailedNode);
  if (failedNode !== undefined) params.set("hasFailedNode", failedNode);
  const clarify = serializeBool(filters.hasClarify);
  if (clarify !== undefined) params.set("hasClarify", clarify);
  return params.toString();
};

export const buildConversationQuery = (
  filters: TraceConversationFilters,
  current: number,
  size = CONVERSATION_PAGE_SIZE
): RagTraceConversationQuery => ({
  current,
  size,
  sessionId: filters.sessionId.trim() || undefined,
  traceId: filters.traceId.trim() || undefined,
  userName: filters.userKeyword.trim() || undefined,
  status: filters.status,
  intentCode: filters.intentCode.trim() || undefined,
  keyword: filters.keyword.trim() || undefined,
  minDurationMs: filters.minDurationMs,
  maxDurationMs: filters.maxDurationMs,
  minTtftMs: filters.minTtftMs,
  maxTtftMs: filters.maxTtftMs,
  hasFailedNode: filters.hasFailedNode,
  hasClarify: filters.hasClarify,
  startTime: filters.timeRange?.[0],
  endTime: filters.timeRange?.[1]
});

export const activeConversationFilterCount = (filters: TraceConversationFilters): number => {
  let count = 0;
  if (filters.sessionId.trim()) count += 1;
  if (filters.traceId.trim()) count += 1;
  if (filters.userKeyword.trim()) count += 1;
  if (filters.status.length) count += 1;
  if (filters.intentCode.trim()) count += 1;
  if (filters.keyword.trim()) count += 1;
  if (filters.minDurationMs !== undefined || filters.maxDurationMs !== undefined) count += 1;
  if (filters.minTtftMs !== undefined || filters.maxTtftMs !== undefined) count += 1;
  if (filters.hasFailedNode !== undefined) count += 1;
  if (filters.hasClarify !== undefined) count += 1;
  return count;
};

export const toDateTimeLocalValue = (iso?: string | null): string => {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

export const fromDateTimeLocalValue = (value: string): string => {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
};

export const conversationFilterLabel = (
  key: TraceConversationFilterKey,
  filters: TraceConversationFilters
): string | null => {
  if (key === "timeRange" && filters.timeRange) {
    return `时间：${new Date(filters.timeRange[0]).toLocaleString("zh-CN")} - ${new Date(filters.timeRange[1]).toLocaleString("zh-CN")}`;
  }
  if (key === "sessionId" && filters.sessionId.trim()) return `会话：${filters.sessionId.trim()}`;
  if (key === "traceId" && filters.traceId.trim()) return `Trace：${filters.traceId.trim()}`;
  if (key === "userKeyword" && filters.userKeyword.trim()) return `用户：${filters.userKeyword.trim()}`;
  if (key === "status" && filters.status.length) {
    const names = filters.status.map((status) => CONVERSATION_STATUS_OPTIONS.find((item) => item.value === status)?.label || status);
    return `状态：${names.join("、")}`;
  }
  if (key === "intentCode" && filters.intentCode.trim()) return `意图：${filters.intentCode.trim()}`;
  if (key === "keyword" && filters.keyword.trim()) return `问题：${filters.keyword.trim()}`;
  if (key === "duration" && (filters.minDurationMs !== undefined || filters.maxDurationMs !== undefined)) {
    return `耗时：${filters.minDurationMs ?? 0} - ${filters.maxDurationMs ?? "∞"} ms`;
  }
  if (key === "ttft" && (filters.minTtftMs !== undefined || filters.maxTtftMs !== undefined)) {
    return `首字：${filters.minTtftMs ?? 0} - ${filters.maxTtftMs ?? "∞"} ms`;
  }
  if (key === "hasFailedNode" && filters.hasFailedNode !== undefined) {
    return `失败节点：${filters.hasFailedNode ? "有" : "无"}`;
  }
  if (key === "hasClarify" && filters.hasClarify !== undefined) {
    return `追问：${filters.hasClarify ? "有" : "无"}`;
  }
  return null;
};

export const clearConversationFilter = (
  filters: TraceConversationFilters,
  key: TraceConversationFilterKey
): TraceConversationFilters => {
  const defaults = createDefaultConversationFilters();
  if (key === "timeRange") return { ...filters, timeRange: defaults.timeRange };
  if (key === "sessionId") return { ...filters, sessionId: "" };
  if (key === "traceId") return { ...filters, traceId: "" };
  if (key === "userKeyword") return { ...filters, userKeyword: "" };
  if (key === "status") return { ...filters, status: [] };
  if (key === "intentCode") return { ...filters, intentCode: "" };
  if (key === "keyword") return { ...filters, keyword: "" };
  if (key === "duration") return { ...filters, minDurationMs: undefined, maxDurationMs: undefined };
  if (key === "ttft") return { ...filters, minTtftMs: undefined, maxTtftMs: undefined };
  if (key === "hasFailedNode") return { ...filters, hasFailedNode: undefined };
  if (key === "hasClarify") return { ...filters, hasClarify: undefined };
  return filters;
};
