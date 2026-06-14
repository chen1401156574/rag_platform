import { ArrowRight, CheckCircle2, Clock3, FileCheck2, HelpCircle, Loader2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { RagTraceConversationRun } from "@/services/ragTraceService";
import { formatDateTime, formatDuration, normalizeStatus, statusBadgeVariant } from "@/pages/admin/traces/traceUtils";

interface ConversationRunsTimelineProps {
  runs: RagTraceConversationRun[];
  selectedTraceId?: string | null;
  onSelectRun: (traceId: string) => void;
  onOpenRun: (traceId: string) => void;
}

const statusText = (status?: string | null) => {
  const normalized = normalizeStatus(status);
  if (normalized === "success") return "成功";
  if (normalized === "failed" || normalized === "timeout") return "失败";
  if (normalized === "running") return "运行中";
  if (normalized === "clarify_needed") return "等待补充";
  return status || "未知";
};

const StatusIcon = ({ status }: { status?: string | null }) => {
  const normalized = normalizeStatus(status);
  if (normalized === "failed" || normalized === "timeout") return <XCircle className="h-4 w-4 text-red-500" />;
  if (normalized === "running") return <Loader2 className="h-4 w-4 animate-spin text-amber-500" />;
  if (normalized === "clarify_needed") return <HelpCircle className="h-4 w-4 text-amber-500" />;
  return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
};

export function ConversationRunsTimeline({
  runs,
  selectedTraceId,
  onSelectRun,
  onOpenRun
}: ConversationRunsTimelineProps) {
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="border-b border-slate-100 px-5 py-4">
        <CardTitle className="text-base">多轮问答时间线</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {runs.length === 0 ? (
          <div className="flex min-h-[240px] items-center justify-center text-sm text-slate-500">
            暂无轮次记录
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {runs.map((run, index) => {
              const selected = run.traceId === selectedTraceId;
              return (
                <div
                  key={run.traceId}
                  className={cn(
                    "grid gap-4 px-5 py-4 transition-colors lg:grid-cols-[44px_minmax(0,1fr)_220px]",
                    selected ? "bg-indigo-50/60" : "hover:bg-slate-50"
                  )}
                >
                  <div className="flex lg:flex-col lg:items-center">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-sm font-semibold text-slate-700">
                      {run.turnNo || index + 1}
                    </div>
                    {index < runs.length - 1 ? (
                      <div className="mt-2 hidden h-full w-px bg-slate-200 lg:block" />
                    ) : null}
                  </div>

                  <button
                    type="button"
                    className="min-w-0 text-left"
                    onClick={() => onSelectRun(run.traceId)}
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <StatusIcon status={run.status} />
                      <Badge variant={statusBadgeVariant(run.status)}>
                        {statusText(run.status)}
                      </Badge>
                      {run.hasClarify ? <Badge variant="secondary">追问链路</Badge> : null}
                      {run.persisted === false ? <Badge variant="destructive">落库失败</Badge> : null}
                      {run.persisted === true ? <Badge variant="outline">已落库</Badge> : null}
                    </div>
                    <p className="line-clamp-2 text-sm font-medium text-slate-900">
                      {run.question || "无问题内容"}
                    </p>
                    {run.finalAnswerSummary ? (
                      <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">
                        {run.finalAnswerSummary}
                      </p>
                    ) : (
                      <p className="mt-2 text-xs text-slate-400">
                        {normalizeStatus(run.status) === "clarify_needed" ? "本轮触发追问，未进入正式最终回答。" : "暂无最终回答摘要。"}
                      </p>
                    )}
                  </button>

                  <div className="flex flex-col gap-2 lg:items-end">
                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-500 lg:w-full">
                      <div className="rounded-md border border-slate-200 bg-white px-2 py-1">
                        <span className="block text-slate-400">意图</span>
                        <span className="block truncate text-slate-700" title={run.intentName || run.intentCode || undefined}>
                          {run.intentName || run.intentCode || "-"}
                        </span>
                      </div>
                      <div className="rounded-md border border-slate-200 bg-white px-2 py-1">
                        <span className="block text-slate-400">节点</span>
                        <span className="text-slate-700">
                          {run.nodeCount ?? 0} / 失败 {run.failedNodeCount ?? 0}
                        </span>
                      </div>
                      <div className="rounded-md border border-slate-200 bg-white px-2 py-1">
                        <span className="flex items-center gap-1 text-slate-400">
                          <Clock3 className="h-3 w-3" />
                          耗时
                        </span>
                        <span className="text-slate-700">{formatDuration(run.durationMs ?? undefined)}</span>
                      </div>
                      <div className="rounded-md border border-slate-200 bg-white px-2 py-1">
                        <span className="flex items-center gap-1 text-slate-400">
                          <FileCheck2 className="h-3 w-3" />
                          TTFT
                        </span>
                        <span className="text-slate-700">{formatDuration(run.ttftMs ?? undefined)}</span>
                      </div>
                    </div>
                    <div className="text-xs text-slate-400">
                      {formatDateTime(run.startTime ?? undefined)}
                    </div>
                    <Button size="sm" onClick={() => onOpenRun(run.traceId)}>
                      查看单轮
                      <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
