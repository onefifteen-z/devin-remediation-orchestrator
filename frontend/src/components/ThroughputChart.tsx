import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  formatTriggerSource,
  getActiveTriggerSources,
  getTriggerSourceChartColor,
} from "@/lib/devin"
import type { ThroughputPoint } from "@/types/metrics"

interface ThroughputChartProps {
  data: ThroughputPoint[]
}

type ChartRow = {
  date: string
  count: number
} & Record<string, number | string>

function toChartRows(data: ThroughputPoint[]): ChartRow[] {
  return data.map((point) => ({
    date: point.date,
    count: point.count,
    ...(point.by_source ?? {}),
  }))
}

function ThroughputTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ dataKey?: string; value?: number; color?: string }>
  label?: string
}) {
  if (!active || !payload?.length) return null

  const entries = payload
    .filter((entry) => entry.dataKey !== "count" && (entry.value ?? 0) > 0)
    .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))

  const total = entries.reduce((sum, entry) => sum + (entry.value ?? 0), 0)

  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-sm">
      <div className="mb-2 text-muted-foreground">{label}</div>
      <div className="space-y-1">
        {entries.map((entry) => (
          <div key={entry.dataKey} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-2">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              {formatTriggerSource(entry.dataKey)}
            </span>
            <span className="font-medium text-foreground">{entry.value}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 border-t border-border pt-2 font-medium text-foreground">
        Total: {total}
      </div>
    </div>
  )
}

export function ThroughputChart({ data }: ThroughputChartProps) {
  const hasData = data.some((point) => point.count > 0)
  const activeSources = getActiveTriggerSources(data)
  const chartData = toChartRows(data)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Remediation Throughput</CardTitle>
      </CardHeader>
      <CardContent>
        {!hasData ? (
          <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
            No throughput data yet
          </div>
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  tickFormatter={(value) => String(value).slice(5)}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={30}
                />
                <Tooltip content={<ThroughputTooltip />} />
                <Legend
                  verticalAlign="bottom"
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ fontSize: "11px", paddingTop: "12px" }}
                  formatter={(value) => formatTriggerSource(String(value))}
                />
                {activeSources.map((source, index) => (
                  <Bar
                    key={source}
                    dataKey={source}
                    name={source}
                    stackId="throughput"
                    fill={getTriggerSourceChartColor(source)}
                    radius={
                      index === activeSources.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]
                    }
                    maxBarSize={40}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
