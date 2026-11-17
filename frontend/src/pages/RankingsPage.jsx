/**
 * Candidate ranking for one analysis. All filtering, sorting and ranking is done by the
 * backend (SQL); this page only sends parameters. Filters live in the URL, so a shortlist
 * view can be bookmarked or shared with the hiring manager.
 */
import { AlertCircle, ArrowDown, ArrowUp, ArrowUpDown, ChevronRight, Download, PlusCircle, Search, Trophy, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ScoreBadge, ScoreBar } from '../components/Score'
import { SkillChips } from '../components/Skills'
import { useToast } from '../components/Toast'
import { Badge, Button, ButtonLink, Card, EmptyState, ErrorState, Field, PageHeader, SegmentedControl, Spinner, inputClass } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { useDebounce } from '../hooks/useDebounce'
import { analysisApi, getErrorMessage, jobsApi } from '../services/api'
import { saveBlob } from '../utils/download'
import { formatDateTime, formatScore, formatYears, orNotFound, pluralize } from '../utils/format'
import { BAND_FILTERS } from '../utils/scoring'

const BAND_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'strong', label: 'Strong 80+' },
  { value: 'good', label: 'Good 60–79' },
  { value: 'partial', label: 'Partial 40–59' },
  { value: 'limited', label: 'Limited <40' },
]
const TOP_OPTIONS = [
  { value: '', label: 'All' },
  { value: '5', label: 'Top 5' },
  { value: '10', label: 'Top 10' },
]
const EXPERIENCE_OPTIONS = ['', '1', '2', '3', '5', '8']

