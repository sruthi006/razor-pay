import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  ComposedChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BreakdownRow, RetryDistributionBucket } from "@/lib/api/types";
import { formatInr, formatNumber, formatPct } from "@/lib/format";

const axis = {
  stroke: "var(--muted-foreground)",
  fontSize: 11,
  tickLine: false,
  axisLine: false,
};

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid var(--border)",
  background: "var(--card)",
  boxShadow: "var(--shadow-soft)",
  fontSize: 12,
  color: "var(--foreground)",
};

export function ComparisonBarChart({
  data,
}: {
  data: Array<{ label: string; fixed: number; smart: number }>;
}) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }} barGap={8}>
        <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 6" />
        <XAxis dataKey="label" {...axis} />
        <YAxis {...axis} tickFormatter={(v: number) => formatInr(v)} width={62} />
        <Tooltip
          cursor={{ fill: "var(--muted)" }}
          contentStyle={tooltipStyle}
          formatter={(v: number) => formatInr(v)}
        />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
        <Bar dataKey="fixed" name="Fixed Schedule" fill="var(--sky)" radius={[8, 8, 0, 0]} />
        <Bar dataKey="smart" name="Smart Retry" fill="var(--periwinkle)" radius={[8, 8, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function BreakdownChart({ rows, height = 320 }: { rows: BreakdownRow[]; height?: number }) {
  const data = rows.map((r) => ({
    label: r.label,
    fixed: r.fixed_schedule_inr,
    smart: r.smart_retry_inr,
  }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid horizontal={false} stroke="var(--border)" strokeDasharray="3 6" />
        <XAxis type="number" {...axis} tickFormatter={(v: number) => formatInr(v)} />
        <YAxis type="category" dataKey="label" {...axis} width={132} />
        <Tooltip
          cursor={{ fill: "var(--muted)" }}
          contentStyle={tooltipStyle}
          formatter={(v: number) => formatInr(v)}
        />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
        <Bar dataKey="fixed" name="Fixed Schedule" fill="var(--sky)" radius={[0, 6, 6, 0]} barSize={10} />
        <Bar dataKey="smart" name="Smart Retry" fill="var(--periwinkle)" radius={[0, 6, 6, 0]} barSize={10} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function RecoveryRateChart({
  data,
}: {
  data: Array<{ label: string; fixed: number; smart: number }>;
}) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 6" />
        <XAxis dataKey="label" {...axis} />
        <YAxis {...axis} tickFormatter={(v: number) => `${v}%`} width={44} />
        <Tooltip
          cursor={{ fill: "var(--muted)" }}
          contentStyle={tooltipStyle}
          formatter={(v: number) => formatPct(Number(v), 1)}
        />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
        <Bar dataKey="fixed" name="Fixed Schedule rate" fill="var(--peach)" radius={[8, 8, 0, 0]} />
        <Bar dataKey="smart" name="Smart Retry rate" fill="var(--mint)" radius={[8, 8, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function RetryDistributionChart({ buckets }: { buckets: RetryDistributionBucket[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={buckets} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 6" />
        <XAxis dataKey="offset_label" {...axis} />
        <YAxis
          yAxisId="left"
          {...axis}
          width={52}
          tickFormatter={(v: number) => formatNumber(v)}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          {...axis}
          width={44}
          tickFormatter={(v: number) => `${v}%`}
        />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--muted)" }} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
        <Bar
          yAxisId="left"
          dataKey="selected_count"
          name="Times selected"
          radius={[8, 8, 0, 0]}
          fill="var(--lavender)"
        >
          {buckets.map((b) => (
            <Cell
              key={b.offset_label}
              fill={b.selected_count >= Math.max(...buckets.map((x) => x.selected_count)) ? "var(--periwinkle)" : "var(--lavender)"}
            />
          ))}
        </Bar>
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="recovery_rate_pct"
          name="Recovery rate"
          stroke="var(--mint)"
          strokeWidth={2.5}
          dot={{ r: 3, fill: "var(--mint)", strokeWidth: 0 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
