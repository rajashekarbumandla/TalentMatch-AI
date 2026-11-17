/**
 * New Analysis wizard
 *   Step 1 - Job:      choose a saved job, or paste/upload a JD -> review extracted requirements -> save
 *   Step 2 - Resumes:  drag & drop PDF/DOCX files, instant format/size checks
 *   Step 3 - Results:  real upload progress -> server parses resumes -> matching & ranking -> summary
 */
import {
  ArrowLeft, ArrowRight, BriefcaseBusiness, CheckCircle2, Circle, FileSearch, FileText, Loader2, Sparkles, Trophy, Upload, XCircle,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import FileDropzone from '../components/FileDropzone'
import RequirementsEditor from '../components/RequirementsEditor'
import { SkillChips } from '../components/Skills'
import { useToast } from '../components/Toast'
import { Badge, Button, Card, CardHeader, ErrorState, Field, Notice, PageHeader, SegmentedControl, Spinner, inputClass } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { useSettings } from '../hooks/useSettings'
import { analysisApi, getErrorMessage, jobsApi, resumesApi } from '../services/api'
import { formatYears, pluralize } from '../utils/format'
import { emptyRequirements, toJobPayload, validateRequirements } from '../utils/requirements'

const STEPS = ['Job description', 'Upload resumes', 'Analysis']

function Stepper({ step }) {
  return (
    <ol className="mb-6 flex flex-wrap items-center gap-2 text-sm" aria-label="Progress">
      {STEPS.map((label, index) => {
        const number = index + 1
        const state = number < step ? 'done' : number === step ? 'current' : 'todo'
        return (
          <li key={label} className="flex items-center gap-2" aria-current={state === 'current' ? 'step' : undefined}>
            <span
              className={`flex size-7 items-center justify-center rounded-full text-xs font-semibold ${
                state === 'done' ? 'bg-emerald-600 text-white' : state === 'current' ? 'bg-navy-900 text-white' : 'bg-slate-200 text-slate-600'
              }`}
            >
              {state === 'done' ? <CheckCircle2 className="size-4" aria-hidden="true" /> : number}
            </span>
            <span className={state === 'todo' ? 'text-slate-500' : 'font-medium text-slate-900'}>{label}</span>
            {number < STEPS.length && <span className="mx-1 h-px w-8 bg-slate-300 sm:w-12" aria-hidden="true" />}
          </li>
        )
      })}
    </ol>
  )
}

/* ---------- Step 1: job ------------------------------------------------------------------------- */

function SavedJobSummary({ job }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
      <p className="font-semibold text-slate-900">{job.job_title}</p>
      <p className="mt-1 text-slate-600">
        Minimum experience: {job.minimum_experience === null ? 'No requirement' : formatYears(job.minimum_experience)}
      </p>
      <div className="mt-3 space-y-2">
        <div><p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Required skills</p><SkillChips skills={job.required_skills} tone="required" /></div>
        <div><p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Preferred skills</p><SkillChips skills={job.preferred_skills} tone="preferred" /></div>
      </div>
    </div>
  )
}

