/** Score visuals: band badge, horizontal bar, and the circular overall score. */
import { scoreBand } from '../utils/scoring'
import { formatScore } from '../utils/format'

export function ScoreBadge({ score }) {
  const band = scoreBand(score)
  if (!band) return <span className="text-xs text-slate-400">—</span>
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${band.badge}`}>
      {band.short}
    </span>
  )
}

/** Score number with a thin bar (0-100). Colour comes with the band label in tooltips/badges. */
export function ScoreBar({ score, showValue = true, className = '' }) {
  const band = scoreBand(score)
  const width = score === null || score === undefined ? 0 : Math.max(0, Math.min(100, score))
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div
        className="h-2 w-full min-w-16 overflow-hidden rounded-full bg-slate-100"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score ?? undefined}
        aria-label={score === null || score === undefined ? 'Not available' : `${formatScore(score)} out of 100, ${band.label}`}
      >
        <div className={`h-full rounded-full ${band ? band.bar : ''}`} style={{ width: `${width}%` }} />
      </div>
      {showValue && <span className="w-12 text-right text-sm font-semibold tabular-nums text-slate-900">{formatScore(score)}</span>}
    </div>
  )
}

/** Large circular score for the candidate header. */
export function ScoreRing({ score, size = 112 }) {
  const band = scoreBand(score)
  const stroke = 10
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const progress = score ? (Math.min(score, 100) / 100) * circumference : 0
  const colour = { strong: '#047857', good: '#2563eb', partial: '#d97706', limited: '#94a3b8' }[band?.key] || '#94a3b8'
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e2e8f0" strokeWidth={stroke} />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={colour} strokeWidth={stroke}
          strokeDasharray={`${progress} ${circumference}`} strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold tabular-nums text-navy-900">{formatScore(score)}</span>
        <span className="text-xs text-slate-500">of 100</span>
      </div>
      <span className="sr-only">{`Overall score ${formatScore(score)} out of 100, ${band?.label ?? 'not available'}`}</span>
    </div>
  )
}
