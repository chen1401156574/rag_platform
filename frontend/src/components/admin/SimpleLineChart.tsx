import { useMemo } from "react";

export type ChartXAxisMode = "hour" | "date";
export type ChartYAxisType = "number" | "duration" | "percent";
export type ChartTone = "primary" | "success" | "warning" | "critical" | "info" | "danger";

export type TrendPoint = {
  ts: number;
  value: number;
};

export type TrendSeries = {
  name: string;
  data: TrendPoint[];
  tone?: ChartTone;
};

export type ChartThreshold = {
  value: number;
  label?: string;
  tone?: ChartTone;
};

const TONE_COLORS: Record<ChartTone, string> = {
  primary: "#2563eb",
  success: "#059669",
  warning: "#d97706",
  critical: "#dc2626",
  info: "#0891b2",
  danger: "#dc2626"
};

function formatX(ts: number, mode: ChartXAxisMode) {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "";
  return mode === "hour"
    ? `${String(date.getHours()).padStart(2, "0")}:00`
    : `${date.getMonth() + 1}/${date.getDate()}`;
}

function formatY(value: number, type: ChartYAxisType) {
  if (type === "percent") return `${Math.round(value)}%`;
  if (type === "duration") {
    return value >= 1000 ? `${Math.round(value / 1000)}s` : `${Math.round(value)}ms`;
  }
  return String(Math.round(value));
}

export function SimpleLineChart({
  series,
  thresholds = [],
  xAxisMode,
  yAxisType = "number",
  height = 220,
  yAxisTickCount = 4
}: {
  series: TrendSeries[];
  thresholds?: ChartThreshold[];
  xAxisMode: ChartXAxisMode;
  yAxisType?: ChartYAxisType;
  height?: number;
  theme?: "light" | "dark";
  yAxisTickCount?: number;
}) {
  const chart = useMemo(() => {
    const points = series.flatMap((item) => item.data || []);
    const xValues = points.map((point) => point.ts);
    const yValues = points.map((point) => point.value).concat(thresholds.map((item) => item.value));
    const xMin = Math.min(...xValues);
    const xMax = Math.max(...xValues);
    const yMinRaw = Math.min(0, ...yValues);
    const yMaxRaw = Math.max(1, ...yValues);
    const yPadding = Math.max(1, (yMaxRaw - yMinRaw) * 0.12);

    return {
      empty: points.length === 0,
      xMin,
      xMax,
      yMin: yMinRaw,
      yMax: yMaxRaw + yPadding
    };
  }, [series, thresholds]);

  const width = 640;
  const padding = { top: 18, right: 20, bottom: 32, left: 48 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  const xScale = (value: number) => {
    if (chart.xMax === chart.xMin) return padding.left + innerWidth / 2;
    return padding.left + ((value - chart.xMin) / (chart.xMax - chart.xMin)) * innerWidth;
  };

  const yScale = (value: number) => {
    if (chart.yMax === chart.yMin) return padding.top + innerHeight / 2;
    return padding.top + innerHeight - ((value - chart.yMin) / (chart.yMax - chart.yMin)) * innerHeight;
  };

  const yTicks = Array.from({ length: Math.max(2, yAxisTickCount) }, (_, index) => {
    const maxIndex = Math.max(1, yAxisTickCount - 1);
    return chart.yMin + ((chart.yMax - chart.yMin) * index) / maxIndex;
  });

  const xTicks = useMemo(() => {
    const all = series.flatMap((item) => item.data || []).sort((a, b) => a.ts - b.ts);
    if (all.length <= 1) return all;
    return [all[0], all[Math.floor(all.length / 2)], all[all.length - 1]].filter(Boolean);
  }, [series]);

  if (chart.empty) {
    return (
      <div className="flex h-full min-h-32 items-center justify-center rounded-lg border border-dashed border-slate-200 text-sm text-slate-400">
        No trend data
      </div>
    );
  }

  return (
    <div className="h-full w-full overflow-hidden">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" className="h-full w-full">
        <rect x="0" y="0" width={width} height={height} fill="transparent" />
        {yTicks.map((tick) => {
          const y = yScale(tick);
          return (
            <g key={tick}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="#e2e8f0" strokeWidth="1" />
              <text x={padding.left - 8} y={y + 4} textAnchor="end" fontSize="11" fill="#94a3b8">
                {formatY(tick, yAxisType)}
              </text>
            </g>
          );
        })}
        {thresholds.map((threshold) => {
          const y = yScale(threshold.value);
          const color = TONE_COLORS[threshold.tone || "info"];
          return (
            <g key={`${threshold.value}-${threshold.label || ""}`}>
              <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke={color}
                strokeDasharray="4 4"
                strokeOpacity="0.65"
              />
              {threshold.label ? (
                <text x={width - padding.right} y={y - 4} textAnchor="end" fontSize="11" fill={color}>
                  {threshold.label}
                </text>
              ) : null}
            </g>
          );
        })}
        {series.map((item) => {
          const color = TONE_COLORS[item.tone || "primary"];
          const path = (item.data || [])
            .map((point, index) => `${index === 0 ? "M" : "L"} ${xScale(point.ts)} ${yScale(point.value)}`)
            .join(" ");
          return <path key={item.name} d={path} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" />;
        })}
        {series.flatMap((item) =>
          (item.data || []).map((point) => (
            <circle
              key={`${item.name}-${point.ts}`}
              cx={xScale(point.ts)}
              cy={yScale(point.value)}
              r="3"
              fill={TONE_COLORS[item.tone || "primary"]}
            />
          ))
        )}
        {xTicks.map((point) => (
          <text key={point.ts} x={xScale(point.ts)} y={height - 10} textAnchor="middle" fontSize="11" fill="#94a3b8">
            {formatX(point.ts, xAxisMode)}
          </text>
        ))}
      </svg>
    </div>
  );
}
