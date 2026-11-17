import { Activity, ArrowRight, BarChart3, BriefcaseBusiness, FileText, Gauge, PlusCircle, Star, Trophy, Users } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { ActivityChart, ScoreDistributionChart, ShortlistChart } from '../components/charts'
import { ScoreBadge } from '../components/Score'
import { ButtonLink, Card, CardHeader, EmptyState, ErrorState, PageHeader, Spinner } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { dashboardApi } from '../services/api'
import { formatDateTime, formatScore } from '../utils/format'

function StatTile({ icon: Icon, label, value, hint }) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
        <Icon className="size-4 text-brand-600" aria-hidden="true" />
        {label}
      </div>
      <p className="mt-2 text-3xl font-bold tabular-nums tracking-tight text-navy-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </Card>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { data: stats, loading, error, reload } = useApi(() => dashboardApi.stats(), [])

  const actions = (
    <ButtonLink to="/analysis/new" icon={PlusCircle} variant="accent">
      New analysis
    </ButtonLink>
  )

  if (loading && !stats) return <><PageHeader title="Dashboard" actions={actions} /><Spinner label="Loading dashboard…" /></>
  if (error && !stats) return <><PageHeader title="Dashboard" /><ErrorState message={error} onRetry={reload} /></>

  if (stats.total_analyses === 0) {
    return (
      <>
        <PageHeader title="Welcome to TalentMatch AI" description="Intelligent Resume Screening. Smarter Hiring Decisions." />
        <Card>
          <EmptyState
            icon={Trophy}
            title="No analyses yet"
            description="Add a job description, upload candidate resumes (PDF or DOCX) and TalentMatch AI will rank them with an explainable 0–100 score."
            action={<ButtonLink to="/analysis/new" icon={PlusCircle} variant="accent">Start your first analysis</ButtonLink>}
          />
          <ol className="grid gap-4 border-t border-slate-100 p-6 text-sm sm:grid-cols-3">
            {[
              ['1', 'Describe the job', 'Paste or upload the JD. Skills, experience and education are extracted for you to review.'],
              ['2', 'Upload resumes', 'Drag in 10 or more resumes at once. Contact details, skills and experience are read automatically.'],
              ['3', 'Review the ranking', 'See who fits best, why, and what to verify in the interview.'],
            ].map(([step, title, text]) => (
              <li key={step} className="flex gap-3">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-navy-900 text-xs font-semibold text-white">{step}</span>
                <div>
                  <p className="font-medium text-slate-900">{title}</p>
                  <p className="text-slate-500">{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      </>
    )
  }

  const overview = stats.ranking_overview
  return (
    <>
      <PageHeader title="Dashboard" description="An overview of your screening activity, based on all saved analyses." actions={actions} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatTile icon={FileText} label="Resumes analysed" value={stats.resumes_analyzed} hint={`${stats.total_analyses} analyses run`} />
        <StatTile icon={BriefcaseBusiness} label="Job descriptions" value={stats.total_jobs} />
        <StatTile icon={Users} label="Candidates" value={stats.total_candidates} hint="Resumes uploaded" />
        <StatTile icon={Gauge} label="Average score" value={formatScore(stats.average_score, 1)} hint="Across all results" />
        <StatTile icon={Star} label="High-match candidates" value={stats.high_match_candidates} hint={`Scored ${stats.high_match_threshold} or more`} />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader
            icon={Trophy}
            title="Latest shortlist"
            description={overview ? `Top candidates for ${overview.job_title}. Click a bar to open the candidate.` : undefined}
            action={overview && <ButtonLink to={`/rankings?jobId=${overview.job_id}&analysisId=${overview.analysis_id}`} variant="secondary" size="sm">Full ranking</ButtonLink>}
          />
          <div className="p-4">
            {overview?.candidates.length ? (
              <ShortlistChart
                candidates={overview.candidates}
                onSelect={(c) => navigate(`/candidates/${c.candidate_id}/jobs/${overview.job_id}?analysisId=${overview.analysis_id}`)}
              />
            ) : (
              <p className="py-10 text-center text-sm text-slate-500">No candidates in the latest analysis.</p>
            )}
          </div>
        </Card>
        <Card className="xl:col-span-2">
          <CardHeader icon={BarChart3} title="Score distribution" description="Number of candidate results per score range." />
          <div className="p-4">
            <ScoreDistributionChart buckets={stats.score_distribution} />
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader
            title="Recent analyses"
            action={<ButtonLink to="/history" variant="ghost" size="sm">View all</ButtonLink>}
          />
          <div className="relative overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-2.5 font-medium">Job title</th>
                  <th className="px-3 py-2.5 font-medium">Resumes</th>
                  <th className="px-3 py-2.5 font-medium">Average score</th>
                  <th className="px-3 py-2.5 font-medium">Date</th>
                  <th className="px-5 py-2.5"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {stats.recent_analyses.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3 font-medium text-slate-900">{a.job_title}</td>
                    <td className="px-3 py-3 tabular-nums">{a.total_resumes}</td>
                    <td className="px-3 py-3">
                      <span className="mr-2 tabular-nums">{formatScore(a.average_score)}</span>
                      <ScoreBadge score={a.average_score} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-slate-500">{formatDateTime(a.created_at)}</td>
                    <td className="px-5 py-3 text-right">
                      <ButtonLink to={`/rankings?jobId=${a.job_id}&analysisId=${a.id}`} variant="ghost" size="sm" className="whitespace-nowrap">
                        View results <ArrowRight className="size-3.5" aria-hidden="true" />
                      </ButtonLink>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card className="xl:col-span-2">
          <CardHeader icon={Activity} title="Activity (last 30 days)" description="Resumes analysed per day." />
          <div className="p-4">
            <ActivityChart points={stats.activity} />
          </div>
        </Card>
      </div>
    </>
  )
}