function JobStep({ initialJobId, onJobReady }) {
  const toast = useToast()
  const { limits } = useSettings()
  const jobs = useApi(() => jobsApi.list(), [])
  const [mode, setMode] = useState(initialJobId ? 'saved' : 'new')
  const [selectedId, setSelectedId] = useState(initialJobId || '')
  const [source, setSource] = useState('paste')
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [jdFiles, setJdFiles] = useState([])
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState(null)
  const [form, setForm] = useState(emptyRequirements)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const jobList = useMemo(() => jobs.data || [], [jobs.data])
  const selectedJob = useMemo(() => jobList.find((j) => j.id === selectedId), [jobList, selectedId])

  const analyze = async () => {
    setAnalyzing(true)
    try {
      const result =
        source === 'file' ? await jobsApi.analyzeFile(jdFiles[0].file, title) : await jobsApi.analyzeText(text, title)
      setAnalysis(result)
      setForm({
        job_title: result.job_title || title,
        description: result.description,
        required_skills: result.required_skills,
        preferred_skills: result.preferred_skills,
        minimum_experience: result.minimum_experience ?? '',
        education_requirements: result.education_requirements || '',
        responsibilities: result.responsibilities,
        keywords: result.keywords,
      })
      setErrors({})
      toast.success('Requirements extracted. Please review them below.')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setAnalyzing(false)
    }
  }

  const save = async () => {
    const found = validateRequirements(form)
    setErrors(found)
    if (Object.keys(found).length) return
    setSaving(true)
    try {
      const job = await jobsApi.create(toJobPayload(form))
      toast.success(`"${job.job_title}" saved.`)
      onJobReady(job)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const canAnalyze = source === 'paste' ? text.trim().length >= 30 : jdFiles.length === 1 && !jdFiles[0].error

  return (
    <Card>
      <CardHeader icon={BriefcaseBusiness} title="Which job are you hiring for?" description="Use a saved job description or add a new one." />
      <div className="space-y-5 p-5">
        <SegmentedControl
          label="Job source"
          value={mode}
          onChange={setMode}
          options={[
            { value: 'new', label: 'New job description' },
            { value: 'saved', label: `Saved job${jobList.length ? ` (${jobList.length})` : ''}` },
          ]}
        />

        {mode === 'saved' && (
          <div className="space-y-4">
            {jobs.loading && !jobs.data ? (
              <Spinner label="Loading saved jobs…" />
            ) : jobs.error ? (
              <ErrorState message={jobs.error} onRetry={jobs.reload} />
            ) : jobList.length === 0 ? (
              <Notice>No saved jobs yet. Choose “New job description” to add one.</Notice>
            ) : (
              <>
                <Field label="Saved job">
                  {(id) => (
                    <select id={id} className={inputClass} value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
                      <option value="">Select a job…</option>
                      {jobList.map((j) => <option key={j.id} value={j.id}>{j.job_title}</option>)}
                    </select>
                  )}
                </Field>
                {selectedJob && <SavedJobSummary job={selectedJob} />}
                <div className="flex justify-end">
                  <Button icon={ArrowRight} disabled={!selectedJob} onClick={() => onJobReady(selectedJob)}>
                    Continue to resumes
                  </Button>
                </div>
              </>
            )}
          </div>
        )}

        {mode === 'new' && !analysis && (
          <div className="space-y-4">
            <Field label="Job title" hint="Optional. Detected from the description if left empty.">
              {(id) => <input id={id} className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Python Developer" />}
            </Field>
            <SegmentedControl
              label="Job description input"
              value={source}
              onChange={setSource}
              options={[{ value: 'paste', label: 'Paste text' }, { value: 'file', label: 'Upload PDF / DOCX' }]}
            />
            {source === 'paste' ? (
              <Field label="Job description" hint={`${text.trim().length} characters (minimum 30). Paste the complete JD for the best results.`}>
                {(id) => (
                  <textarea
                    id={id}
                    rows={10}
                    className={inputClass}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="We are looking for a Python Developer with at least 3 years of experience in Python, FastAPI, SQL…"
                  />
                )}
              </Field>
            ) : (
              <FileDropzone files={jdFiles} onChange={setJdFiles} limits={limits} multiple={false} label="Drop the job description here, or" />
            )}
            <div className="flex justify-end">
              <Button icon={Sparkles} variant="accent" onClick={analyze} loading={analyzing} disabled={!canAnalyze}>
                {analyzing ? 'Analysing…' : 'Extract requirements'}
              </Button>
            </div>
          </div>
        )}

        {mode === 'new' && analysis && (
          <div className="space-y-5">
            <Notice title="Review before saving">
              These requirements were extracted automatically. Correct anything that looks wrong; the ranking uses exactly what you save.
            </Notice>
            {analysis.warnings.length > 0 && (
              <Notice tone="warning" title="Please check">
                <ul className="list-disc pl-4">{analysis.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
              </Notice>
            )}
            <RequirementsEditor form={form} onChange={setForm} errors={errors} />
            {analysis.education_level && (
              <p className="text-xs text-slate-500">Detected minimum degree level: <Badge>{analysis.education_level}</Badge></p>
            )}
            <div className="flex flex-wrap justify-between gap-2 border-t border-slate-100 pt-4">
              <Button variant="secondary" icon={ArrowLeft} onClick={() => setAnalysis(null)}>Back to description</Button>
              <Button icon={ArrowRight} onClick={save} loading={saving}>Save job and continue</Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}

/* ---------- Step 2: resumes ------------------------------------------------------------------------ */

function ResumesStep({ job, files, onFilesChange, onBack, onStart }) {
  const { limits } = useSettings()
  const valid = files.filter((f) => !f.error)
  const invalid = files.length - valid.length
  const tooMany = valid.length > limits.maxFilesPerBatch
  return (
    <Card>
      <CardHeader
        icon={Upload}
        title="Upload candidate resumes"
        description={`Matching against: ${job.job_title}. Select all the resumes you want to compare (10 or more is fine).`}
      />
      <div className="space-y-4 p-5">
        <FileDropzone files={files} onChange={onFilesChange} limits={limits} />
        {files.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge>{pluralize(files.length, 'file')} selected</Badge>
            <Badge className="bg-emerald-50 text-emerald-800 ring-emerald-600/20">{valid.length} ready</Badge>
            {invalid > 0 && <Badge className="bg-red-50 text-red-700 ring-red-600/20">{invalid} cannot be used</Badge>}
            <span className="text-xs text-slate-500">Supported: {limits.allowedExtensions.join(', ')}</span>
          </div>
        )}
        {tooMany && <Notice tone="warning">At most {limits.maxFilesPerBatch} resumes can be analysed at once. Remove some files.</Notice>}
        <p className="text-xs text-slate-500">
          Files are only used to extract text and candidate details; the original files are not stored.
        </p>
        <div className="flex flex-wrap justify-between gap-2 border-t border-slate-100 pt-4">
          <Button variant="secondary" icon={ArrowLeft} onClick={onBack}>Change job</Button>
          <Button variant="accent" icon={Sparkles} disabled={!valid.length || tooMany} onClick={onStart}>
            Analyse {valid.length ? pluralize(valid.length, 'resume') : 'resumes'}
          </Button>
        </div>
      </div>
    </Card>
  )
}

/* ---------- Step 3: processing ----------------------------------------------------------------------- */

function StageRow({ state, label, detail }) {
  const icon = {
    done: <CheckCircle2 className="size-5 text-emerald-600" aria-hidden="true" />,
    active: <Loader2 className="size-5 animate-spin text-brand-600" aria-hidden="true" />,
    error: <XCircle className="size-5 text-red-600" aria-hidden="true" />,
    todo: <Circle className="size-5 text-slate-300" aria-hidden="true" />,
  }[state]
  return (
    <li className="flex items-start gap-3">
      {icon}
      <div>
        <p className={`text-sm font-medium ${state === 'todo' ? 'text-slate-400' : 'text-slate-900'}`}>{label}</p>
        {detail && <p className="text-xs text-slate-500">{detail}</p>}
      </div>
    </li>
  )
}

/**
 * Runs upload -> analysis. Started from the "Analyse" button click (an event, so it runs exactly once;
 * starting it in useEffect would run twice in React StrictMode and upload everything twice).
 * `update` receives partial state changes for the progress screen.
 */
async function runAnalysis(job, files, update) {
  const STAGES = ['uploading', 'parsing', 'analyzing']
  let current = 'uploading'
  const go = (stage) => {
    current = stage
    update({ stage })
  }
  try {
    const uploaded = await resumesApi.upload(files.map((f) => f.file), (percent) => {
      update({ progress: percent })
      if (percent >= 100 && current === 'uploading') go('parsing') // all bytes sent: the server is reading the resumes
    })
    update({ upload: uploaded })
    if (!uploaded.candidate_ids.length) {
      update({ stage: 'error', failedAt: 'parsing', error: 'None of the files could be read as a resume. See the reasons below, fix the files and try again.' })
      return null
    }
    go('analyzing')
    const result = await analysisApi.run(job.id, uploaded.candidate_ids)
    update({ stage: 'done', analysis: result })
    return result
  } catch (err) {
    update({ stage: 'error', failedAt: STAGES.includes(current) ? current : 'uploading', error: getErrorMessage(err) })
    return null
  }
}

const INITIAL_RUN = { stage: 'uploading', progress: 0, upload: null, analysis: null, error: null, failedAt: null }

function stageState(run, name) {
  const order = ['uploading', 'parsing', 'analyzing', 'done']
  const reached = run.stage === 'error' ? run.failedAt : run.stage
  const index = order.indexOf(name)
  const current = order.indexOf(reached)
  if (index < current) return 'done'
  if (index > current) return 'todo'
  return run.stage === 'error' ? 'error' : 'active'
}

function ProcessingStep({ job, files, run, onBack }) {
  const navigate = useNavigate()
  const { stage, progress, upload, analysis, error } = run
  const stateOf = (name) => stageState(run, name)
  const problems = upload?.files.filter((f) => f.status !== 'parsed') || []
  const withWarnings = upload?.files.filter((f) => f.status === 'parsed' && f.warnings.length) || []
  const top = analysis?.items[0]

  return (
    <Card>
      <CardHeader icon={FileSearch} title={`Analysing resumes for ${job.job_title}`} description="Please keep this page open until the analysis is complete." />
      <div className="grid gap-6 p-5 lg:grid-cols-2">
        <ol className="space-y-4">
          <StageRow state={stateOf('uploading')} label="Uploading files" detail={stage === 'uploading' ? `${progress}% sent` : `${pluralize(files.length, 'file')}`} />
          <StageRow
            state={stateOf('parsing')}
            label="Reading resumes"
            detail={upload ? `${upload.parsed} read · ${upload.duplicates} duplicates · ${upload.failed} could not be read` : 'Extracting contact details, skills, education and experience'}
          />
          <StageRow
            state={stateOf('analyzing')}
            label="Matching and ranking"
            detail={analysis ? `${analysis.total_candidates} candidates scored` : 'Semantic similarity, skills and experience'}
          />
          {stage === 'uploading' && (
            <div className="h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} aria-label="Upload progress">
              <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${progress}%` }} />
            </div>
          )}
        </ol>

        <div className="space-y-4">
          {stage === 'error' && <ErrorState message={error} />}
          {stage === 'done' && top && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <p className="flex items-center gap-2 text-sm font-semibold text-emerald-900">
                <Trophy className="size-4" aria-hidden="true" /> Top match: {top.name || 'Name not found'} ({top.final_score.toFixed(2)})
              </p>
              <p className="mt-1 text-sm text-emerald-800">Average score: {analysis.analysis.average_score?.toFixed(2)}</p>
              <Button
                className="mt-3"
                icon={ArrowRight}
                onClick={() => navigate(`/rankings?jobId=${job.id}&analysisId=${analysis.analysis.id}`)}
              >
                View candidate ranking
              </Button>
            </div>
          )}
          {problems.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-medium text-slate-900">Files not included ({problems.length})</p>
              <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm">
                {problems.map((f) => (
                  <li key={f.filename + f.status} className="flex gap-2 px-3 py-2">
                    <FileText className="mt-0.5 size-4 shrink-0 text-slate-400" aria-hidden="true" />
                    <div>
                      <p className="font-medium text-slate-900">{f.filename}</p>
                      <p className="text-xs text-slate-600">{f.status === 'duplicate' ? `Same file as ${f.duplicate_of}; analysed once.` : f.error}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {withWarnings.length > 0 && stage === 'done' && (
            <Notice tone="warning" title={`${pluralize(withWarnings.length, 'resume')} with missing details`}>
              Some details (e.g. email or experience dates) were not found. They are shown as “Not found” and never guessed; check the candidate pages.
            </Notice>
          )}
          {stage === 'error' && (
            <Button variant="secondary" icon={ArrowLeft} onClick={onBack}>Back to resumes</Button>
          )}
        </div>
      </div>
    </Card>
  )
}

/* ---------- Page ----------------------------------------------------------------------------------- */

export default function NewAnalysisPage() {
  const [searchParams] = useSearchParams()
  const toast = useToast()
  const [step, setStep] = useState(1)
  const [job, setJob] = useState(null)
  const [files, setFiles] = useState([])
  const [run, setRun] = useState(INITIAL_RUN)

  const start = async () => {
    setRun(INITIAL_RUN)
    setStep(3)
    const result = await runAnalysis(job, files.filter((f) => !f.error), (changes) => setRun((r) => ({ ...r, ...changes })))
    if (result) toast.success(`Analysis complete: ${pluralize(result.total_candidates, 'candidate')} ranked.`)
  }

  return (
    <>
      <PageHeader
        title="New analysis"
        description="Compare a batch of resumes against a job description. You stay in control: review the extracted requirements, then the ranking."
      />
      <Stepper step={step} />
      {step === 1 && (
        <JobStep
          initialJobId={searchParams.get('jobId')}
          onJobReady={(selected) => {
            setJob(selected)
            setStep(2)
          }}
        />
      )}
      {step === 2 && (
        <ResumesStep
          job={job}
          files={files}
          onFilesChange={setFiles}
          onBack={() => setStep(1)}
          onStart={start}
        />
      )}
      {step === 3 && <ProcessingStep job={job} files={files.filter((f) => !f.error)} run={run} onBack={() => setStep(2)} />}
    </>
  )
}
