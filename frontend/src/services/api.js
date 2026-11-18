/**
 * Every call to the FastAPI backend goes through this file.
 * The base URL comes from VITE_API_BASE_URL, so the same build works locally and on Vercel.
 * No credentials live here: the browser only ever talks to our own API.
 */
import axios from 'axios'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  timeout: 30000,
})

// Uploading/parsing a batch and running an analysis can take a while on a slow connection.
const LONG_TIMEOUT = 180000

/* ---------- Login token -------------------------------------------------------------------------
 * The token returned by /auth/login is kept in localStorage (so a page refresh keeps you logged in)
 * and sent as "Authorization: Bearer <token>" on every request. It expires after a working day.
 * Trade-off: localStorage is readable by scripts on this site, so the app never renders untrusted
 * HTML (React escapes all text). An httpOnly cookie would need same-site hosting of API and frontend.
 */
const TOKEN_KEY = 'talentmatch:token'
let authToken = null
try {
  authToken = localStorage.getItem(TOKEN_KEY)
} catch {
  authToken = null
}

export function getToken() {
  return authToken
}

export function setToken(token) {
  authToken = token
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage unavailable: the session lasts until the tab is closed */
  }
}

let onUnauthorized = () => {}
/** The auth provider registers what to do when the server says the session is no longer valid. */
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

