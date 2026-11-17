/**
 * Score bands used across the UI. The colour always comes with a text label
 * (never colour alone), so the meaning is clear for colour-blind users and in print.
 * Thresholds match the backend's explanation wording (strong >= 80, good >= 60, partial >= 40).
 */
export const SCORE_BANDS = [
  { key: 'strong', label: 'Strong match', short: 'Strong', min: 80, bar: 'bg-emerald-600', badge: 'bg-emerald-50 text-emerald-800 ring-emerald-600/20' },
  { key: 'good', label: 'Good match', short: 'Good', min: 60, bar: 'bg-brand-600', badge: 'bg-brand-50 text-brand-700 ring-brand-600/20' },
  { key: 'partial', label: 'Partial match', short: 'Partial', min: 40, bar: 'bg-amber-500', badge: 'bg-amber-50 text-amber-800 ring-amber-600/20' },
  { key: 'limited', label: 'Limited match', short: 'Limited', min: 0, bar: 'bg-slate-400', badge: 'bg-slate-100 text-slate-700 ring-slate-500/20' },
]

export function scoreBand(score) {
  if (score === null || score === undefined) return null
  return SCORE_BANDS.find((band) => score >= band.min) || SCORE_BANDS[SCORE_BANDS.length - 1]
}

/** Quick filters on the ranking page: [min, max] score ranges sent to the API. */
export const BAND_FILTERS = {
  strong: { min_score: 80 },
  good: { min_score: 60, max_score: 79.99 },
  partial: { min_score: 40, max_score: 59.99 },
  limited: { max_score: 39.99 },
}

export const COMPONENT_INFO = {
  semantic: {
    label: 'Semantic similarity',
    help: 'How closely the overall content of the resume matches the job description, measured with an AI language model (all-MiniLM-L6-v2). It compares meaning, not just keywords.',
  },
  skills: {
    label: 'Skills match',
    help: 'Share of the job’s skills found in the resume. Required skills count twice as much as preferred skills.',
  },
  experience: {
    label: 'Experience match',
    help: 'Relevant experience compared with the minimum the job asks for. Only past jobs related to this role count; internships are listed separately.',
  },
}

export const EXPERIENCE_STATUS = {
  met: { label: 'Requirement met', badge: 'bg-emerald-50 text-emerald-800 ring-emerald-600/20' },
  not_met: { label: 'Below requirement', badge: 'bg-amber-50 text-amber-800 ring-amber-600/20' },
  not_required: { label: 'No requirement', badge: 'bg-slate-100 text-slate-700 ring-slate-500/20' },
  unknown: { label: 'Could not be determined', badge: 'bg-slate-100 text-slate-700 ring-slate-500/20' },
}
