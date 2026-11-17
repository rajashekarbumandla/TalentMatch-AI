/** Saved job descriptions: view requirements, edit, delete, run a new analysis, open results. */
import { BriefcaseBusiness, Pencil, PlayCircle, PlusCircle, Trash2, Trophy } from 'lucide-react'
import { useState } from 'react'
import { SkillChips } from '../components/Skills'
import { useToast } from '../components/Toast'
import { Badge, ButtonLink, Button, Card, ConfirmDialog, EmptyState, ErrorState, PageHeader, Spinner } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { getErrorMessage, jobsApi } from '../services/api'
import { formatDate, formatDateTime, formatYears, pluralize } from '../utils/format'

export default function JobsPage() {
  const toast = useToast()
  const { data: jobs, loading, error, reload } = useApi(() => jobsApi.list(), [])
  const [toDelete, setToDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const confirmDelete = async () => {
    setDeleting(true)
    try {
      await jobsApi.remove(toDelete.id)
      toast.success(`"${toDelete.job_title}" deleted.`)
      setToDelete(null)
      reload()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setDeleting(false)
    }
  }

  const actions = <ButtonLink to="/analysis/new" icon={PlusCircle} variant="accent">New job & analysis</ButtonLink>
  return (
    <>
      <PageHeader title="Job descriptions" description="Saved jobs and their extracted requirements. Edit requirements at any time, then re-run the analysis." actions={actions} />
      {loading && !jobs ? (
        <Spinner />
      ) : error && !jobs ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !jobs.length ? (
        <Card>
          <EmptyState icon={BriefcaseBusiness} title="No job descriptions yet" description="Add a JD in a new analysis; it is saved here for reuse." action={actions} />
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {jobs.map((job) => (
            <Card key={job.id} className="flex flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-semibold text-navy-900">{job.job_title}</h2>
                  <p className="text-xs text-slate-500">
                    Created {formatDate(job.created_at)} · {pluralize(job.analysis_count, 'analysis', 'analyses')}
                    {job.latest_analysis_at && ` · last run ${formatDateTime(job.latest_analysis_at)}`}
                  </p>
                </div>
                <Badge>{job.minimum_experience === null ? 'No exp. requirement' : `${formatYears(job.minimum_experience)}+`}</Badge>
              </div>
              <div className="mt-4 flex-1 space-y-3 text-sm">
                <div><p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Required skills</p><SkillChips skills={job.required_skills} tone="required" limit={10} /></div>
                <div><p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Preferred skills</p><SkillChips skills={job.preferred_skills} tone="preferred" limit={8} /></div>
                {job.education_requirements && <p className="text-xs text-slate-500">Education: {job.education_requirements}</p>}
              </div>
              <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
                {job.analysis_count > 0 && <ButtonLink to={`/rankings?jobId=${job.id}`} size="sm" icon={Trophy}>View results</ButtonLink>}
                <ButtonLink to={`/analysis/new?jobId=${job.id}`} size="sm" variant="secondary" icon={PlayCircle}>Run analysis</ButtonLink>
                <ButtonLink to={`/jobs/${job.id}/edit`} size="sm" variant="secondary" icon={Pencil}>Edit</ButtonLink>
                <Button size="sm" variant="dangerGhost" icon={Trash2} className="ml-auto" onClick={() => setToDelete(job)}>Delete</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete job description?"
        message={toDelete ? `"${toDelete.job_title}" and all of its ${pluralize(toDelete.analysis_count, 'analysis', 'analyses')} will be permanently deleted. Uploaded candidates are kept.` : ''}
        confirmLabel="Delete"
        danger
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </>
  )
}
