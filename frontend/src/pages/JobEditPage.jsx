/** Edit a saved job's requirements. Changes apply to future analyses (past results are kept as they were). */
import { ArrowLeft, Save } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import RequirementsEditor from '../components/RequirementsEditor'
import { useToast } from '../components/Toast'
import { Button, ButtonLink, Card, ErrorState, Notice, PageHeader, Spinner } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { getErrorMessage, jobsApi } from '../services/api'
import { fromJob, toJobPayload, validateRequirements } from '../utils/requirements'

function EditForm({ job }) {
  const navigate = useNavigate()
  const toast = useToast()
  const [form, setForm] = useState(() => fromJob(job))
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const save = async () => {
    const found = validateRequirements(form)
    setErrors(found)
    if (Object.keys(found).length) return
    setSaving(true)
    try {
      await jobsApi.update(job.id, toJobPayload(form))
      toast.success('Job description updated.')
      navigate('/jobs')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-5">
        <Notice>Changes apply to new analyses. Existing results keep the scores they were calculated with; re-run the analysis to update them.</Notice>
      </div>
      <RequirementsEditor form={form} onChange={setForm} errors={errors} showDescription />
      <div className="mt-6 flex justify-end gap-2 border-t border-slate-100 pt-4">
        <ButtonLink to="/jobs" variant="secondary">Cancel</ButtonLink>
        <Button icon={Save} onClick={save} loading={saving}>Save changes</Button>
      </div>
    </Card>
  )
}

export default function JobEditPage() {
  const { jobId } = useParams()
  const { data: job, loading, error, reload } = useApi(() => jobsApi.get(jobId), [jobId])
  return (
    <>
      <ButtonLink to="/jobs" variant="ghost" icon={ArrowLeft} className="mb-4">Back to job descriptions</ButtonLink>
      <PageHeader title={job ? `Edit: ${job.job_title}` : 'Edit job description'} />
      {loading && !job ? <Spinner /> : error && !job ? <ErrorState message={error} onRetry={reload} /> : <EditForm key={job.id} job={job} />}
    </>
  )
}
