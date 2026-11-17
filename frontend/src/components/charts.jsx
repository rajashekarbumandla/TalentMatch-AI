/**
 * Dashboard charts (Recharts).
 *
 * Data-visualisation rules followed here:
 * - one measure per chart, one hue (blue), so no legend is needed: the card title names it;
 * - thin bars with 4px rounded data ends, a quiet grid and muted axes;
 * - a hover tooltip on every bar, and a visually hidden table for screen readers;
 * - text uses text colours, never the series colour;
 * - no entry animation (bars appear immediately; avoids distracting motion).
 */
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatScore } from '../utils/format'

const SERIES = '#2a78d6'
const SERIES_HOVER = '#1c5cab'
const GRID = '#e2e8f0'
const AXIS_TEXT = { fill: '#64748b', fontSize: 12 }

function TooltipBox({ title, rows }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-slate-900">{title}</p>
      {rows.map(([label, value]) => (
        <p key={label} className="flex justify-between gap-4 text-slate-600">
          <span>{label}</span>
          <span className="font-medium tabular-nums text-slate-900">{value}</span>
        </p>
      ))}
    </div>
  )
}

function SrTable({ caption, headers, rows }) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <thead>
        <tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>
        ))}
      </tbody>
    </table>
  )
}

/** How many candidate results fall in each 20-point score band. */
export function ScoreDistributionChart({ buckets }) {
  return (
    <div>
      <div className="h-56" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={buckets} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barCategoryGap="28%">
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="range" tick={AXIS_TEXT} tickLine={false} axisLine={{ stroke: GRID }} />
            <YAxis allowDecimals={false} tick={AXIS_TEXT} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ fill: '#f1f5f9' }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TooltipBox title={`Score ${payload[0].payload.range}`} rows={[['Candidates', payload[0].value]]} />
                ) : null
              }
            />
            <Bar isAnimationActive={false} dataKey="count" fill={SERIES} radius={[4, 4, 0, 0]} activeBar={{ fill: SERIES_HOVER }} maxBarSize={56} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <SrTable caption="Score distribution" headers={['Score range', 'Candidates']} rows={buckets.map((b) => [b.range, b.count])} />
    </div>
  )
}

/** Top candidates of the latest analysis; clicking a bar opens that candidate. */
export function ShortlistChart({ candidates, onSelect }) {
  const data = candidates.map((c) => ({ ...c, label: `${c.rank}. ${c.name || 'Name not found'}` }))
  return (
    <div>
      <div style={{ height: Math.max(160, data.length * 32 + 32) }} aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }} barCategoryGap="30%">
            <CartesianGrid horizontal={false} stroke={GRID} />
            <XAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={AXIS_TEXT} tickLine={false} axisLine={false} />
            <YAxis
              type="category"
              dataKey="label"
              width={150}
              tick={{ ...AXIS_TEXT, fill: '#334155' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => (value.length > 22 ? `${value.slice(0, 21)}…` : value)}
            />
            <Tooltip
              cursor={{ fill: '#f1f5f9' }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TooltipBox
                    title={payload[0].payload.name || 'Name not found'}
                    rows={[['Rank', `#${payload[0].payload.rank}`], ['Final score', formatScore(payload[0].value)], ['', 'Click to view details']]}
                  />
                ) : null
              }
            />
            <Bar
              isAnimationActive={false}
              dataKey="final_score"
              fill={SERIES}
              radius={[0, 4, 4, 0]}
              activeBar={{ fill: SERIES_HOVER }}
              maxBarSize={18}
              cursor="pointer"
              onClick={(entry) => onSelect?.(entry.payload ?? entry)}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <SrTable
        caption="Top candidates of the latest analysis"
        headers={['Rank', 'Candidate', 'Final score']}
        rows={data.map((c) => [c.rank, c.name || 'Name not found', formatScore(c.final_score)])}
      />
    </div>
  )
}

/** Resumes analysed per day over the last 30 days. */
export function ActivityChart({ points }) {
  const data = points.map((p) => ({
    ...p,
    label: new Date(`${p.date}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }),
  }))
  return (
    <div>
      <div className="h-56" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barCategoryGap="20%">
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" tick={AXIS_TEXT} tickLine={false} axisLine={{ stroke: GRID }} interval={6} />
            <YAxis allowDecimals={false} tick={AXIS_TEXT} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ fill: '#f1f5f9' }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TooltipBox
                    title={payload[0].payload.label}
                    rows={[['Resumes analysed', payload[0].payload.resumes], ['Analyses run', payload[0].payload.analyses]]}
                  />
                ) : null
              }
            />
            <Bar isAnimationActive={false} dataKey="resumes" fill={SERIES} radius={[4, 4, 0, 0]} activeBar={{ fill: SERIES_HOVER }} maxBarSize={16} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <SrTable
        caption="Resumes analysed per day"
        headers={['Date', 'Resumes analysed', 'Analyses']}
        rows={points.filter((p) => p.analyses).map((p) => [p.date, p.resumes, p.analyses])}
      />
    </div>
  )
}
