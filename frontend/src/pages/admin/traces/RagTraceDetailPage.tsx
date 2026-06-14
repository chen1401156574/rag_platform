import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  RefreshCw,
  XCircle,
  Loader2,
  Activity,
  Clock,
  Zap,
  User,
  Calendar,
  Hash,
  X,
  Copy,
  Download,
  Target,
  Crosshair,
  HelpCircle
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getRagTraceDetail, type RagTraceDetail } from "@/services/ragTraceService";
import { getErrorMessage } from "@/utils/error";
import {
  clamp,
  formatDateTime,
  formatDuration,
  nodeTypeChipClass,
  normalizeStatus,
  prettifyNodeName,
  resolveNodeDuration,
  statusBadgeVariant,
  statusLabel,
  toTimestamp,
  type TimelineNode
} from "@/pages/admin/traces/traceUtils";

// ============ 工具函数 ============

const decodeTraceId = (value?: string): string => {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

const copyToClipboard = (text: string, label: string) => {
  navigator.clipboard.writeText(text).then(() => {
    toast.success(`${label} 已复制`);
  }).catch(() => {
    toast.error("复制失败");
  });
};

// ============ 状态颜色 ============

type StatusColor = { dot: string; bar: string };

const STATUS_COLORS: Record<string, StatusColor> = {
  success: { dot: "bg-emerald-500", bar: "bg-emerald-400" },
  failed: { dot: "bg-red-500", bar: "bg-red-400" },
  running: { dot: "bg-amber-500", bar: "bg-amber-400" },
  timeout: { dot: "bg-red-500", bar: "bg-red-400" },
  clarify_needed: { dot: "bg-amber-500", bar: "bg-amber-400" },
  default: { dot: "bg-slate-300", bar: "bg-slate-300" }
};

const getStatusColors = (status?: string | null): StatusColor => {
  const normalized = normalizeStatus(status);
  return STATUS_COLORS[normalized] ?? STATUS_COLORS.default;
};

// ============ 子组件 ============

function MetricItem({
                      icon: Icon,
                      label,
                      value,
                      variant = "default"
                    }: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  variant?: "default" | "success" | "error" | "warning" | "primary";
}) {
  const styles = {
    default: "text-slate-600",
    success: "text-emerald-600",
    error: "text-red-600",
    warning: "text-amber-600",
    primary: "text-blue-600"
  };

  return (
      <div className="flex items-center gap-2 px-4 py-2">
        <Icon className={cn("h-4 w-4", styles[variant])} />
        <span className={cn("text-lg font-semibold", styles[variant])}>{value}</span>
        <span className="text-xs text-slate-500">{label}</span>
      </div>
  );
}

function TimeScale({ totalMs }: { totalMs: number }) {
  const ticks = [0, 25, 50, 75, 100];
  return (
      <div className="relative h-6 border-b border-slate-200">
        {ticks.map((percent) => (
            <div
                key={percent}
                className="absolute top-0 bottom-0 flex flex-col items-center"
                style={{ left: `${percent}%`, transform: "translateX(-50%)" }}
            >
              <div className="w-px h-2 bg-slate-300" />
              <span className="text-[10px] text-slate-400 mt-0.5">
            {formatDuration((totalMs * percent) / 100)}
          </span>
            </div>
        ))}
      </div>
  );
}

function WaterfallRow({
                        node,
                        nodeDisplayName,
                        nodeStatus,
                        isTopSlowest,
                        isSelected,
                        isRoot,
                        onSelect
                      }: {
  node: TimelineNode & {
    depthValue: number;
    resolvedDurationMs: number;
    offsetMs: number;
    leftPercent: number;
    widthPercent: number;
  };
  nodeDisplayName: string;
  nodeStatus: string | null;
  isTopSlowest?: boolean;
  isSelected?: boolean;
  isRoot?: boolean;
  onSelect?: () => void;
}) {
  const colors = getStatusColors(nodeStatus);
  const depth = isRoot ? 0 : Math.min(Math.max(node.depthValue - 1, 0), 6);
  const clickable = !!onSelect;

  return (
      <div
          onClick={onSelect}
          className={cn(
              "grid grid-cols-[minmax(180px,1fr)_120px_2fr_100px] gap-4 px-4 py-2.5 transition-colors group",
              clickable && "cursor-pointer hover:bg-slate-50/80",
              isRoot && "bg-indigo-50/40 border-b border-indigo-100",
              isTopSlowest && !isSelected && !isRoot && "bg-amber-50/40",
              isSelected && "bg-blue-50/60 ring-1 ring-inset ring-blue-200"
          )}
      >
        <div className="flex items-center gap-1.5 min-w-0">
          {depth > 0 && (
              <div className="flex items-stretch self-stretch shrink-0">
                {Array.from({ length: depth }).map((_, idx) => {
                  const isLast = idx === depth - 1;
                  return (
                      <span
                          key={idx}
                          className={cn(
                              "w-4 border-slate-200",
                              "border-l",
                              isLast && "border-b"
                          )}
                          style={{ marginTop: isLast ? -10 : 0 }}
                      />
                  );
                })}
              </div>
          )}
          <span className={cn(
              "h-2 w-2 rounded-full shrink-0 transition-transform group-hover:scale-125",
              colors.dot
          )} />
          <span
              className={cn(
                  "truncate",
                  isRoot ? "text-sm font-semibold text-indigo-900" : "text-sm text-slate-700"
              )}
              title={nodeDisplayName}
          >
            {nodeDisplayName}
          </span>
          {isTopSlowest && !isRoot && (
              <Zap className="h-3 w-3 text-amber-500 shrink-0" />
          )}
        </div>

        <div className="flex items-center">
          <span
              className={cn("text-xs px-2 py-0.5 rounded truncate font-medium", nodeTypeChipClass(node.nodeType))}
              title={node.nodeType || "-"}
          >
            {node.nodeType || "-"}
          </span>
        </div>

        <div className="flex items-center">
          <div className="relative w-full h-6 bg-slate-50 rounded overflow-hidden">
            {[25, 50, 75].map(p => (
                <div
                    key={p}
                    className="absolute top-0 bottom-0 w-px bg-slate-200"
                    style={{ left: `${p}%` }}
                />
            ))}
            <div
                className={cn(
                    "absolute top-1 bottom-1 rounded transition-all",
                    colors.bar,
                    "group-hover:brightness-110"
                )}
                style={{
                  left: `${node.leftPercent}%`,
                  width: `${Math.max(node.widthPercent, 0.5)}%`,
                  minWidth: "4px"
                }}
                title={`${nodeDisplayName} - ${formatDuration(node.resolvedDurationMs)}`}
            />
          </div>
        </div>

        <div className="text-right">
          <p className="text-sm font-medium text-slate-700">
            {formatDuration(node.resolvedDurationMs)}
          </p>
          <p className="text-[10px] text-slate-400">
            @{formatDuration(node.offsetMs)}
          </p>
        </div>
      </div>
  );
}

