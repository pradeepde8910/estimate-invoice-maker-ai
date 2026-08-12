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
  layout = 'horizontal',
}: {
  data: DonutDatum[]
  valueFormatter?: (v: number) => string
  centerLabel?: { value: string; label: string }
  layout?: 'horizontal' | 'vertical'
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

  // Largest remainder method to ensure percentages sum exactly to 100%
  let exactPcts: number[] = []
  if (total > 0) {
    const rawPcts = chartData.map((d) => (d.value / total) * 100)
    const intPcts = rawPcts.map(Math.floor)
    const remainders = rawPcts.map((p, i) => ({ idx: i, rem: p - intPcts[i] }))
    let diff = 100 - intPcts.reduce((a, b) => a + b, 0)
    remainders.sort((a, b) => b.rem - a.rem)
    for (let i = 0; i < diff; i++) {
      intPcts[remainders[i].idx] += 1
    }
    exactPcts = intPcts
  }

  return (
    <div className={`flex ${layout === 'vertical' ? 'flex-col' : 'flex-row items-start'} gap-6`}>
      <div className="flex flex-col items-center mx-auto">
        <div className="relative w-40 h-40 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                innerRadius={0}
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
                formatter={(value: number, name: string) => {
                  const idx = chartData.findIndex((d) => d.name === name)
                  return [
                    `${fmt(value)} (${exactPcts[idx] || 0}%)`,
                    name,
                  ]
                }}
                contentStyle={{ borderRadius: 10, borderColor: '#e1e0d9', fontSize: 12 }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        {centerLabel && (
          <div className="flex flex-col items-center justify-center -mt-2 mb-2">
            <div className="text-base font-bold text-slate-800">{centerLabel.value}</div>
            <div className="text-[10px] text-slate-400">{centerLabel.label}</div>
          </div>
        )}
      </div>
      <div className="flex-1 overflow-hidden rounded-xl border border-slate-200 shadow-sm">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500 font-semibold">
            <tr>
              <th className="px-4 py-3">Label</th>
              <th className="px-4 py-3 text-right">Amount</th>
              <th className="px-4 py-3 text-right">%</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {chartData.map((d, i) => {
              const pct = exactPcts[i] || 0
              return (
                <tr key={d.name} className="hover:bg-slate-50/50 transition-colors">
                  <td className="px-4 py-2.5 flex items-center gap-3 w-full min-w-[150px]">
                    <span
                      className="w-2 h-2 rounded-full shrink-0 shadow-sm"
                      style={{ background: d.name === 'Other' ? OTHER_COLOR : SERIES_COLORS[i % SERIES_COLORS.length] }}
                    />
                    <span className="text-slate-700 font-medium truncate">{d.name}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-slate-700 whitespace-nowrap">
                    {fmt(d.value)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-slate-500 font-medium">
                    {pct}%
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