function SortHeader({ field, label, sort, order, onSort, className = '' }) {
  const active = sort === field
  const Icon = !active ? ArrowUpDown : order === 'asc' ? ArrowUp : ArrowDown
  return (
    <th className={`px-3 py-2.5 font-medium ${className}`} aria-sort={active ? (order === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" onClick={() => onSort(field)} className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-slate-900">
        {label}
        <Icon className={`size-3 ${active ? 'text-slate-900' : 'text-slate-400'}`} aria-hidden="true" />
      </button>
    </th>
  )
}

function TopMatchCard({ item, jobId, analysisId }) {
  return (
    <Card className="mb-4 border-emerald-200 bg-gradient-to-r from-emerald-50 to-white p-5">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex size-11 items-center justify-center rounded-full bg-emerald-600 text-white">
          <Trophy className="size-5" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-emerald-800">Top match</p>
          <p className="text-lg font-semibold text-navy-900">{orNotFound(item.name)}</p>
          <p className="text-sm text-slate-600">
            {formatScore(item.final_score)} / 100 · {item.matched_skills.length} of {item.matched_skills.length + item.missing_skills.length} skills found ·{' '}
            {formatYears(item.relevant_experience)} relevant experience
          </p>
        </div>
        <ButtonLink to={`/candidates/${item.candidate_id}/jobs/${jobId}?analysisId=${analysisId}`} icon={ChevronRight}>
          View analysis
        </ButtonLink>
      </div>
    </Card>
  )
}

export default function RankingsPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [exporting, setExporting] = useState(false)

  const jobs = useApi(() => jobsApi.list(), [])
  const analysedJobs = useMemo(
    () =>
      (jobs.data || [])
        .filter((j) => j.analysis_count > 0)
        .sort((a, b) => (b.latest_analysis_at || '').localeCompare(a.latest_analysis_at || '')),
    [jobs.data],
  )
  const jobId = params.get('jobId') || analysedJobs[0]?.id || ''
  const analysisId = params.get('analysisId') || ''
  const search = params.get('search') || ''
  const band = params.get('band') || ''
  const top = params.get('top') || ''
  const minExperience = params.get('minExp') || ''
  const sort = params.get('sort') || 'rank'
  const order = params.get('order') || ''
  const [searchDraft, setSearchDraft] = useState(search)
  const debouncedSearch = useDebounce(searchDraft)

  const update = useCallback(
    (changes) =>
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          Object.entries(changes).forEach(([key, value]) => (value ? next.set(key, value) : next.delete(key)))
          return next
        },
        { replace: true },
      ),
    [setParams],
  )
  // Copy the debounced search box value into the URL (which triggers the API request).
  useEffect(() => {
    update({ search: debouncedSearch.trim() })
  }, [debouncedSearch, update])

  const queryParams = {
    analysis_id: analysisId,
    search,
    top,
    min_experience: minExperience,
    sort_by: sort,
    order,
    ...(BAND_FILTERS[band] || {}),
  }
  const history = useApi(() => (jobId ? analysisApi.history({ job_id: jobId }) : Promise.resolve([])), [jobId])
  const results = useApi(() => (jobId ? analysisApi.results(jobId, queryParams) : Promise.resolve(null)), [jobId, queryParams])

  const onSort = (field) => {
    if (sort === field) update({ order: order === 'asc' ? 'desc' : 'asc' })
    else update({ sort: field === 'rank' ? '' : field, order: '' })
  }
  const filtersActive = Boolean(search || band || top || minExperience)
  const clearFilters = () => {
    setSearchDraft('')
    update({ search: '', band: '', top: '', minExp: '' })
  }

  const exportCsv = async () => {
    setExporting(true)
    try {
      const { blob, filename } = await analysisApi.exportCsv(jobId, queryParams)
      saveBlob(blob, filename)
      toast.success(`Exported ${filename}`)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setExporting(false)
    }
  }

  if (jobs.loading && !jobs.data) return <><PageHeader title="Candidate rankings" /><Spinner /></>
  if (jobs.error) return <><PageHeader title="Candidate rankings" /><ErrorState message={jobs.error} onRetry={jobs.reload} /></>
  if (!analysedJobs.length) {
    return (
      <>
        <PageHeader title="Candidate rankings" />
        <Card>
          <EmptyState
            icon={Trophy}
            title="No rankings yet"
            description="Run an analysis to rank candidates against a job description."
            action={<ButtonLink to="/analysis/new" icon={PlusCircle} variant="accent">New analysis</ButtonLink>}
          />
        </Card>
      </>
    )
  }

  const data = results.data
  const items = data?.items || []
  const showTopCard = data && !filtersActive && items[0]?.rank === 1

  return (
    <>
      <PageHeader
        title="Candidate rankings"
        description="Ranked from highest to lowest match. Scores support your judgement; review each shortlisted candidate before deciding."
        actions={
          <>
            <ButtonLink to={`/analysis/new?jobId=${jobId}`} variant="secondary" icon={PlusCircle}>Re-run with new resumes</ButtonLink>
            <Button icon={Download} onClick={exportCsv} loading={exporting} disabled={!items.length}>Export CSV</Button>
          </>
        }
      />

      <Card className="mb-4 p-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Job">
            {(id) => (
              <select id={id} className={inputClass} value={jobId} onChange={(e) => update({ jobId: e.target.value, analysisId: '' })}>
                {analysedJobs.map((j) => <option key={j.id} value={j.id}>{j.job_title} ({pluralize(j.analysis_count, 'analysis', 'analyses')})</option>)}
              </select>
            )}
          </Field>
          <Field label="Analysis">
            {(id) => (
              <select id={id} className={inputClass} value={analysisId} onChange={(e) => update({ analysisId: e.target.value })}>
                <option value="">Most recent</option>
                {(history.data || []).map((a) => (
                  <option key={a.id} value={a.id}>{formatDateTime(a.created_at)} · {a.total_resumes} resumes · avg {formatScore(a.average_score)}</option>
                ))}
              </select>
            )}
          </Field>
        </div>
        <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-slate-100 pt-4">
          <div className="relative min-w-56 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              className={`${inputClass} pl-9`}
              value={searchDraft}
              onChange={(e) => setSearchDraft(e.target.value)}
              placeholder="Search by name or email"
              aria-label="Search candidates by name or email"
            />
          </div>
          <SegmentedControl label="Score band" options={BAND_OPTIONS} value={band} onChange={(v) => update({ band: v })} />
          <SegmentedControl label="Show top" options={TOP_OPTIONS} value={top} onChange={(v) => update({ top: v })} />
          <div className="w-full sm:w-48">
            <select
              className={inputClass}
              value={minExperience}
              onChange={(e) => update({ minExp: e.target.value })}
              aria-label="Minimum relevant experience"
            >
              {EXPERIENCE_OPTIONS.map((v) => <option key={v} value={v}>{v ? `${v}+ yrs relevant` : 'Any experience'}</option>)}
            </select>
          </div>
          {filtersActive && <Button variant="ghost" size="sm" icon={X} onClick={clearFilters}>Clear filters</Button>}
        </div>
      </Card>

      {showTopCard && <TopMatchCard item={items[0]} jobId={jobId} analysisId={data.analysis.id} />}

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-3 text-sm">
          <p className="text-slate-600">
            {data ? (
              <>Showing <strong className="text-slate-900">{data.filtered_count}</strong> of {pluralize(data.total_candidates, 'candidate')} · {data.job.job_title}
                {data.job.minimum_experience !== null && <> · requires {formatYears(data.job.minimum_experience)}</>}</>
            ) : 'Loading…'}
          </p>
          {results.loading && data && <span className="text-xs text-slate-400">Updating…</span>}
        </div>
        {results.error ? (
          <div className="p-5"><ErrorState message={results.error} onRetry={results.reload} /></div>
        ) : !data ? (
          <Spinner label="Loading ranking…" />
        ) : !items.length ? (
          <EmptyState
            icon={Search}
            title="No candidates match these filters"
            action={<Button variant="secondary" onClick={clearFilters}>Clear filters</Button>}
          />
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[960px] text-sm">
              <thead className="bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  <SortHeader field="rank" label="Rank" sort={sort} order={order} onSort={onSort} className="pl-5" />
                  <SortHeader field="name" label="Candidate" sort={sort} order={order} onSort={onSort} />
                  <SortHeader field="total_experience" label="Total exp." sort={sort} order={order} onSort={onSort} />
                  <SortHeader field="relevant_experience" label="Relevant exp." sort={sort} order={order} onSort={onSort} />
                  <SortHeader field="final_score" label="Match" sort={sort} order={order} onSort={onSort} className="w-52" />
                  <th className="px-3 py-2.5 font-medium uppercase tracking-wide">Matched skills</th>
                  <th className="px-3 py-2.5 font-medium uppercase tracking-wide">Missing skills</th>
                  <th className="px-5 py-2.5"><span className="sr-only">Details</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item) => {
                  const detailUrl = `/candidates/${item.candidate_id}/jobs/${jobId}?analysisId=${data.analysis.id}`
                  return (
                    <tr
                      key={item.match_id}
                      onClick={() => navigate(detailUrl)}
                      className={`cursor-pointer align-top hover:bg-slate-50 ${item.rank === 1 ? 'bg-emerald-50/40' : ''}`}
                    >
                      <td className="py-3 pl-5 pr-3">
                        <span className={`inline-flex size-7 items-center justify-center rounded-full text-xs font-semibold ${item.rank === 1 ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-700'}`}>
                          {item.rank}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <p className="font-medium text-slate-900">{orNotFound(item.name)}</p>
                        <p className="text-xs text-slate-500">{orNotFound(item.email)}</p>
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 tabular-nums">{formatYears(item.total_experience)}</td>
                      <td className="whitespace-nowrap px-3 py-3 tabular-nums">{formatYears(item.relevant_experience)}</td>
                      <td className="px-3 py-3">
                        <ScoreBar score={item.final_score} />
                        <div className="mt-1 flex items-center gap-1.5">
                          <ScoreBadge score={item.final_score} />
                          {item.status === 'incomplete' && (
                            <Badge className="bg-amber-50 text-amber-800 ring-amber-600/20">
                              <AlertCircle className="size-3" aria-hidden="true" /> Verify
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3"><SkillChips skills={item.matched_skills} tone="matched" limit={3} /></td>
                      <td className="px-3 py-3"><SkillChips skills={item.missing_skills} tone="missing" limit={3} empty="None" /></td>
                      <td className="px-5 py-3 text-right">
                        <Link to={detailUrl} onClick={(e) => e.stopPropagation()} className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">
                          Details <ChevronRight className="size-4" aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <p className="mt-3 text-xs text-slate-500">
        “Verify” means part of the score could not be calculated (for example, experience dates were missing), so the score is based on the available information only.
      </p>
    </>
  )
}