function NodeDetailCard({
                          node,
                          onClose
                        }: {
  node: TimelineNode | RagTraceDetail["nodes"][number];
  onClose: () => void;
}) {
  const nodeStatus = normalizeStatus(node.status);
  const displayName = prettifyNodeName(node.nodeName || node.methodName || node.nodeId);
  const durationMs = resolveNodeDuration(node);

  return (
      <Card>
        <CardHeader className="py-3 px-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <CardTitle className="text-sm font-medium text-slate-700 truncate" title={displayName}>
                {displayName}
              </CardTitle>
              <Badge variant={statusBadgeVariant(node.status)} className="text-xs">
                {statusLabel(node.status)}
              </Badge>
              <span className={cn(
                  "text-xs px-2 py-0.5 rounded font-medium",
                  nodeTypeChipClass(node.nodeType)
              )}>
                {node.nodeType || "-"}
              </span>
            </div>
            <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                className="h-7 px-2 text-slate-500 hover:text-slate-800"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2 text-xs">
            <DetailField label="Node Id" value={node.nodeId} mono copyable />
            <DetailField label="Parent Node Id" value={node.parentNodeId || "-"} mono copyable={!!node.parentNodeId} />
            <DetailField label="耗时" value={formatDuration(durationMs)} highlight={nodeStatus === "failed" ? "error" : "primary"} />
            <DetailField label="深度" value={String(node.depth ?? 0)} />
            <DetailField label="开始时间" value={formatDateTime(node.startTime ?? undefined)} />
            <DetailField label="结束时间" value={formatDateTime(node.endTime ?? undefined)} />
            {node.className && <DetailField label="类" value={node.className} mono />}
            {node.methodName && <DetailField label="方法" value={node.methodName} mono />}
          </div>
          {node.errorMessage && (
              <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                <div className="text-xs">
                  <p className="font-medium text-red-800 mb-1">错误信息</p>
                  <p className="text-red-700 whitespace-pre-wrap break-all">{node.errorMessage}</p>
                </div>
              </div>
          )}
          {"inputJson" in node && node.inputJson && (
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">输入数据</p>
                <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all text-slate-700">
                  {tryPrettyJson(node.inputJson)}
                </pre>
              </div>
          )}
          {"outputJson" in node && node.outputJson && (
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">输出数据</p>
                <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all text-slate-700">
                  {tryPrettyJson(node.outputJson)}
                </pre>
              </div>
          )}
          {node.extraData && (
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">额外数据</p>
                <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all text-slate-700">
                  {tryPrettyJson(node.extraData)}
                </pre>
              </div>
          )}
        </CardContent>
      </Card>
  );
}

function DetailField({
                       label,
                       value,
                       mono,
                       copyable,
                       highlight
                     }: {
  label: string;
  value: string;
  mono?: boolean;
  copyable?: boolean;
  highlight?: "primary" | "error";
}) {
  const highlightClass = highlight === "error"
      ? "text-red-600 font-medium"
      : highlight === "primary"
          ? "text-blue-600 font-medium"
          : "text-slate-700";
  return (
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-slate-500 shrink-0">{label}</span>
        <span
            className={cn(
                "truncate",
                mono && "font-mono",
                highlightClass,
                copyable && "cursor-pointer hover:text-blue-600 transition-colors"
            )}
            title={value}
            onClick={copyable ? () => copyToClipboard(value, label) : undefined}
        >
          {value}
        </span>
        {copyable && (
            <Copy className="h-3 w-3 text-slate-300 shrink-0" />
        )}
      </div>
  );
}

function tryPrettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function parseTraceJson(raw?: string | null): any {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function getNodeInput(node?: RagTraceDetail["nodes"][number] | null): any {
  const parsed = parseTraceJson(node?.inputJson);
  return parsed?.data ?? parsed;
}

function getNodeOutput(node?: RagTraceDetail["nodes"][number] | null): any {
  const parsed = parseTraceJson(node?.outputJson);
  return parsed?.data ?? parsed;
}

function findNode(nodes: RagTraceDetail["nodes"], nodeType: string) {
  return nodes.find((node) => node.nodeType === nodeType);
}

function truncateText(value?: string | null, limit = 260): string {
  const text = (value || "").trim();
  if (!text) return "—";
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

function markdownCell(value?: string | number | null): string {
  const text = value === null || value === undefined || value === "" ? "—" : String(value);
  return text.replace(/\|/g, "\\|").replace(/\r?\n/g, "<br>");
}

function markdownCodeFence(language: string, content: string): string {
  let fence = "```";
  while (content.includes(fence)) {
    fence += "`";
  }
  return `${fence}${language}\n${content}\n${fence}`;
}

function safeFilePart(value: string): string {
  return value
      .replace(/[\\/:*?"<>|]+/g, "-")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 120);
}

function buildTraceExportFileName(run: RagTraceDetail["run"]): string {
  const startedAt = run.startTime ? new Date(run.startTime) : new Date();
  const timestamp = Number.isNaN(startedAt.getTime())
      ? new Date().toISOString()
      : startedAt.toISOString();
  const safeTime = timestamp.replace(/[:.]/g, "-");
  const tracePart = safeFilePart(run.traceId || "unknown-trace");
  return `rag-trace-${tracePart}-${safeTime}.md`;
}

function downloadTextFile(fileName: string, content: string, type = "text/markdown;charset=utf-8") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function buildTraceExportMarkdown(detail: RagTraceDetail): string {
  const run = detail.run;
  const nodes = detail.nodes || [];
  const exportedAt = formatDateTime(Date.now());
  const userName = run.userName || run.username || run.userId || "—";
  const failedNodes = nodes.filter((node) => {
    const status = normalizeStatus(node.status);
    return status === "failed" || status === "timeout";
  });

  const mergeNode = findNode(nodes, "ClarificationMerge");
  const finalNode = findNode(nodes, "LLMFinalAnswer");
  const llmNode = findNode(nodes, "LLMCall");
  const clarifyNode = findNode(nodes, "ClarifyResponse");
  const contextNode = findNode(nodes, "ContextAssemble");
  const promptNode = findNode(nodes, "PromptBuild");
  const recommendNode = findNode(nodes, "RecommendQuestions");

  const mergeInput = getNodeInput(mergeNode);
  const mergeOutput = getNodeOutput(mergeNode);
  const finalOutput = getNodeOutput(finalNode);
  const llmOutput = getNodeOutput(llmNode);
  const clarifyOutput = getNodeOutput(clarifyNode);
  const contextOutput = getNodeOutput(contextNode);
  const promptOutput = getNodeOutput(promptNode);
  const recommendOutput = getNodeOutput(recommendNode);

  const originalQuestion = mergeInput?.original_question || run.question || "";
  const effectiveQuestion = mergeOutput?.effective_question || run.question || "";
  const finalAnswerSummary = finalOutput?.answer_summary || llmOutput?.answer || "";
  const clarifyQuestions = Array.isArray(clarifyOutput?.clarifying_questions)
      ? clarifyOutput.clarifying_questions
      : [];

  const stageRows = END_TO_END_STAGES.map((stage) => {
    const stageNodes = nodes.filter((node) => stage.nodeTypes.includes(node.nodeType || ""));
    const hasFailed = stageNodes.some((node) => {
      const status = normalizeStatus(node.status);
      return status === "failed" || status === "timeout";
    });
    const hasRunning = stageNodes.some((node) => normalizeStatus(node.status) === "running");
    const status = !stageNodes.length ? "未记录" : hasFailed ? "异常" : hasRunning ? "运行中" : "完成";
    const duration = stageNodes.reduce((sum, node) => sum + resolveNodeDuration(node), 0);
    const nodeNames = stageNodes
        .map((node) => prettifyNodeName(node.nodeName || node.nodeType || node.nodeId))
        .join(", ");
    return `| ${markdownCell(stage.title)} | ${markdownCell(status)} | ${markdownCell(stageNodes.length)} | ${markdownCell(formatDuration(duration))} | ${markdownCell(nodeNames)} |`;
  }).join("\n");

  const nodeRows = nodes.length
      ? nodes.map((node, index) => {
        const displayName = prettifyNodeName(node.nodeName || node.methodName || node.nodeId);
        return `| ${index + 1} | ${markdownCell(displayName)} | ${markdownCell(node.nodeType)} | ${markdownCell(statusLabel(node.status))} | ${markdownCell(formatDuration(resolveNodeDuration(node)))} | ${markdownCell(formatDateTime(node.startTime ?? undefined))} | ${markdownCell(formatDateTime(node.endTime ?? undefined))} | ${markdownCell(node.parentNodeId)} |`;
      }).join("\n")
      : "| — | — | — | — | — | — | — | — |";

  const nodeDetails = nodes.length
      ? nodes.map((node, index) => {
        const displayName = prettifyNodeName(node.nodeName || node.methodName || node.nodeId);
        const blocks = [
          `### ${index + 1}. ${displayName}`,
          `- Node Id: \`${node.nodeId}\``,
          `- Parent Node Id: \`${node.parentNodeId || "—"}\``,
          `- 类型：${node.nodeType || "—"}`,
          `- 状态：${statusLabel(node.status)}`,
          `- 耗时：${formatDuration(resolveNodeDuration(node))}`,
          `- 开始时间：${formatDateTime(node.startTime ?? undefined)}`,
          `- 结束时间：${formatDateTime(node.endTime ?? undefined)}`,
          node.errorMessage
              ? `\n**错误信息**\n\n${markdownCodeFence("text", node.errorMessage)}`
              : "",
          node.inputJson
              ? `\n**输入 JSON**\n\n${markdownCodeFence("json", tryPrettyJson(node.inputJson))}`
              : "\n**输入 JSON**：无",
          node.outputJson
              ? `\n**输出 JSON**\n\n${markdownCodeFence("json", tryPrettyJson(node.outputJson))}`
              : "\n**输出 JSON**：无",
          node.extraData
              ? `\n**额外数据**\n\n${markdownCodeFence("json", tryPrettyJson(node.extraData))}`
              : "\n**额外数据**：无"
        ];
        return blocks.filter(Boolean).join("\n");
      }).join("\n\n")
      : "暂无节点详情。";

  return [
    "# RAG 单轮问答全链路详情",
    "",
    `导出时间：${exportedAt}`,
    "",
    "## 运行概览",
    "",
    "| 字段 | 值 |",
    "| --- | --- |",
    `| Trace Id | ${markdownCell(run.traceId)} |`,
    `| 会话 ID | ${markdownCell(run.sessionId || run.conversationId)} |`,
    `| 用户 | ${markdownCell(userName)} |`,
    `| 状态 | ${markdownCell(statusLabel(run.status))} |`,
    `| 链路名称 | ${markdownCell(run.traceName)} |`,
    `| 入口方法 | ${markdownCell(run.entryMethod)} |`,
    `| 开始时间 | ${markdownCell(formatDateTime(run.startTime ?? undefined))} |`,
    `| 结束时间 | ${markdownCell(formatDateTime(run.endTime ?? undefined))} |`,
    `| 总耗时 | ${markdownCell(formatDuration(run.durationMs ?? undefined))} |`,
    `| 首包耗时 | ${markdownCell(run.ttftMs != null ? formatDuration(run.ttftMs) : "—")} |`,
    `| 节点数 | ${markdownCell(nodes.length)} |`,
    `| 失败节点数 | ${markdownCell(failedNodes.length)} |`,
    "",
    "## 问答摘要",
    "",
    "### 用户原始问题",
    "",
    originalQuestion || "—",
    "",
    "### 有效问题",
    "",
    effectiveQuestion || "—",
    "",
    clarifyQuestions.length ? "### 追问问题" : "### 模型最终回答摘要",
    "",
    clarifyQuestions.length
        ? clarifyQuestions.map((question: string, index: number) => `${index + 1}. ${question}`).join("\n")
        : finalAnswerSummary || "—",
    "",
    "### 生成指标",
    "",
    "| 指标 | 值 |",
    "| --- | --- |",
    `| 回答字符数 | ${markdownCell(finalOutput?.answer_chars)} |`,
    `| 思考字符数 | ${markdownCell(finalOutput?.thinking_chars)} |`,
    `| 引用标记数 | ${markdownCell(finalOutput?.citation_marker_count)} |`,
    `| 总引用数 | ${markdownCell(contextOutput?.total_reference_count)} |`,
    `| 推荐问题数 | ${markdownCell(recommendOutput?.recommended_question_count)} |`,
    `| Prompt 长度 | ${markdownCell(promptOutput?.prompt_length)} |`,
    `| 引用范围 | ${markdownCell(promptOutput?.reference_range)} |`,
    "",
    "## 阶段摘要",
    "",
    "| 阶段 | 状态 | 节点数 | 累计耗时 | 节点 |",
    "| --- | --- | ---: | ---: | --- |",
    stageRows,
    "",
    "## 节点列表",
    "",
    "| 序号 | 节点 | 类型 | 状态 | 耗时 | 开始时间 | 结束时间 | 父节点 |",
    "| ---: | --- | --- | --- | ---: | --- | --- | --- |",
    nodeRows,
    "",
    "## 节点详情",
    "",
    nodeDetails,
    "",
    "## 原始详情 JSON",
    "",
    markdownCodeFence("json", JSON.stringify(detail, null, 2)),
    ""
  ].join("\n");
}

const END_TO_END_STAGES: Array<{
  key: string;
  title: string;
  description: string;
  nodeTypes: string[];
}> = [
  {
    key: "request",
    title: "用户请求",
    description: "问题进入后端并加载运行配置",
    nodeTypes: ["UserQuestionReceived", "AuthLoadSettings"]
  },
  {
    key: "routing",
    title: "路由与检索",
    description: "意图分类、检索查询、ES 混合召回和重排",
    nodeTypes: ["IntentClassify", "RetrievalQueryBuild", "ESHybridSearch", "RerankChunks", "VectorRetrieve"]
  },
  {
    key: "clarification",
    title: "追问与上下文",
    description: "追问判断、追问合并、快速解析文档和上下文组装",
    nodeTypes: ["ClarificationMerge", "AmbiguityAudit", "ClarifyResponse", "QuickParseLoad", "ContextAssemble"]
  },
  {
    key: "generation",
    title: "模型生成",
    description: "Prompt 构建、LLM 流式生成、首包和最终回答",
    nodeTypes: ["PromptBuild", "LLMStreamStart", "LLMFirstToken", "LLMAnswerStream", "LLMFinalAnswer", "RecommendQuestions", "LLMCall"]
  },
  {
    key: "streaming",
    title: "返回前端",
    description: "引用文档、推荐问题、结束或错误事件",
    nodeTypes: ["SSEDocumentsSent", "SSEEndSent", "SSEErrorSent"]
  },
  {
    key: "persistence",
    title: "持久化",
    description: "回答写入消息表并更新会话标题",
    nodeTypes: ["PersistMessage", "SessionTitleUpdate"]
  }
];

function EndToEndTraceCard({
                             detail,
                             onSelectNode
                           }: {
  detail: RagTraceDetail;
  onSelectNode: (nodeId: string) => void;
}) {
  const nodes = detail.nodes || [];
  const run = detail.run;
  const mergeNode = findNode(nodes, "ClarificationMerge");
  const finalNode = findNode(nodes, "LLMFinalAnswer");
  const llmNode = findNode(nodes, "LLMCall");
  const persistNode = findNode(nodes, "PersistMessage");
  const clarifyNode = findNode(nodes, "ClarifyResponse");
  const sseEndNode = findNode(nodes, "SSEEndSent");
  const promptNode = findNode(nodes, "PromptBuild");
  const contextNode = findNode(nodes, "ContextAssemble");
  const recommendNode = findNode(nodes, "RecommendQuestions");

  const mergeInput = getNodeInput(mergeNode);
  const mergeOutput = getNodeOutput(mergeNode);
  const finalOutput = getNodeOutput(finalNode);
  const llmOutput = getNodeOutput(llmNode);
  const persistOutput = getNodeOutput(persistNode);
  const clarifyOutput = getNodeOutput(clarifyNode);
  const sseOutput = getNodeOutput(sseEndNode);
  const promptOutput = getNodeOutput(promptNode);
  const contextOutput = getNodeOutput(contextNode);
  const recommendOutput = getNodeOutput(recommendNode);

  const finalAnswerSummary =
      finalOutput?.answer_summary ||
      llmOutput?.answer ||
      "";
  const hasFinalAnswer = Boolean(finalNode || finalAnswerSummary);
  const hasClarify = Boolean(clarifyNode);
  const persistStatus = normalizeStatus(persistNode?.status);
  const sseEndStatus = normalizeStatus(sseEndNode?.status);

  const statusItems = [
    {
      label: "最终回答",
      value: hasFinalAnswer ? "已生成" : hasClarify ? "等待补充" : "未完成",
      variant: hasFinalAnswer ? "success" : hasClarify ? "warning" : "error"
    },
    {
      label: "SSE 结束",
      value: sseEndNode ? (sseOutput?.end_type || "已发送") : "未记录",
      variant: sseEndStatus === "failed" ? "error" : sseEndNode ? "success" : "warning"
    },
    {
      label: "消息落库",
      value: persistNode ? (persistStatus === "failed" ? "失败" : "成功") : "未记录",
      variant: persistStatus === "failed" ? "error" : persistNode ? "success" : "warning"
    }
  ];

  return (
      <Card className="border-slate-200">
        <CardHeader className="py-4 px-5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Crosshair className="h-4 w-4 text-blue-600" />
              <CardTitle className="text-sm font-semibold text-slate-800">
                端到端问答链路
              </CardTitle>
            </div>
            <div className="flex flex-wrap gap-2">
              {statusItems.map((item) => (
                  <span
                      key={item.label}
                      className={cn(
                          "inline-flex items-center gap-1 rounded px-2 py-1 text-xs",
                          item.variant === "success" && "bg-emerald-50 text-emerald-700 border border-emerald-100",
                          item.variant === "warning" && "bg-amber-50 text-amber-700 border border-amber-100",
                          item.variant === "error" && "bg-red-50 text-red-700 border border-red-100"
                      )}
                  >
                    <span className="text-slate-500">{item.label}</span>
                    <span className="font-medium">{item.value}</span>
                  </span>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="px-5 pb-5 pt-0 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
              <div className="text-xs font-medium text-slate-500 mb-1">用户原始问题</div>
              <div className="text-sm text-slate-800 whitespace-pre-wrap break-words">
                {truncateText(mergeInput?.original_question || run.question, 420)}
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
              <div className="text-xs font-medium text-slate-500 mb-1">有效问题</div>
              <div className="text-sm text-slate-800 whitespace-pre-wrap break-words">
                {truncateText(mergeOutput?.effective_question || run.question, 420)}
              </div>
            </div>
          </div>

          {hasClarify && !hasFinalAnswer ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3">
                <div className="text-xs font-medium text-amber-700 mb-2">本轮触发追问，未进入正式最终回答</div>
                <ol className="list-decimal pl-5 space-y-1 text-sm text-amber-900">
                  {(clarifyOutput?.clarifying_questions || []).map((question: string, index: number) => (
                      <li key={`${question}-${index}`}>{question}</li>
                  ))}
                </ol>
              </div>
          ) : (
              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <div className="flex items-center justify-between gap-3 mb-2">
                  <div className="text-xs font-medium text-slate-500">模型最终回答摘要</div>
                  <div className="flex flex-wrap gap-2 text-[11px] text-slate-500">
                    <span>回答 {finalOutput?.answer_chars ?? "—"} 字</span>
                    <span>思考 {finalOutput?.thinking_chars ?? "—"} 字</span>
                    <span>引用标记 {finalOutput?.citation_marker_count ?? "—"} 个</span>
                    <span>推荐问题 {recommendOutput?.recommended_question_count ?? persistOutput?.recommended_question_count ?? "—"} 个</span>
                    <span>总引用 {contextOutput?.total_reference_count ?? "—"} 条</span>
                  </div>
                </div>
                <div className="text-sm text-slate-800 whitespace-pre-wrap break-words">
                  {truncateText(finalAnswerSummary, 900)}
                </div>
                {promptOutput?.prompt_length ? (
                    <div className="mt-2 text-xs text-slate-500">
                      Prompt 长度 {promptOutput.prompt_length}，引用范围 {promptOutput.reference_range || "—"}
                    </div>
                ) : null}
              </div>
          )}

          <div className="space-y-2">
            {END_TO_END_STAGES.map((stage) => {
              const stageNodes = nodes.filter((node) => stage.nodeTypes.includes(node.nodeType || ""));
              const failed = stageNodes.some((node) => normalizeStatus(node.status) === "failed");
              const success = stageNodes.length > 0 && stageNodes.every((node) => normalizeStatus(node.status) !== "failed");
              return (
                  <div key={stage.key} className="grid grid-cols-[150px_1fr] gap-4 rounded-lg border border-slate-200 bg-white px-3 py-2">
                    <div className="flex items-start gap-2">
                      <span
                          className={cn(
                              "mt-1 h-2.5 w-2.5 rounded-full shrink-0",
                              failed ? "bg-red-500" : success ? "bg-emerald-500" : "bg-slate-300"
                          )}
                      />
                      <div>
                        <div className="text-sm font-medium text-slate-800">{stage.title}</div>
                        <div className="text-[11px] text-slate-500">{stage.description}</div>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {stageNodes.length ? stageNodes.map((node) => (
                          <button
                              key={`${stage.key}-${node.nodeId}`}
                              type="button"
                              onClick={() => onSelectNode(node.nodeId)}
                              className={cn(
                                  "inline-flex items-center gap-1 rounded border px-2 py-1 text-xs transition-colors hover:border-blue-300 hover:bg-blue-50",
                                  normalizeStatus(node.status) === "failed"
                                      ? "border-red-200 bg-red-50 text-red-700"
                                      : "border-slate-200 bg-slate-50 text-slate-700"
                              )}
                          >
                            <span>{prettifyNodeName(node.nodeName || node.nodeType)}</span>
                            <span className="text-slate-400">{formatDuration(resolveNodeDuration(node))}</span>
                          </button>
                      )) : (
                          <span className="text-xs text-slate-400">未记录</span>
                      )}
                    </div>
                  </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
  );
}

// ============ 主组件 ============

export function RagTraceDetailPage() {
  const params = useParams<{ traceId: string }>();
  const traceId = decodeTraceId(params.traceId);
  const detailRequestRef = useRef(0);
  const [detail, setDetail] = useState<RagTraceDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);

  const loadDetail = async (nextTraceId: string) => {
    if (!nextTraceId) return;
    const requestId = ++detailRequestRef.current;
    setDetailLoading(true);
    try {
      const result = await getRagTraceDetail(nextTraceId);
      if (detailRequestRef.current !== requestId) return;
      setDetail(result);
    } catch (error) {
      if (detailRequestRef.current !== requestId) return;
      toast.error(getErrorMessage(error, "加载链路详情失败"));
      console.error(error);
      setDetail(null);
    } finally {
      if (detailRequestRef.current !== requestId) return;
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    if (!traceId) {
      detailRequestRef.current += 1;
      setDetail(null);
      setDetailLoading(false);
      return;
    }
    loadDetail(traceId);
  }, [traceId]);

  const selectedRun = detail?.run || null;

  const timeline = useMemo(() => {
    const nodes = detail?.nodes || [];
    if (!nodes.length && !selectedRun) return { totalWindowMs: 0, nodes: [] as any[] };

    const normalized = nodes.map((node) => {
      const startTs = toTimestamp(node.startTime);
      const endTs = toTimestamp(node.endTime);
      const resolvedDurationMs = resolveNodeDuration(node);
      const depthValue = Math.max(0, Number(node.depth ?? 0)) + 1;
      const resolvedStartTs = startTs ?? 0;
      const resolvedEndTs = endTs ?? (resolvedStartTs > 0 ? resolvedStartTs + resolvedDurationMs : 0);
      return { ...node, depthValue, resolvedDurationMs, startTs: resolvedStartTs, endTs: resolvedEndTs };
    });

    const withTime = normalized.filter((item) => item.startTs > 0);
    const runStartTs = toTimestamp(selectedRun?.startTime);
    const baseStart = runStartTs
        ?? (withTime.length
            ? withTime.reduce((min, item) => Math.min(min, item.startTs), withTime[0].startTs)
            : Date.now());
    const runEndTs = toTimestamp(selectedRun?.endTime);
    const maxEnd = withTime.length
        ? withTime.reduce((max, item) => Math.max(max, item.endTs || item.startTs), withTime[0].endTs || withTime[0].startTs)
        : baseStart;
    const runDuration = Number(selectedRun?.durationMs ?? 0);
    const resolvedRunEnd = runEndTs ?? (runDuration > 0 ? baseStart + runDuration : maxEnd);
    const windowDuration = Math.max(resolvedRunEnd - baseStart, runDuration, maxEnd - baseStart, 1);

    const rootRow = selectedRun
        ? {
          traceId: selectedRun.traceId,
          nodeId: "__root__",
          parentNodeId: null,
          depth: -1,
          nodeType: "ROOT",
          nodeName: selectedRun.traceName || "rag-stream-chat",
          className: null,
          methodName: selectedRun.entryMethod || null,
          status: selectedRun.status,
          errorMessage: selectedRun.errorMessage,
          durationMs: selectedRun.durationMs ?? null,
          startTime: selectedRun.startTime ?? null,
          endTime: selectedRun.endTime ?? null,
          extraData: null,
          depthValue: 0,
          resolvedDurationMs: Math.max(resolvedRunEnd - baseStart, 1),
          startTs: baseStart,
          endTs: resolvedRunEnd
        }
        : null;

    // 使用 parentNodeId 构建树，DFS 遍历确定显示顺序
    const childrenMap = new Map<string, typeof normalized>();
    const treeRoots: typeof normalized = [];

    for (const node of normalized) {
      const parentId = node.parentNodeId;
      if (!parentId) {
        treeRoots.push(node);
      } else {
        let siblings = childrenMap.get(parentId);
        if (!siblings) {
          siblings = [];
          childrenMap.set(parentId, siblings);
        }
        siblings.push(node);
      }
    }

    const sortSiblings = (list: typeof normalized) =>
        list.sort((a, b) => a.startTs - b.startTs || a.depthValue - b.depthValue);

    sortSiblings(treeRoots);
    for (const siblings of childrenMap.values()) {
      sortSiblings(siblings);
    }

    const ordered: typeof normalized = [];
    const dfsStack = [...treeRoots].reverse();
    while (dfsStack.length > 0) {
      const node = dfsStack.pop()!;
      ordered.push(node);
      const children = childrenMap.get(node.nodeId);
      if (children) {
        for (let i = children.length - 1; i >= 0; i--) {
          dfsStack.push(children[i]);
        }
      }
    }

    const orderedSet = new Set(ordered.map(n => n.nodeId));
    for (const node of normalized) {
      if (!orderedSet.has(node.nodeId)) {
        ordered.push(node);
      }
    }

    const rows = [
      ...(rootRow ? [rootRow] : []),
      ...ordered
    ].map((node) => {
      const offsetMs = node.startTs > 0 ? Math.max(0, node.startTs - baseStart) : 0;
      const leftPercent = clamp((offsetMs / windowDuration) * 100, 0, 99.2);
      const widthPercent = clamp(
          (Math.max(node.resolvedDurationMs, 1) / windowDuration) * 100,
          0.8,
          100 - leftPercent
      );
      return { ...node, offsetMs, leftPercent, widthPercent };
    });

    return { totalWindowMs: windowDuration, nodes: rows };
  }, [detail?.nodes, selectedRun]);

  const stats = useMemo(() => {
    const nodes = detail?.nodes || [];
    const total = nodes.length;
    const failed = nodes.filter((n) => normalizeStatus(n.status) === "failed").length;
    const success = nodes.filter((n) => normalizeStatus(n.status) === "success").length;
    const running = nodes.filter((n) => normalizeStatus(n.status) === "running").length;

    const durations = nodes.map(n => resolveNodeDuration(n));
    const avgDuration = total > 0 ? Math.round(durations.reduce((a, b) => a + b, 0) / total) : 0;

    const sortedByDuration = [...nodes].sort((a, b) => resolveNodeDuration(b) - resolveNodeDuration(a));
    const topSlowestId = sortedByDuration[0]?.nodeId;

    const userTtftNode = nodes.find(n => (n.nodeType || "").toUpperCase() === "USER_TTFT");
    const llmTtftNode = nodes.find(n => (n.nodeType || "").toUpperCase() === "LLM_TTFT");
    const ttftMs = userTtftNode
        ? resolveNodeDuration(userTtftNode)
        : (llmTtftNode ? resolveNodeDuration(llmTtftNode) : null);
    const ttftKind: "user" | "llm" | null = userTtftNode ? "user" : (llmTtftNode ? "llm" : null);

    return { total, failed, success, running, avgDuration, topSlowestId, ttftMs, ttftKind };
  }, [detail?.nodes]);

  const intentInfo = useMemo(() => {
    const nodes = detail?.nodes || [];
    const intentNode = nodes.find(n => n.nodeType === "IntentClassify");
    if (!intentNode?.outputJson) return null;
    try {
      const parsed = JSON.parse(intentNode.outputJson);
      if (parsed.intent_code) {
        return {
          matched: true as const,
          code: parsed.intent_code as string,
          name: (parsed.name || parsed.intent_code) as string,
          kind: parsed.kind as number | undefined,
          score: parsed.score as number | undefined,
        };
      }
      return { matched: false as const, reason: "no_intent_matched" };
    } catch {
      return { matched: false as const, reason: "parse_error" };
    }
  }, [detail?.nodes]);

  const activeNode = useMemo(() => {
    if (!activeNodeId) return null;
    return detail?.nodes?.find(n => n.nodeId === activeNodeId) || null;
  }, [detail?.nodes, activeNodeId]);

  const handleExportDetail = () => {
    if (!detail) {
      toast.error("暂无可导出的链路详情");
      return;
    }

    try {
      const content = buildTraceExportMarkdown(detail);
      downloadTextFile(buildTraceExportFileName(detail.run), content);
      toast.success("单轮问答全链路详情已导出");
    } catch (error) {
      console.error(error);
      toast.error("导出链路详情失败");
    }
  };

  if (detailLoading) {
    return (
        <div className="min-h-[400px] flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-slate-500">
            <Loader2 className="h-8 w-8 animate-spin" />
            <p>加载链路详情中...</p>
          </div>
        </div>
    );
  }

  if (!traceId || !selectedRun) {
    return (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-sm">
              <Link to="/admin/traces" className="text-slate-500 hover:text-slate-700">
                链路追踪
              </Link>
              <span className="text-slate-300">/</span>
              <span className="text-slate-400">详情</span>
            </div>
            <Button
                asChild
                variant="outline"
                size="sm"
                className="text-slate-600 hover:text-slate-800"
            >
              <Link to="/admin/traces">
                <ArrowLeft className="mr-1.5 h-4 w-4" />
                返回列表
              </Link>
            </Button>
          </div>
          <div className="min-h-[300px] flex items-center justify-center">
            <div className="text-center text-slate-500">
              <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-slate-300" />
              <p>{!traceId ? "缺少 Trace Id" : "暂无数据"}</p>
            </div>
          </div>
        </div>
    );
  }

  return (
      <div className="space-y-4 pb-8">
        {/* 标题栏 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-sm">
              <Link
                  to="/admin/traces"
                  className="text-slate-500 hover:text-slate-700 transition-colors"
              >
                RAG 链路列表
              </Link>
              <span className="text-slate-300">/</span>
            </div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-slate-900">
                {selectedRun.traceName || "未命名链路"}
              </h1>
              <Badge variant={statusBadgeVariant(selectedRun.status)} className="text-xs">
                {statusLabel(selectedRun.status)}
              </Badge>
            </div>
          </div>

          {/* 右侧按钮组 */}
          <div className="flex items-center gap-2">
            {selectedRun.sessionId && (
                <Button
                    asChild
                    variant="outline"
                    size="sm"
                    className="text-slate-600 hover:text-slate-800"
                >
                  <Link to={`/admin/traces/conversations/${encodeURIComponent(selectedRun.sessionId)}`}>
                    返回会话
                  </Link>
                </Button>
            )}
            <Button
                asChild
                variant="outline"
                size="sm"
                className="text-slate-600 hover:text-slate-800"
            >
              <Link to="/admin/traces">
                <ArrowLeft className="mr-1.5 h-4 w-4" />
                返回列表
              </Link>
            </Button>
            <Button
                variant="outline"
                size="sm"
                className="text-slate-600 hover:text-slate-800"
                onClick={handleExportDetail}
                disabled={!detail || detailLoading}
            >
              <Download className="mr-1.5 h-4 w-4" />
              导出
            </Button>
            <Button
                variant="outline"
                size="sm"
                className="text-slate-600 hover:text-slate-800"
                onClick={() => loadDetail(traceId)}
                disabled={detailLoading}
            >
              <RefreshCw className={cn("mr-1.5 h-4 w-4", detailLoading && "animate-spin")} />
              刷新
            </Button>
          </div>
        </div>

        {/* 元信息 */}
        <div className="flex items-center gap-4 text-xs text-slate-500">
        <span
            className="font-mono cursor-pointer hover:text-slate-700 flex items-center gap-1 transition-colors"
            onClick={() => copyToClipboard(traceId, "Trace Id")}
            title="点击复制 Trace Id"
        >
          <Hash className="h-3 w-3" />
          {traceId.length > 28 ? `${traceId.slice(0, 12)}...${traceId.slice(-8)}` : traceId}
        </span>
          {selectedRun.sessionId && (
              <span
                  className="font-mono cursor-pointer hover:text-slate-700 flex items-center gap-1 transition-colors"
                  onClick={() => copyToClipboard(selectedRun.sessionId!, "Session Id")}
                  title="点击复制 Session Id"
              >
                <Hash className="h-3 w-3" />
                {selectedRun.sessionId.length > 28
                    ? `${selectedRun.sessionId.slice(0, 12)}...${selectedRun.sessionId.slice(-8)}`
                    : selectedRun.sessionId}
              </span>
          )}
          <span className="flex items-center gap-1">
          <Calendar className="h-3 w-3" />
            {formatDateTime(selectedRun.startTime ?? undefined)}
        </span>
          {(selectedRun.username || selectedRun.userId) && (
              <span className="flex items-center gap-1">
            <User className="h-3 w-3" />
                {selectedRun.username || selectedRun.userId}
          </span>
          )}
        </div>

        {/* 错误提示 */}
        {selectedRun.errorMessage && (
            <div className="flex items-start gap-3 p-3 bg-red-50 border border-red-200 rounded-lg">
              <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
              <div className="text-sm">
                <span className="font-medium text-red-800">执行出错：</span>
                <span className="text-red-600 ml-1">{selectedRun.errorMessage}</span>
              </div>
            </div>
        )}

        <EndToEndTraceCard
            detail={detail!}
            onSelectNode={(nodeId) => setActiveNodeId(nodeId)}
        />

        {/* 意图分类 */}
        {intentInfo && (
            <Card className={intentInfo.matched ? "border-blue-200 bg-blue-50/60" : "border-amber-200 bg-amber-50/60"}>
              <CardContent className="py-4 px-5">
                <div className="flex items-start gap-4">
                  <div className={cn(
                      "h-10 w-10 rounded-full flex items-center justify-center shrink-0",
                      intentInfo.matched ? "bg-blue-100 text-blue-600" : "bg-amber-100 text-amber-600"
                  )}>
                    {intentInfo.matched ? <Target className="h-5 w-5" /> : <HelpCircle className="h-5 w-5" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-slate-700">意图分类</span>
                      {intentInfo.matched ? (
                          <Badge variant="default" className="text-xs bg-blue-100 text-blue-700 hover:bg-blue-100">
                            已匹配
                          </Badge>
                      ) : (
                          <Badge variant="secondary" className="text-xs bg-amber-100 text-amber-700 hover:bg-amber-100">
                            未匹配
                          </Badge>
                      )}
                    </div>
                    {intentInfo.matched ? (
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                          <span className="font-semibold text-slate-900">
                            {intentInfo.name}
                          </span>
                          <span className="text-xs font-mono text-slate-500 bg-white px-1.5 py-0.5 rounded border border-slate-200">
                            {intentInfo.code}
                          </span>
                          {intentInfo.kind !== undefined && (
                              <span className="text-xs text-slate-500">
                                类型：{intentInfo.kind === 0 ? "领域" : intentInfo.kind === 1 ? "系统" : intentInfo.kind === 2 ? "数据" : String(intentInfo.kind)}
                              </span>
                          )}
                          {intentInfo.score !== undefined && (
                              <span className={cn(
                                  "text-xs font-mono px-1.5 py-0.5 rounded",
                                  intentInfo.score >= 0.8 ? "bg-emerald-100 text-emerald-700" :
                                      intentInfo.score >= 0.5 ? "bg-amber-100 text-amber-700" :
                                          "bg-red-100 text-red-700"
                              )}>
                                置信度：{(intentInfo.score * 100).toFixed(0)}%
                              </span>
                          )}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-600">
                          {intentInfo.reason === "parse_error"
                              ? "意图数据解析失败"
                              : "此次查询未命中任何意图节点，已走默认通用问答路由"}
                        </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
        )}

        {/* 指标条 */}
        <div className="flex items-center bg-slate-50 rounded-lg border border-slate-200 divide-x divide-slate-200">
          <MetricItem
              icon={Clock}
              label="总耗时"
              value={formatDuration(selectedRun.durationMs ?? undefined)}
              variant="primary"
          />
          {stats.ttftMs !== null && (
              <MetricItem
                  icon={Zap}
                  label={stats.ttftKind === "user" ? "首包" : "LLM 首包"}
                  value={formatDuration(stats.ttftMs)}
                  variant={stats.ttftKind === "user" ? "primary" : "success"}
              />
          )}
          <MetricItem
              icon={Activity}
              label="节点"
              value={stats.total}
          />
          <MetricItem
              icon={CheckCircle2}
              label="成功"
              value={stats.success}
              variant="success"
          />
          <MetricItem
              icon={XCircle}
              label="失败"
              value={stats.failed}
              variant={stats.failed > 0 ? "error" : "default"}
          />
          {stats.running > 0 && (
              <MetricItem
                  icon={Loader2}
                  label="运行中"
                  value={stats.running}
                  variant="warning"
              />
          )}
          <MetricItem
              icon={Zap}
              label="平均耗时"
              value={formatDuration(stats.avgDuration)}
          />
        </div>

        {/* 瀑布图 */}
        <Card>
          <CardHeader className="py-3 px-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-slate-700">
                执行时序
              </CardTitle>
              <span className="text-xs text-slate-500">
              窗口 {formatDuration(timeline.totalWindowMs)}
            </span>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {timeline.nodes.length === 0 ? (
                <div className="py-16 text-center text-slate-400">
                  <Activity className="h-10 w-10 mx-auto mb-3 opacity-50" />
                  <p>暂无节点记录</p>
                </div>
            ) : (
                <div>
                  <div className="grid grid-cols-[minmax(180px,1fr)_120px_2fr_100px] gap-4 px-4 py-2 text-xs font-medium text-slate-500 bg-slate-50 border-y border-slate-100">
                    <span>节点</span>
                    <span>类型</span>
                    <span>时间线</span>
                    <span className="text-right">耗时</span>
                  </div>

                  <div className="grid grid-cols-[minmax(180px,1fr)_120px_2fr_100px] gap-4 px-4 bg-white">
                    <div />
                    <div />
                    <TimeScale totalMs={timeline.totalWindowMs} />
                    <div />
                  </div>

                  <div className="divide-y divide-slate-50">
                    {timeline.nodes.map((node) => {
                      const nodeDisplayName = prettifyNodeName(node.nodeName || node.methodName || node.nodeId);
                      const nodeStatus = normalizeStatus(node.status);
                      const isTopSlowest = node.nodeId === stats.topSlowestId;
                      const isSelected = node.nodeId === activeNodeId;
                      const isRoot = node.nodeId === "__root__";

                      return (
                          <WaterfallRow
                              key={node.nodeId}
                              node={node}
                              nodeDisplayName={nodeDisplayName}
                              nodeStatus={nodeStatus}
                              isTopSlowest={isTopSlowest && !isRoot}
                              isSelected={isSelected}
                              isRoot={isRoot}
                              onSelect={isRoot ? undefined : () => setActiveNodeId(isSelected ? null : node.nodeId)}
                          />
                      );
                    })}
                  </div>
                </div>
            )}
          </CardContent>
        </Card>

        {activeNode && (
            <NodeDetailCard
                node={activeNode}
                onClose={() => setActiveNodeId(null)}
            />
        )}
      </div>
  );
}
