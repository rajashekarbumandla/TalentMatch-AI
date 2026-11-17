/** Skill chips (read-only lists) and the editable skill input used in the requirements editor. */
import { Check, Minus, Plus, X } from 'lucide-react'
import { useState } from 'react'
import { inputClass } from './ui'

const CHIP_STYLES = {
  matched: { className: 'bg-emerald-50 text-emerald-800 ring-emerald-600/20', icon: Check, label: 'found' },
  missing: { className: 'bg-red-50 text-red-700 ring-red-600/20', icon: X, label: 'not found' },
  neutral: { className: 'bg-slate-100 text-slate-700 ring-slate-500/20', icon: null, label: '' },
  required: { className: 'bg-navy-900/5 text-navy-900 ring-navy-900/15', icon: null, label: '' },
  preferred: { className: 'bg-accent-50 text-accent-600 ring-accent-500/20', icon: null, label: '' },
}

export function SkillChips({ skills, tone = 'neutral', limit, empty = 'None' }) {
  if (!skills?.length) return <span className="text-sm text-slate-400">{empty}</span>
  const style = CHIP_STYLES[tone]
  const shown = limit ? skills.slice(0, limit) : skills
  const Icon = style.icon
  return (
    <ul className="flex flex-wrap gap-1.5">
      {shown.map((skill) => (
        <li key={skill} className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${style.className}`}>
          {Icon && <Icon className="size-3" aria-hidden="true" />}
          {skill}
          {style.label && <span className="sr-only"> ({style.label})</span>}
        </li>
      ))}
      {limit && skills.length > limit && (
        <li className="inline-flex items-center rounded-md px-2 py-0.5 text-xs text-slate-500" title={skills.slice(limit).join(', ')}>
          +{skills.length - limit} more
        </li>
      )}
    </ul>
  )
}

/**
 * Editable list of skills: type and press Enter (or comma) to add, click × to remove.
 * Writing "FastAPI or Django" creates one requirement satisfied by either skill.
 */
export function SkillInput({ id, value, onChange, placeholder = 'Type a skill and press Enter', tone = 'required' }) {
  const [draft, setDraft] = useState('')
  const style = CHIP_STYLES[tone]

  const add = (raw) => {
    const parts = raw.split(',').map((s) => s.trim()).filter(Boolean)
    const existing = new Set(value.map((s) => s.toLowerCase()))
    const additions = parts.filter((p) => !existing.has(p.toLowerCase()))
    if (additions.length) onChange([...value, ...additions])
    setDraft('')
  }

  return (
    <div className="rounded-lg bg-white p-2 ring-1 ring-inset ring-slate-300 focus-within:ring-2 focus-within:ring-brand-500">
      {value.length > 0 && (
        <ul className="mb-2 flex flex-wrap gap-1.5">
          {value.map((skill) => (
            <li key={skill} className={`inline-flex items-center gap-1 rounded-md py-0.5 pl-2 pr-1 text-xs font-medium ring-1 ring-inset ${style.className}`}>
              {skill}
              <button
                type="button"
                onClick={() => onChange(value.filter((s) => s !== skill))}
                className="rounded p-0.5 hover:bg-black/10"
                aria-label={`Remove ${skill}`}
              >
                <X className="size-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <input
          id={id}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if ((event.key === 'Enter' || event.key === ',') && draft.trim()) {
              event.preventDefault()
              add(draft)
            } else if (event.key === 'Backspace' && !draft && value.length) {
              onChange(value.slice(0, -1))
            }
          }}
          placeholder={placeholder}
          className={`${inputClass} ring-0 focus:ring-0`}
        />
        <button
          type="button"
          onClick={() => draft.trim() && add(draft)}
          disabled={!draft.trim()}
          className="inline-flex items-center gap-1 rounded-md px-2 text-xs font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-40"
        >
          <Plus className="size-3.5" aria-hidden="true" /> Add
        </button>
      </div>
    </div>
  )
}

/** Simple list editor for responsibilities (one item per line). */
export function LinesInput({ id, value, onChange, rows = 5, placeholder }) {
  return (
    <textarea
      id={id}
      rows={rows}
      value={value.join('\n')}
      onChange={(event) => onChange(event.target.value.split('\n'))}
      onBlur={() => onChange(value.map((line) => line.trim()).filter(Boolean))}
      placeholder={placeholder}
      className={inputClass}
    />
  )
}

export function SkillLegend() {
  return (
    <p className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
      <span className="inline-flex items-center gap-1"><Check className="size-3 text-emerald-700" /> found in resume</span>
      <span className="inline-flex items-center gap-1"><X className="size-3 text-red-600" /> not found</span>
      <span className="inline-flex items-center gap-1"><Minus className="size-3" /> extra skill, not requested</span>
    </p>
  )
}
