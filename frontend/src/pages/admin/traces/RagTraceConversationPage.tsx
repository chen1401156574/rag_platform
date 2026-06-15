import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Copy, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { ConversationRunsTimeline } from "@/pages/admin/traces/components/ConversationRunsTimeline";
import { ConversationSummary } from "@/pages/admin/traces/components/ConversationSummary";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getRagTraceConversationDetail,
  type RagTraceConversationDetail,
  type RagTraceConversationRun
} from "@/services/ragTraceService";
import { getErrorMessage } from "@/utils/error";
import { formatDateTime, formatDuration, statusBadgeVariant } from "@/pages/admin/traces/traceUtils";

const decodeParam = (value?: string): string => {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

const copy = async (value: string, label: string) => {
  try {
    await navigator.clipboard.writeText(value);
    toast.success(`${label} 已复制`);
  } catch {
    toast.error("复制失败");
  }
};

function SelectedRunCard({
  run,
  onOpenRun
}: {
  run: RagTraceConversationRun | null;
  onOpenRun: (traceId: string) => void;
}) {
  if (!run) {
    return (
      <Card className="border-[var(--neutral-200)] shadow-sm">
        <CardContent className="flex min-h-[220px] items-center justify-center text-sm text-[var(--neutral-600)]">
          请选择一个轮次查看概要
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-[var(--neutral-200)] shadow-sm">
      <CardHeader className="border-b border-[var(--neutral-100)] px-5 py-4">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">第 {run.turnNo} 轮概要</CardTitle>
          <Badge variant={statusBadgeVariant(run.status)}>{run.status || "unknown"}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 p-5">
        <div>
          <p className="mb-1 text-xs text-[var(--neutral-600)]">Trace Id</p>
          <button
            type="button"
            className="flex max-w-full items-center gap-2 rounded border border-[var(--neutral-200)] bg-[var(--neutral-050)] px-2 py-1 font-mono text-xs text-[var(--neutral-600)] hover:bg-[var(--brand-green-050)]"
            onClick={() => copy(run.traceId, "Trace Id")}
          >
            <span className="truncate">{run.traceId}</span>
            <Copy className="h-3.5 w-3.5 shrink-0" />
          </button>
        </div>
        <div>
          <p className="mb-1 text-xs text-[var(--neutral-600)]">用户问题</p>
          <p className="max-h-32 overflow-auto whitespace-pre-wrap rounded-md border border-[var(--neutral-200)] bg-[var(--neutral-050)] p-3 text-sm leading-6 text-[var(--brand-ink-800)]">
            {run.question || "-"}
          </p>
        </div>
        {run.finalAnswerSummary ? (
          <div>
            <p className="mb-1 text-xs text-[var(--neutral-600)]">最终回答摘要</p>
            <p className="max-h-40 overflow-auto whitespace-pre-wrap rounded-md border border-[var(--brand-green-100)] bg-[var(--brand-green-050)] p-3 text-sm leading-6 text-[var(--brand-ink-700)]">
              {run.finalAnswerSummary}
            </p>
          </div>
        ) : null}
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-md border border-[var(--neutral-200)] bg-[var(--neutral-050)] p-3">
            <p className="text-xs text-[var(--neutral-600)]">意图</p>
            <p className="mt-1 truncate text-[var(--brand-ink-800)]">{run.intentName || run.intentCode || "-"}</p>
          </div>
          <div className="rounded-md border border-[var(--neutral-200)] bg-[var(--neutral-050)] p-3">
            <p className="text-xs text-[var(--neutral-600)]">开始时间</p>
            <p className="mt-1 text-[var(--brand-ink-800)]">{formatDateTime(run.startTime ?? undefined)}</p>
          </div>
          <div className="rounded-md border border-[var(--neutral-200)] bg-[var(--neutral-050)] p-3">
            <p className="text-xs text-[var(--neutral-600)]">总耗时</p>
            <p className="mt-1 text-[var(--brand-ink-800)]">{formatDuration(run.durationMs ?? undefined)}</p>
          </div>
          <div className="rounded-md border border-[var(--neutral-200)] bg-[var(--neutral-050)] p-3">
            <p className="text-xs text-[var(--neutral-600)]">首字耗时</p>
            <p className="mt-1 text-[var(--brand-ink-800)]">{formatDuration(run.ttftMs ?? undefined)}</p>
          </div>
          <div className="rounded-md border border-[var(--neutral-200)] bg-[var(--neutral-050)] p-3">
            <p className="text-xs text-[var(--neutral-600)]">节点</p>
            <p className="mt-1 text-[var(--brand-ink-800)]">{run.nodeCount ?? 0}</p>
          </div>
          <div className="rounded-md border border-[var(--neutral-200)] bg-[var(--neutral-050)] p-3">
            <p className="text-xs text-[var(--neutral-600)]">失败节点</p>
            <p className="mt-1 text-[var(--brand-ink-800)]">{run.failedNodeCount ?? 0}</p>
          </div>
        </div>
        <Button className="w-full" onClick={() => onOpenRun(run.traceId)}>
          查看单轮端到端链路
        </Button>
      </CardContent>
    </Card>
  );
}

export function RagTraceConversationPage() {
  const { sessionId: rawSessionId } = useParams();
  const navigate = useNavigate();
  const requestRef = useRef(0);
  const sessionId = decodeParam(rawSessionId);
  const [detail, setDetail] = useState<RagTraceConversationDetail | null>(null);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadDetail = async () => {
    if (!sessionId) return;
    const requestId = ++requestRef.current;
    setLoading(true);
    try {
      const result = await getRagTraceConversationDetail(sessionId);
      if (requestRef.current !== requestId) return;
      setDetail(result);
      setSelectedTraceId((prev) => prev || result.runs[0]?.traceId || null);
    } catch (error) {
      if (requestRef.current !== requestId) return;
      toast.error(getErrorMessage(error, "加载会话链路详情失败"));
      setDetail(null);
    } finally {
      if (requestRef.current !== requestId) return;
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
  }, [sessionId]);

  const selectedRun = useMemo(() => {
    if (!detail?.runs.length) return null;
    return detail.runs.find((run) => run.traceId === selectedTraceId) || detail.runs[0];
  }, [detail?.runs, selectedTraceId]);

  const openRun = (traceId: string) => {
    navigate(`/admin/traces/runs/${encodeURIComponent(traceId)}`);
  };

  if (loading && !detail) {
    return (
      <div className="flex min-h-[420px] items-center justify-center text-slate-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        加载会话链路详情...
      </div>
    );
  }

  if (!sessionId || !detail) {
    return (
      <div className="space-y-5">
        <Button asChild variant="outline" size="sm">
          <Link to="/admin/traces">
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            返回会话列表
          </Link>
        </Button>
        <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 rounded-lg border border-slate-200 bg-white text-slate-500">
          <AlertTriangle className="h-10 w-10 text-slate-300" />
          <p>{sessionId ? "暂无会话链路数据" : "缺少 Session Id"}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 pb-8">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-1.5 text-sm">
          <Link to="/admin/traces" className="text-slate-500 hover:text-slate-700">
            链路追踪
          </Link>
          <span className="text-slate-300">/</span>
          <span className="text-slate-700">会话详情</span>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm">
            <Link to="/admin/traces">
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              返回会话列表
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={loadDetail} disabled={loading}>
            <RefreshCw className={`mr-1.5 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            刷新
          </Button>
        </div>
      </div>

      <ConversationSummary conversation={detail.conversation} />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <ConversationRunsTimeline
          runs={detail.runs}
          selectedTraceId={selectedRun?.traceId || null}
          onSelectRun={setSelectedTraceId}
          onOpenRun={openRun}
        />
        <SelectedRunCard run={selectedRun} onOpenRun={openRun} />
      </div>
    </div>
  );
}
