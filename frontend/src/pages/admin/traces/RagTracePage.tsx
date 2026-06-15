import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Activity, Clock3, MessageSquare, RefreshCw, Route } from "lucide-react";
import { toast } from "sonner";

import { ConversationFilterBar } from "@/pages/admin/traces/components/ConversationFilterBar";
import { ConversationTable } from "@/pages/admin/traces/components/ConversationTable";
import { StatCard, type StatCardTone } from "@/pages/admin/traces/components/StatCard";
import {
  buildConversationQuery,
  CONVERSATION_PAGE_SIZE,
  conversationFiltersToSearch,
  createDefaultConversationFilters,
  loadStoredConversationFilters,
  parseConversationFiltersFromSearch,
  saveConversationFilters,
  type TraceConversationFilters
} from "@/pages/admin/traces/traceConversationFilterUtils";
import { formatDuration, normalizeStatus } from "@/pages/admin/traces/traceUtils";
import {
  getRagTraceConversations,
  type PageResult,
  type RagTraceConversation
} from "@/services/ragTraceService";
import { getErrorMessage } from "@/utils/error";

type DurationMetric = {
  value: string;
  unit: string;
};

const formatDurationMetric = (durationMs: number): DurationMetric => {
  const duration = Number.isFinite(durationMs) && durationMs > 0 ? durationMs : 0;
  if (duration < 1000) return { value: `${Math.round(duration)}`, unit: "ms" };
  if (duration < 60_000) return { value: (duration / 1000).toFixed(2), unit: "s" };
  return { value: (duration / 1000).toFixed(1), unit: "s" };
};

const resolveInitialState = (search: string) => {
  if (search && search !== "?") return parseConversationFiltersFromSearch(search);
  const stored = loadStoredConversationFilters();
  return {
    filters: stored || createDefaultConversationFilters(),
    page: 1
  };
};

