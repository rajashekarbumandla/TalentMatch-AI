/** All past analyses (newest first), optionally filtered by job. Every analysis stays viewable. */
import { ArrowRight, History, PlusCircle } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { ScoreBadge } from '../components/Score'
import { ButtonLink, Card, EmptyState, ErrorState, Field, PageHeader, Spinner, inputClass } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { analysisApi, jobsApi } from '../services/api'
import { formatDateTime, formatScore } from '../utils/format'

export default function HistoryPage() {
  const [params, setParams] = useSearchParams()
  const jobId = params.get('jobId') || ''
  const jobs = useApi(() => jobsApi.list(), [])
  const { data: analyses, loading, error, reload } = useApi(() => analysisApi.history({ job_id: jobId, limit: 200 }), [jobId])

  return (
    <>
      <PageHeader
        title="Analysis history"
        description="Every analysis is saved. Open any of them to see its ranking exactly as it was calculated."
        actions={<ButtonLink to="/analysis/new" icon={PlusCircle} variant="accent">New analysis</ButtonLink>}
      />
      <Card>
        <div className="border-b border-slate-100 p-4 sm:max-w-sm">
          <Field label="Job">
            {(id) => (
              <select id={id} className={inputClass} value={jobId} onChange={(e) => setParams(e.target.value ? { jobId: e.target.value } : {})}>
                <option value="">All jobs</option>
                {(jobs.data || []).map((j) => <option key={j.id} value={j.id}>{j.job_title}</option>)}
              </select>
            )}
          </Field>
        </div>
        {loading && !analyses ? (
          <Spinner />
        ) : error && !analyses ? (
          <div className="p-5"><ErrorState message={error} onRetry={reload} /></div>
        ) : !analyses.length ? (
          <EmptyState icon={History} title="No analyses yet" description={jobId ? 'This job has not been analysed yet.' : 'Run your first analysis to see it here.'} />
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-2.5 font-medium">Date</th>
                  <th className="px-3 py-2.5 font-medium">Job title</th>
                  <th className="px-3 py-2.5 font-medium">Resumes analysed</th>
                  <th className="px-3 py-2.5 font-medium">Average score</th>
                  <th className="px-5 py-2.5"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {analyses.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50">
                    <td className="whitespace-nowrap px-5 py-3 text-slate-600">{formatDateTime(a.created_at)}</td>
                    <td className="px-3 py-3 font-medium text-slate-900">{a.job_title}</td>
                    <td className="px-3 py-3 tabular-nums">{a.total_resumes}</td>
                    <td className="px-3 py-3"><span className="mr-2 tabular-nums">{formatScore(a.average_score)}</span><ScoreBadge score={a.average_score} /></td>
                    <td className="px-5 py-3 text-right">
                      <ButtonLink to={`/rankings?jobId=${a.job_id}&analysisId=${a.id}`} variant="ghost" size="sm">
                        View results <ArrowRight className="size-3.5" aria-hidden="true" />
                      </ButtonLink>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
