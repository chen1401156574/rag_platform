import { CheckCircle2, Clock3, Copy, Hash, MessageSquare, Route, UserRound, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { RagTraceConversation } from "@/services/ragTraceService";
import { formatDateTime, formatDuration, normalizeStatus, statusBadgeVariant } from "@/pages/admin/traces/traceUtils";

interface ConversationSummaryProps {
  conversation: RagTraceConversation;
}

const statusText = (status?: string | null) => {
  const normalized = normalizeStatus(status);
  if (normalized === "success") return "成功";
  if (normalized === "failed" || normalized === "timeout") return "失败";
  if (normalized === "running") return "运行中";
  if (normalized === "clarify_needed") return "等待补充";
  return status || "未知";
};

const copy = async (value: string, label: string) => {
  try {
    await navigator.clipboard.writeText(value);
    toast.success(`${label} 已复制`);
  } catch {
    toast.error("复制失败");
  }
};

export function ConversationSummary({ conversation }: ConversationSummaryProps) {
  const normalized = normalizeStatus(conversation.status);
  const StatusIcon = normalized === "failed" || normalized === "timeout" ? XCircle : CheckCircle2;

  return (
    <Card className="border-[var(--neutral-200)] shadow-sm">
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge variant={statusBadgeVariant(conversation.status)} className="gap-1">
                <StatusIcon className="h-3 w-3" />
                {statusText(conversation.status)}
              </Badge>
              {conversation.hasFailedNode ? (
                <Badge variant="destructive">存在失败节点</Badge>
              ) : null}
              {conversation.hasClarify ? (
                <Badge variant="secondary">包含追问</Badge>
              ) : null}
            </div>
            <h2 className="truncate text-xl font-semibold text-[var(--brand-ink-900)]">
              {conversation.sessionName || "未命名会话"}
            </h2>
            <p className="mt-1 line-clamp-2 text-sm text-[var(--neutral-600)]">
              {conversation.lastQuestion || "暂无最近问题"}
            </p>
          </div>
          <button
            type="button"
            className="inline-flex max-w-full items-center gap-2 rounded-md border border-[var(--neutral-200)] bg-[var(--neutral-050)] px-3 py-2 font-mono text-xs text-[var(--neutral-600)] hover:bg-[var(--brand-green-050)]"
            onClick={() => copy(conversation.sessionId, "Session Id")}
          >
            <Hash className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{conversation.sessionId}</span>
            <Copy className="h-3.5 w-3.5 shrink-0" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <div className="rounded-lg border border-[var(--neutral-200)] bg-[var(--neutral-050)] px-3 py-2">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-[var(--neutral-600)]">
              <UserRound className="h-3.5 w-3.5" />
              用户
            </div>
            <p className="truncate text-sm font-medium text-[var(--brand-ink-800)]">
              {conversation.userName || conversation.userId || "-"}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--neutral-200)] bg-[var(--neutral-050)] px-3 py-2">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-[var(--neutral-600)]">
              <Route className="h-3.5 w-3.5" />
              轮次
            </div>
            <p className="text-sm font-medium text-[var(--brand-ink-800)]">{conversation.turnCount}</p>
          </div>
          <div className="rounded-lg border border-[var(--neutral-200)] bg-[var(--neutral-050)] px-3 py-2">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-[var(--neutral-600)]">
              <MessageSquare className="h-3.5 w-3.5" />
              成功/失败/追问
            </div>
            <p className="text-sm font-medium text-[var(--brand-ink-800)]">
              {conversation.successCount} / {conversation.failedCount} / {conversation.clarifyCount}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--neutral-200)] bg-[var(--neutral-050)] px-3 py-2">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-[var(--neutral-600)]">
              <Clock3 className="h-3.5 w-3.5" />
              平均耗时
            </div>
            <p className="text-sm font-medium text-[var(--brand-ink-800)]">
              {formatDuration(conversation.avgDurationMs ?? undefined)}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--neutral-200)] bg-[var(--neutral-050)] px-3 py-2">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-[var(--neutral-600)]">
              <Clock3 className="h-3.5 w-3.5" />
              平均 TTFT
            </div>
            <p className="text-sm font-medium text-[var(--brand-ink-800)]">
              {formatDuration(conversation.avgTtftMs ?? undefined)}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--neutral-200)] bg-[var(--neutral-050)] px-3 py-2">
            <div className="mb-1 text-xs text-[var(--neutral-600)]">最近执行</div>
            <p className="truncate text-sm font-medium text-[var(--brand-ink-800)]">
              {formatDateTime(conversation.lastStartTime ?? conversation.lastEndTime ?? undefined)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
