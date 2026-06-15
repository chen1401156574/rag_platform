import { RefreshCw, RotateCcw, Search, SlidersHorizontal, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import {
  CONVERSATION_STATUS_OPTIONS,
  activeConversationFilterCount,
  clearConversationFilter,
  conversationFilterLabel,
  fromDateTimeLocalValue,
  toDateTimeLocalValue,
  type TraceConversationFilterKey,
  type TraceConversationFilters,
  type TraceConversationStatus
} from "@/pages/admin/traces/traceConversationFilterUtils";

interface ConversationFilterBarProps {
  filters: TraceConversationFilters;
  loading: boolean;
  onChange: (filters: TraceConversationFilters) => void;
  onSearch: () => void;
  onReset: () => void;
  onRefresh: () => void;
}

const CHIP_KEYS: TraceConversationFilterKey[] = [
  "timeRange",
  "sessionId",
  "traceId",
  "userKeyword",
  "status",
  "intentCode",
  "keyword",
  "duration",
  "ttft",
  "hasFailedNode",
  "hasClarify"
];

const ADVANCED_KEYS: TraceConversationFilterKey[] = [
  "intentCode",
  "duration",
  "ttft",
  "hasFailedNode",
  "hasClarify"
];

const parseOptionalNumber = (value: string): number | undefined => {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
};

function TriStateSelect({
  value,
  onChange,
  placeholder
}: {
  value?: boolean;
  onChange: (value?: boolean) => void;
  placeholder: string;
}) {
  const selectValue = value === undefined ? "all" : value ? "true" : "false";
  return (
    <Select
      value={selectValue}
      onValueChange={(next) => {
        if (next === "all") onChange(undefined);
        else onChange(next === "true");
      }}
    >
      <SelectTrigger>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">全部</SelectItem>
        <SelectItem value="true">有</SelectItem>
        <SelectItem value="false">无</SelectItem>
      </SelectContent>
    </Select>
  );
}

export function ConversationFilterBar({
  filters,
  loading,
  onChange,
  onSearch,
  onReset,
  onRefresh
}: ConversationFilterBarProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const advancedCount = useMemo(
    () => ADVANCED_KEYS.filter((key) => conversationFilterLabel(key, filters)).length,
    [filters]
  );
  const chips = useMemo(
    () =>
      CHIP_KEYS.map((key) => ({
        key,
        label: conversationFilterLabel(key, filters)
      })).filter((item): item is { key: TraceConversationFilterKey; label: string } => Boolean(item.label)),
    [filters]
  );

  const update = (patch: Partial<TraceConversationFilters>) => onChange({ ...filters, ...patch });

  const toggleStatus = (status: TraceConversationStatus, checked: boolean) => {
    const next = checked
      ? Array.from(new Set([...filters.status, status]))
      : filters.status.filter((item) => item !== status);
    update({ status: next });
  };

  const handleEnterSearch = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") onSearch();
  };

  const setTimeRangePart = (index: 0 | 1, value: string) => {
    const iso = fromDateTimeLocalValue(value);
    if (!iso) return;
    const current = filters.timeRange || ["", ""];
    const next: [string, string] = index === 0 ? [iso, current[1]] : [current[0], iso];
    update({ timeRange: next });
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1.15fr_1fr_1fr_1fr_1.2fr_auto]">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label className="mb-1.5 block text-xs text-slate-500">开始时间</Label>
            <Input
              type="datetime-local"
              value={toDateTimeLocalValue(filters.timeRange?.[0])}
              onChange={(event) => setTimeRangePart(0, event.target.value)}
            />
          </div>
          <div>
            <Label className="mb-1.5 block text-xs text-slate-500">结束时间</Label>
            <Input
              type="datetime-local"
              value={toDateTimeLocalValue(filters.timeRange?.[1])}
              onChange={(event) => setTimeRangePart(1, event.target.value)}
            />
          </div>
        </div>

        <div>
          <Label className="mb-1.5 block text-xs text-slate-500">会话 ID</Label>
          <Input
            value={filters.sessionId}
            onChange={(event) => update({ sessionId: event.target.value })}
            onKeyDown={handleEnterSearch}
            placeholder="Session Id"
          />
        </div>

        <div>
          <Label className="mb-1.5 block text-xs text-slate-500">Trace ID</Label>
          <Input
            value={filters.traceId}
            onChange={(event) => update({ traceId: event.target.value })}
            onKeyDown={handleEnterSearch}
            placeholder="任意轮次 Trace Id"
          />
        </div>

        <div>
          <Label className="mb-1.5 block text-xs text-slate-500">用户</Label>
          <Input
            value={filters.userKeyword}
            onChange={(event) => update({ userKeyword: event.target.value })}
            onKeyDown={handleEnterSearch}
            placeholder="用户名"
          />
        </div>

        <div>
          <Label className="mb-1.5 block text-xs text-slate-500">问题关键词</Label>
          <Input
            value={filters.keyword}
            onChange={(event) => update({ keyword: event.target.value })}
            onKeyDown={handleEnterSearch}
            placeholder="匹配用户问题"
          />
        </div>

        <div className="flex items-end gap-2">
          <Button className="admin-primary-gradient" disabled={loading} onClick={onSearch}>
            <Search className="mr-2 h-4 w-4" />
            查询
          </Button>
          <Button variant="outline" disabled={loading} onClick={onRefresh}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            刷新
          </Button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-3 rounded-md border border-[var(--neutral-200)] bg-[var(--neutral-050)] px-3 py-2">
          <span className="text-xs font-medium text-[var(--neutral-600)]">状态</span>
          {CONVERSATION_STATUS_OPTIONS.map((item) => (
            <label key={item.value} className="flex cursor-pointer items-center gap-1.5 text-xs text-[var(--brand-ink-700)]">
              <Checkbox
                checked={filters.status.includes(item.value)}
                onCheckedChange={(checked) => toggleStatus(item.value, checked === true)}
              />
              {item.label}
            </label>
          ))}
        </div>
        <Button
          variant="outline"
          onClick={() => setAdvancedOpen((prev) => !prev)}
          className="gap-2"
        >
          <SlidersHorizontal className="h-4 w-4" />
          更多筛选{advancedCount > 0 ? ` ${advancedCount}` : ""}
        </Button>
        <Button variant="ghost" disabled={loading} onClick={onReset}>
          <RotateCcw className="mr-2 h-4 w-4" />
          重置
        </Button>
        <span className="text-xs text-[var(--neutral-500)]">
          已启用 {activeConversationFilterCount(filters)} 个非默认条件
        </span>
      </div>

      {advancedOpen && (
        <div className="mt-3 grid grid-cols-1 gap-3 border-t border-[var(--neutral-100)] pt-3 md:grid-cols-2 xl:grid-cols-5">
          <div>
            <Label className="mb-1.5 block text-xs text-slate-500">意图编码</Label>
            <Input
              value={filters.intentCode}
              onChange={(event) => update({ intentCode: event.target.value })}
              onKeyDown={handleEnterSearch}
              placeholder="intent_code"
            />
          </div>
          <div>
            <Label className="mb-1.5 block text-xs text-slate-500">耗时下限 ms</Label>
            <Input
              type="number"
              min={0}
              value={filters.minDurationMs ?? ""}
              onChange={(event) => update({ minDurationMs: parseOptionalNumber(event.target.value) })}
            />
          </div>
          <div>
            <Label className="mb-1.5 block text-xs text-slate-500">耗时上限 ms</Label>
            <Input
              type="number"
              min={0}
              value={filters.maxDurationMs ?? ""}
              onChange={(event) => update({ maxDurationMs: parseOptionalNumber(event.target.value) })}
            />
          </div>
          <div>
            <Label className="mb-1.5 block text-xs text-slate-500">首字下限 ms</Label>
            <Input
              type="number"
              min={0}
              value={filters.minTtftMs ?? ""}
              onChange={(event) => update({ minTtftMs: parseOptionalNumber(event.target.value) })}
            />
          </div>
          <div>
            <Label className="mb-1.5 block text-xs text-slate-500">首字上限 ms</Label>
            <Input
              type="number"
              min={0}
              value={filters.maxTtftMs ?? ""}
              onChange={(event) => update({ maxTtftMs: parseOptionalNumber(event.target.value) })}
            />
          </div>
          <div>
            <Label className="mb-1.5 block text-xs text-slate-500">失败节点</Label>
            <TriStateSelect
              value={filters.hasFailedNode}
              onChange={(value) => update({ hasFailedNode: value })}
              placeholder="失败节点"
            />
          </div>
          <div>
            <Label className="mb-1.5 block text-xs text-slate-500">触发追问</Label>
            <TriStateSelect
              value={filters.hasClarify}
              onChange={(value) => update({ hasClarify: value })}
              placeholder="触发追问"
            />
          </div>
        </div>
      )}

      {chips.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-[var(--neutral-100)] pt-3">
          {chips.map((chip) => (
            <Badge key={chip.key} variant="outline" className="gap-1 border-[var(--brand-green-100)] bg-[var(--brand-green-050)] text-[var(--brand-ink-700)]">
              <span className="max-w-[420px] truncate">{chip.label}</span>
              <button
                type="button"
                onClick={() => onChange(clearConversationFilter(filters, chip.key))}
                className="rounded-full p-0.5 text-[var(--neutral-500)] hover:bg-[var(--brand-green-100)] hover:text-[var(--brand-green-800)]"
                aria-label={`清除${chip.label}`}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