api.interceptors.request.use((config) => {
  if (authToken) config.headers.Authorization = `Bearer ${authToken}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || ''
    if (error.response?.status === 401 && authToken && !url.startsWith('/auth/login')) onUnauthorized()
    return Promise.reject(error)
  },
)

/**
 * Turn any Axios error into a message a recruiter can read.
 * FastAPI returns {"detail": "text"} or, for validation errors, {"detail": [{loc, msg}, ...]}.
 */
export function getErrorMessage(error) {
  if (error?.code === 'ECONNABORTED') return 'The server took too long to respond. Please try again.'
  if (!error?.response) {
    return `Cannot reach the TalentMatch AI server at ${API_BASE_URL}. Is the backend running?`
  }
  const detail = error.response.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = (d.loc || []).filter((p) => p !== 'body' && p !== 'query').join(' → ')
        return field ? `${field}: ${d.msg}` : d.msg
      })
      .join('; ')
  }
  return `Request failed (HTTP ${error.response.status}).`
}

const data = (response) => response.data

export const systemApi = {
  health: () => api.get('/health').then(data),
  settings: () => api.get('/settings/').then(data),
}

export const jobsApi = {
  analyzeText: (description, jobTitle) =>
    api.post('/jobs/analyze', { description, job_title: jobTitle || null }).then(data),
  analyzeFile: (file, jobTitle) => {
    const form = new FormData()
    form.append('file', file)
    if (jobTitle) form.append('job_title', jobTitle)
    return api.post('/jobs/analyze-file', form, { timeout: LONG_TIMEOUT }).then(data)
  },
  list: () => api.get('/jobs/').then(data),
  get: (jobId) => api.get(`/jobs/${jobId}`).then(data),
  create: (job) => api.post('/jobs/', job).then(data),
  update: (jobId, changes) => api.put(`/jobs/${jobId}`, changes).then(data),
  remove: (jobId) => api.delete(`/jobs/${jobId}`),
}

// Hosting platforms limit the size of one request (Vercel: 4.5 MB), so a batch of resumes is
// sent in groups of at most this many bytes. The recruiter still selects all files at once.
const MAX_UPLOAD_GROUP_BYTES = 3.5 * 1024 * 1024
const MAX_UPLOAD_GROUP_FILES = 10

export function groupFilesForUpload(files) {
  const groups = []
  let current = []
  let size = 0
  for (const file of files) {
    const tooBig = size + file.size > MAX_UPLOAD_GROUP_BYTES || current.length >= MAX_UPLOAD_GROUP_FILES
    if (current.length && tooBig) {
      groups.push(current)
      current = []
      size = 0
    }
    current.push(file)
    size += file.size
  }
  if (current.length) groups.push(current)
  return groups
}

export const resumesApi = {
  /**
   * Upload resumes in groups (see MAX_UPLOAD_GROUP_BYTES) and combine the results.
   * onProgress receives 0-100 across ALL files while they are being sent (real upload progress).
   */
  upload: async (files, onProgress) => {
    const totalBytes = files.reduce((sum, file) => sum + file.size, 0) || 1
    let sentBytes = 0
    const combined = { total_files: 0, parsed: 0, duplicates: 0, failed: 0, candidate_ids: [], files: [] }
    for (const group of groupFilesForUpload(files)) {
      const form = new FormData()
      group.forEach((file) => form.append('files', file))
      const groupBytes = group.reduce((sum, file) => sum + file.size, 0)
      const result = await api
        .post('/resumes/upload', form, {
          timeout: LONG_TIMEOUT,
          onUploadProgress: (event) => {
            if (onProgress && event.total) {
              onProgress(Math.min(100, Math.round(((sentBytes + (event.loaded / event.total) * groupBytes) / totalBytes) * 100)))
            }
          },
        })
        .then(data)
      sentBytes += groupBytes
      for (const key of ['total_files', 'parsed', 'duplicates', 'failed']) combined[key] += result[key]
      combined.candidate_ids.push(...result.candidate_ids)
      combined.files.push(...result.files)
    }
    return combined
  },
}

/** Drop empty values so they are not sent as "?search=" etc. */
function cleanParams(params = {}) {
  return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
}

export const analysisApi = {
  run: (jobId, candidateIds) =>
    api.post(`/analyze/${jobId}`, { candidate_ids: candidateIds }, { timeout: LONG_TIMEOUT }).then(data),
  results: (jobId, params) => api.get(`/results/${jobId}`, { params: cleanParams(params) }).then(data),
  history: (params) => api.get('/analyses/', { params: cleanParams(params) }).then(data),
  /** Returns { blob, filename } for the CSV download. */
  exportCsv: async (jobId, params) => {
    const response = await api.get(`/results/${jobId}/export`, { params: cleanParams(params), responseType: 'blob' })
    const disposition = response.headers['content-disposition'] || ''
    const filename = /filename="([^"]+)"/.exec(disposition)?.[1] || 'talentmatch_results.csv'
    return { blob: response.data, filename }
  },
}

export const candidatesApi = {
  list: (params) => api.get('/candidates/', { params: cleanParams(params) }).then(data),
  get: (candidateId) => api.get(`/candidates/${candidateId}`).then(data),
  analysis: (candidateId, jobId, analysisId) =>
    api.get(`/candidates/${candidateId}/analysis/${jobId}`, { params: cleanParams({ analysis_id: analysisId }) }).then(data),
  remove: (candidateId) => api.delete(`/candidates/${candidateId}`),
}

export const dashboardApi = {
  stats: () => api.get('/dashboard/stats').then(data),
}

export const authApi = {
  setupStatus: () => api.get('/auth/setup-status').then(data),
  setup: (fullName, email, password) => api.post('/auth/setup', { full_name: fullName, email, password }).then(data),
  login: (email, password) => api.post('/auth/login', { email, password }).then(data),
  me: () => api.get('/auth/me').then(data),
  changePassword: (currentPassword, newPassword) =>
    api.post('/auth/change-password', { current_password: currentPassword, new_password: newPassword }),
}

/** Admin-only account management. */
export const usersApi = {
  list: () => api.get('/users/').then(data),
  create: (account) => api.post('/users/', account).then(data),
  update: (userId, changes) => api.patch(`/users/${userId}`, changes).then(data),
  resetPassword: (userId, newPassword) => api.post(`/users/${userId}/reset-password`, { new_password: newPassword }),
}

export default api
