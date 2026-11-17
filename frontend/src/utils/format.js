/** Display helpers. Missing values are shown honestly ("Not found", "Unknown"), never invented. */

export function formatScore(value, digits = 2) {
  return value === null || value === undefined ? '—' : Number(value).toFixed(digits)
}

export function formatYears(value, { unknown = 'Unknown' } = {}) {
  if (value === null || value === undefined) return unknown
  const rounded = Math.round(Number(value) * 10) / 10
  return `${rounded} ${rounded === 1 ? 'yr' : 'yrs'}`
}

export function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatDateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString(undefined, {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function orNotFound(value) {
  return value ? value : 'Not found'
}

export function pluralize(count, word, plural = `${word}s`) {
  return `${count} ${count === 1 ? word : plural}`
}