export function RagTracePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const requestRef = useRef(0);
  const initialState = useMemo(() => resolveInitialState(location.search), []);

  const [draftFilters, setDraftFilters] = useState<TraceConversationFilters>(initialState.filters);
  const [appliedFilters, setAppliedFilters] = useState<TraceConversationFilters>(initialState.filters);
  const [pageNo, setPageNo] = useState(initialState.page);
  const [pageData, setPageData] = useState<PageResult<RagTraceConversation> | null>(null);
  const [loading, setLoading] = useState(false);

  const conversations = pageData?.records || [];

  const syncUrl = (filters: TraceConversationFilters, current: number) => {
    const query = conversationFiltersToSearch(filters, current);
    navigate(`/admin/traces?${query}`, { replace: true });
  };

  const loadConversations = async (
    current = pageNo,
    filters = appliedFilters,
    sync = false
  ) => {
    const requestId = ++requestRef.current;
    setLoading(true);
    try {
      const result = await getRagTraceConversations(
        buildConversationQuery(filters, current, CONVERSATION_PAGE_SIZE)
      );
      if (requestRef.current !== requestId) return;
      if (result.pages > 0 && current > result.pages) {
        setPageNo(result.pages);
        syncUrl(filters, result.pages);
        return;
      }
      setPageData(result);
      if (sync) syncUrl(filters, current);
    } catch (error) {
      if (requestRef.current !== requestId) return;
      toast.error(getErrorMessage(error, "加载会话链路列表失败"));
      console.error(error);
    } finally {
      if (requestRef.current !== requestId) return;
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConversations(pageNo, appliedFilters);
  }, [pageNo, appliedFilters]);

  const handleSearch = () => {
    setPageNo(1);
    setAppliedFilters(draftFilters);
    saveConversationFilters(draftFilters);
    syncUrl(draftFilters, 1);
  };

  const handleRefresh = () => {
    loadConversations(pageNo, appliedFilters, true);
  };

  const handleReset = () => {
    const defaults = createDefaultConversationFilters();
    setDraftFilters(defaults);
    setAppliedFilters(defaults);
    setPageNo(1);
    saveConversationFilters(defaults);
    syncUrl(defaults, 1);
  };

  const handlePageChange = (nextPage: number) => {
    const current = Math.max(1, nextPage);
    setPageNo(current);
    syncUrl(appliedFilters, current);
  };

  const stats = useMemo(() => {
    const failedCount = conversations.filter((item) => normalizeStatus(item.status) === "failed").length;
    const turnCount = conversations.reduce((sum, item) => sum + Number(item.turnCount || 0), 0);
    const durations = conversations
      .map((item) => Number(item.avgDurationMs ?? 0))
      .filter((value) => Number.isFinite(value) && value > 0);
    const ttfts = conversations
      .map((item) => Number(item.avgTtftMs ?? 0))
      .filter((value) => Number.isFinite(value) && value > 0);
    const avgDuration = durations.length
      ? Math.round(durations.reduce((sum, value) => sum + value, 0) / durations.length)
      : 0;
    const avgTtft = ttfts.length
      ? Math.round(ttfts.reduce((sum, value) => sum + value, 0) / ttfts.length)
      : 0;
    return {
      conversationTotal: pageData?.total ?? 0,
      currentTurnCount: turnCount,
      failedCount,
      avgDuration,
      avgTtft
    };
  }, [conversations, pageData?.total]);

  const avgDurationMetric = formatDurationMetric(stats.avgDuration);
  const avgTtftMetric = formatDurationMetric(stats.avgTtft);
  const statCards: Array<{
    key: string;
    title: string;
    value: string;
    unit?: string;
    icon: ReactNode;
    tone: StatCardTone;
  }> = [
    {
      key: "conversations",
      title: "会话数",
      value: String(stats.conversationTotal),
      icon: <MessageSquare className="h-4 w-4" />,
      tone: "primary"
    },
    {
      key: "turns",
      title: "当前页轮次",
      value: String(stats.currentTurnCount),
      icon: <Route className="h-4 w-4" />,
      tone: "link"
    },
    {
      key: "failed",
      title: "当前页失败会话",
      value: String(stats.failedCount),
      icon: <Activity className="h-4 w-4" />,
      tone: "danger"
    },
    {
      key: "avg",
      title: `平均耗时 ${formatDuration(stats.avgDuration)}`,
      value: avgDurationMetric.value,
      unit: avgDurationMetric.unit,
      icon: <Clock3 className="h-4 w-4" />,
      tone: "success"
    },
    {
      key: "ttft",
      title: `平均首字 ${formatDuration(stats.avgTtft)}`,
      value: avgTtftMetric.value,
      unit: avgTtftMetric.unit,
      icon: <RefreshCw className="h-4 w-4" />,
      tone: "link"
    }
  ];

  return (
    <div className="admin-page trace-page trace-list-page">
      <div className="trace-list-shell">
        <div className="admin-page-header">
          <div>
            <h1 className="admin-page-title">链路追踪</h1>
            <p className="admin-page-subtitle">
              按会话聚合查看每个对话的多轮问答链路，再下钻到单轮 Trace 分析端到端时间线。
            </p>
          </div>
        </div>

        <ConversationFilterBar
          filters={draftFilters}
          loading={loading}
          onChange={setDraftFilters}
          onSearch={handleSearch}
          onReset={handleReset}
          onRefresh={handleRefresh}
        />

        <section className="trace-list-stat-section">
          <div className="trace-list-stat-caption">
            <span className="trace-list-stat-caption-label">会话聚合统计</span>
            <span className="trace-list-stat-caption-hint">
              当前筛选返回 {stats.conversationTotal.toLocaleString("zh-CN")} 个会话
            </span>
          </div>
          <div className="trace-list-stat-grid">
            {statCards.map((stat) => (
              <StatCard
                key={stat.key}
                title={stat.title}
                value={stat.value}
                unit={stat.unit}
                icon={stat.icon}
                tone={stat.tone}
              />
            ))}
          </div>
        </section>

        <ConversationTable
          conversations={conversations}
          loading={loading}
          current={pageData?.current || pageNo}
          pages={pageData?.pages || 1}
          total={pageData?.total || 0}
          onOpenConversation={(sessionId) =>
            navigate(`/admin/traces/conversations/${encodeURIComponent(sessionId)}`)
          }
          onOpenRun={(traceId) => navigate(`/admin/traces/runs/${encodeURIComponent(traceId)}`)}
          onPrevPage={() => handlePageChange(pageNo - 1)}
          onNextPage={() => handlePageChange(pageNo + 1)}
        />
      </div>
    </div>
  );
}
