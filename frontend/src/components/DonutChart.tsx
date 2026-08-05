import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

// Categorical palette (light mode) from the dataviz skill's validated default —
// fixed hue order, never cycled/re-derived per chart.
const SERIES_COLORS = [
  '#2a78d6', // blue
  '#eb6834', // orange
  '#1baf7a', // aqua
  '#eda100', // yellow
  '#e87ba4', // magenta
  '#008300', // green
  '#4a3aa7', // violet
  '#e34948', // red
]
const OTHER_COLOR = '#898781' // muted ink — used only for the folded "Other" slot

export interface DonutDatum {
  name: string
  value: number
}

export default function DonutChart({
  data,
  valueFormatter,
  centerLabel,
}: {
  data: DonutDatum[]
  valueFormatter?: (v: number) => string
  centerLabel?: { value: string; label: string }
}) {
  const sorted = [...data].filter((d) => d.value > 0).sort((a, b) => b.value - a.value)
  const MAX_SLOTS = 8
  let chartData = sorted
  if (sorted.length > MAX_SLOTS) {
    const head = sorted.slice(0, MAX_SLOTS - 1)
    const otherTotal = sorted.slice(MAX_SLOTS - 1).reduce((s, d) => s + d.value, 0)
    chartData = [...head, { name: 'Other', value: otherTotal }]
  }
  const total = chartData.reduce((s, d) => s + d.value, 0)
  const fmt = valueFormatter ?? ((v: number) => v.toLocaleString())

  return (
    <div className="flex items-center gap-6">
      <div className="relative w-40 h-40 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              innerRadius={48}
              outerRadius={72}
              paddingAngle={chartData.length > 1 ? 2 : 0}
              stroke="#fcfcfb"
              strokeWidth={2}
            >
              {chartData.map((d, i) => (
                <Cell
                  key={d.name}
                  fill={d.name === 'Other' ? OTHER_COLOR : SERIES_COLORS[i % SERIES_COLORS.length]}
                />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number, name: string) => [
                `${fmt(value)} (${total ? Math.round((value / total) * 100) : 0}%)`,
                name,
              ]}
              contentStyle={{ borderRadius: 10, borderColor: '#e1e0d9', fontSize: 12 }}
            />
          </PieChart>
        </ResponsiveContainer>
        {centerLabel && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <div className="text-base font-bold text-slate-800">{centerLabel.value}</div>
            <div className="text-[10px] text-slate-400">{centerLabel.label}</div>
          </div>
        )}
      </div>
      <ul className="space-y-1.5 text-sm min-w-0">
        {chartData.map((d, i) => (
          <li key={d.name} className="flex items-center gap-2 min-w-0">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ background: d.name === 'Other' ? OTHER_COLOR : SERIES_COLORS[i % SERIES_COLORS.length] }}
            />
            <span className="text-slate-600 truncate max-w-[9rem]">{d.name}</span>
            <span className="text-slate-400 ml-auto shrink-0 tabular-nums">
              {total ? Math.round((d.value / total) * 100) : 0}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
