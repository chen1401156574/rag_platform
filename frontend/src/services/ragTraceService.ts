import { api } from "@/services/api";

export interface RagTraceRun {
  traceId: string;
  traceName?: string | null;
  entryMethod?: string | null;
  conversationId?: string | null;
  sessionId?: string | null;
  taskId?: string | null;
  userName?: string | null;
  username?: string | null;
  userId?: string | null;
  status?: string | null;
  errorMessage?: string | null;
  durationMs?: number | null;
  ttftMs?: number | null;
  question?: string | null;
  startTime?: string | null;
  endTime?: string | null;
  intentCode?: string | null;
  intentName?: string | null;
  intentScore?: number | null;
}

export interface RagTraceConversation {
  sessionId: string;
  conversationId?: string | null;
  sessionName?: string | null;
  userId?: string | null;
  userName?: string | null;
  turnCount: number;
  successCount: number;
  failedCount: number;
  runningCount?: number;
  clarifyCount: number;
  failedNodeCount?: number;
  hasFailedNode?: boolean;
  hasClarify?: boolean;
  lastTraceId?: string | null;
  lastQuestion?: string | null;
  lastIntentCode?: string | null;
  lastIntentName?: string | null;
  lastIntentScore?: number | null;
  lastStatus?: string | null;
  status?: string | null;
  avgDurationMs?: number | null;
  avgTtftMs?: number | null;
  maxDurationMs?: number | null;
  firstStartTime?: string | null;
  lastStartTime?: string | null;
  lastEndTime?: string | null;
}

export interface RagTraceConversationRun extends RagTraceRun {
  turnNo: number;
  nodeCount?: number | null;
  failedNodeCount?: number | null;
  hasClarify?: boolean;
  finalAnswerSummary?: string | null;
  persisted?: boolean | null;
}

export interface RagTraceConversationDetail {
  conversation: RagTraceConversation;
  runs: RagTraceConversationRun[];
}

export interface RagTraceNode {
  traceId: string;
  nodeId: string;
  parentNodeId?: string | null;
  depth?: number | null;
  nodeType?: string | null;
  nodeName?: string | null;
  className?: string | null;
  methodName?: string | null;
  status?: string | null;
  errorMessage?: string | null;
  durationMs?: number | null;
  startTime?: string | null;
  endTime?: string | null;
  inputJson?: string | null;
  outputJson?: string | null;
  extraData?: string | null;
}

export interface RagTraceDetail {
  run: RagTraceRun;
  nodes: RagTraceNode[];
}

export interface PageResult<T> {
  records: T[];
  total: number;
  size: number;
  current: number;
  pages: number;
}

export interface RagTraceConversationQuery {
  current?: number;
  size?: number;
  sessionId?: string;
  traceId?: string;
  userName?: string;
  userId?: string;
  status?: string | string[];
  intentCode?: string;
  keyword?: string;
  minDurationMs?: number;
  maxDurationMs?: number;
  minTtftMs?: number;
  maxTtftMs?: number;
  hasFailedNode?: boolean;
  hasClarify?: boolean;
  startTime?: string;
  endTime?: string;
}

export interface RagTraceRunQuery {
  current?: number;
  size?: number;
  traceId?: string;
  conversationId?: string;
  taskId?: string;
  status?: string;
}

export interface RagTraceFinalAnswerSummary {
  summary: string;
  answerChars: number;
  thinkingChars: number;
  referenceCount: number;
  citationMarkerCount: number;
  persisted: boolean;
}

export interface RagTraceClientEvent {
  eventName: string;
  status?: string | null;
  durationMs?: number | null;
  occurredAt?: string | null;
  extraData?: string | null;
}

export interface RagTraceTurnTimeline {
  traceId: string;
  sessionId?: string | null;
  question?: string | null;
  effectiveQuestion?: string | null;
  finalAnswer?: RagTraceFinalAnswerSummary;
  stages: Array<{
    key:
      | "request"
      | "routing"
      | "retrieval"
      | "clarification"
      | "generation"
      | "streaming"
      | "persistence"
      | "client";
    status: string;
    durationMs?: number | null;
    nodes: RagTraceNode[];
  }>;
}

const cleanParams = (params: Record<string, unknown>) =>
  Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== "")
  );

export async function getRagTraceRuns(
  query: RagTraceRunQuery = {}
): Promise<PageResult<RagTraceRun>> {
  return api.get<PageResult<RagTraceRun>, PageResult<RagTraceRun>>("/rag/traces/runs", {
    params: {
      current: query.current ?? 1,
      size: query.size ?? 10,
      traceId: query.traceId || undefined,
      conversationId: query.conversationId || undefined,
      taskId: query.taskId || undefined,
      status: query.status || undefined
    }
  });
}

export async function getRagTraceConversations(
  query: RagTraceConversationQuery = {}
): Promise<PageResult<RagTraceConversation>> {
  return api.get<PageResult<RagTraceConversation>, PageResult<RagTraceConversation>>(
    "/rag/traces/conversations",
    {
      params: cleanParams({
        current: query.current ?? 1,
        size: query.size ?? 10,
        sessionId: query.sessionId,
        traceId: query.traceId,
        userName: query.userName,
        userId: query.userId,
        status: Array.isArray(query.status) ? query.status.join(",") : query.status,
        intentCode: query.intentCode,
        keyword: query.keyword,
        minDurationMs: query.minDurationMs,
        maxDurationMs: query.maxDurationMs,
        minTtftMs: query.minTtftMs,
        maxTtftMs: query.maxTtftMs,
        hasFailedNode: query.hasFailedNode,
        hasClarify: query.hasClarify,
        startTime: query.startTime,
        endTime: query.endTime
      })
    }
  );
}

export async function getRagTraceConversationDetail(
  sessionId: string
): Promise<RagTraceConversationDetail> {
  return api.get<RagTraceConversationDetail, RagTraceConversationDetail>(
    `/rag/traces/conversations/${encodeURIComponent(sessionId)}`
  );
}

export async function getRagTraceDetail(traceId: string): Promise<RagTraceDetail> {
  return api.get<RagTraceDetail, RagTraceDetail>(`/rag/traces/runs/${traceId}`);
}

export async function getRagTraceNodes(traceId: string): Promise<RagTraceNode[]> {
  return api.get<RagTraceNode[], RagTraceNode[]>(`/rag/traces/runs/${traceId}/nodes`);
}
