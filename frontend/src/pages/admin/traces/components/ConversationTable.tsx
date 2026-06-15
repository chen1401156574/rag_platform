import { CheckCircle2, Copy, Eye, Loader2, MessageSquare, Route, XCircle } from "lucide-react";
import { toast } from "sonner";

import { RelativeTime } from "@/components/RelativeTime";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { RagTraceConversation } from "@/services/ragTraceService";
import { formatDateTime, formatDuration, normalizeStatus, statusBadgeVariant } from "@/pages/admin/traces/traceUtils";

interface ConversationTableProps {
  conversations: RagTraceConversation[];
  loading: boolean;
  current: number;
  pages: number;
  total: number;
  onOpenConversation: (sessionId: string) => void;
  onOpenRun: (traceId: string) => void;
  onPrevPage: () => void;
  onNextPage: () => void;
}

const statusText = (status?: string | null): string => {
  const normalized = normalizeStatus(status);
  if (normalized === "success") return "成功";
  if (normalized === "failed" || normalized === "timeout") return "失败";
  if (normalized === "running") return "运行中";
  if (normalized === "clarify_needed") return "等待补充";
  return status || "未知";
};

const StatusBadge = ({ status }: { status?: string | null }) => {
  const normalized = normalizeStatus(status);
  const Icon =
    normalized === "failed" || normalized === "timeout"
      ? XCircle
      : normalized === "running"
        ? Loader2
        : CheckCircle2;
  return (
    <Badge variant={statusBadgeVariant(status)} className="gap-1">
      <Icon className={`h-3 w-3 ${normalized === "running" ? "animate-spin" : ""}`} />
      {statusText(status)}
    </Badge>
  );
};

const empty = <span className="text-slate-400">-</span>;

const truncateMiddle = (value: string, head = 8, tail = 6) => {
  if (value.length <= head + tail + 3) return value;
  return `${value.slice(0, head)}...${value.slice(-tail)}`;
};

const copyText = async (value: string, label: string) => {
  try {
    await navigator.clipboard.writeText(value);
    toast.success(`${label} 已复制`);
  } catch {
    toast.error("复制失败");
  }
};

export function ConversationTable({
  conversations,
  loading,
  current,
  pages,
  total,
  onOpenConversation,
  onOpenRun,
  onPrevPage,
  onNextPage
}: ConversationTableProps) {
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardContent className="p-0">
        {loading ? (
          <div className="flex min-h-[280px] items-center justify-center text-sm text-slate-500">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            加载会话链路...
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex min-h-[280px] flex-col items-center justify-center gap-2 text-slate-500">
            <MessageSquare className="h-9 w-9 text-slate-300" />
            <p className="text-sm">暂无符合条件的会话链路</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[320px]">会话 / 最近问题</TableHead>
                  <TableHead className="min-w-[120px]">用户</TableHead>
                  <TableHead className="min-w-[100px]">轮次</TableHead>
                  <TableHead className="min-w-[160px]">最近意图</TableHead>
                  <TableHead className="min-w-[150px]">成功 / 失败 / 追问</TableHead>
                  <TableHead className="min-w-[140px]">平均耗时 / TTFT</TableHead>
                  <TableHead className="min-w-[120px]">状态</TableHead>
                  <TableHead className="min-w-[150px]">最近执行</TableHead>
                  <TableHead className="min-w-[170px] text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {conversations.map((item) => (
                  <TableRow key={item.sessionId} className="hover:bg-[var(--brand-green-050)]">
                    <TableCell>
                      <div className="min-w-0 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="max-w-[260px] truncate text-sm font-medium text-slate-900" title={item.sessionName || item.sessionId}>
                            {item.sessionName || "未命名会话"}
                          </span>
                          <button
                            type="button"
                            className="inline-flex items-center gap-1 rounded border border-[var(--neutral-200)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--neutral-600)] hover:bg-[var(--brand-green-050)]"
                            onClick={() => copyText(item.sessionId, "Session Id")}
                          >
                            {truncateMiddle(item.sessionId)}
                            <Copy className="h-3 w-3" />
                          </button>
                        </div>
                        <p className="line-clamp-2 text-xs text-slate-500" title={item.lastQuestion || undefined}>
                          {item.lastQuestion || "无最近问题"}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-slate-700">
                        {item.userName || item.userId || empty}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5 text-sm text-slate-700">
                        <Route className="h-4 w-4 text-slate-400" />
                        {item.turnCount}
                      </div>
                    </TableCell>
                    <TableCell>
                      {item.lastIntentName || item.lastIntentCode ? (
                        <div className="space-y-1">
                          <span className="block truncate text-sm text-slate-700" title={item.lastIntentName || item.lastIntentCode || undefined}>
                            {item.lastIntentName || item.lastIntentCode}
                          </span>
                          {item.lastIntentScore !== null && item.lastIntentScore !== undefined && (
                            <span className="text-xs text-slate-400">
                              置信度 {Math.round(item.lastIntentScore * 100)}%
                            </span>
                          )}
                        </div>
                      ) : (
                        empty
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="tabular-nums text-sm text-slate-700">
                        {item.successCount ?? 0} / {item.failedCount ?? 0} / {item.clarifyCount ?? 0}
                      </span>
                      {item.failedNodeCount ? (
                        <p className="mt-1 text-xs text-red-500">失败节点 {item.failedNodeCount}</p>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <div className="text-sm tabular-nums text-slate-700">
                        {formatDuration(item.avgDurationMs ?? undefined)}
                      </div>
                      <div className="text-xs tabular-nums text-slate-400">
                        TTFT {formatDuration(item.avgTtftMs ?? undefined)}
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={item.status || item.lastStatus} />
                    </TableCell>
                    <TableCell>
                      <div className="text-sm text-slate-700">
                        <RelativeTime value={item.lastStartTime ?? item.lastEndTime ?? undefined} />
                      </div>
                      <div className="text-xs text-slate-400">
                        {formatDateTime(item.lastStartTime ?? item.lastEndTime ?? undefined)}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        {item.lastTraceId ? (
                          <Button variant="ghost" size="sm" onClick={() => onOpenRun(item.lastTraceId!)}>
                            最近轮次
                          </Button>
                        ) : null}
                        <Button size="sm" onClick={() => onOpenConversation(item.sessionId)}>
                          <Eye className="mr-1.5 h-3.5 w-3.5" />
                          全链路
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
          <span className="text-xs text-slate-500">
            第 {current} / {Math.max(pages, 1)} 页，共 {total.toLocaleString("zh-CN")} 个会话
          </span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={current <= 1 || loading} onClick={onPrevPage}>
              上一页
            </Button>
            <Button variant="outline" size="sm" disabled={current >= pages || loading} onClick={onNextPage}>
              下一页
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
