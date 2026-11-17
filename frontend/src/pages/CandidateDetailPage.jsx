/** One candidate's analysis for one job: score breakdown, skills, experience, explanation and profile. */
import {
  AlertTriangle, ArrowLeft, Award, BriefcaseBusiness, CheckCircle2, ClipboardList, FileText, FolderGit2, GraduationCap,
  HelpCircle, Link2, Mail, MessageSquareText, Phone, Printer, Scale, Sparkles, Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ScoreBadge, ScoreBar, ScoreRing } from '../components/Score'
import { SkillChips, SkillLegend } from '../components/Skills'
import { useToast } from '../components/Toast'
import { Badge, Button, ButtonLink, Card, CardHeader, ConfirmDialog, ErrorState, Notice, Spinner } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { candidatesApi, getErrorMessage } from '../services/api'
import { formatDateTime, formatScore, formatYears, orNotFound } from '../utils/format'
import { COMPONENT_INFO, EXPERIENCE_STATUS } from '../utils/scoring'

function ScoreBreakdown({ match }) {
  const components = [
    ['semantic', match.semantic_score],
    ['skills', match.skills_score],
    ['experience', match.experience_score],
  ]
  return (
    <Card>
      <CardHeader icon={Scale} title="Score breakdown" description="Each part is scored 0–100 and weighted. The points add up to the overall score." />
      <ul className="divide-y divide-slate-100">
        {components.map(([key, score]) => {
          const weight = match.weights_used[key]
          const info = COMPONENT_INFO[key]
          return (
            <li key={key} className="px-5 py-4">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="flex items-center gap-1.5 text-sm font-medium text-slate-900">
                  {info.label}
                  <span title={info.help} className="text-slate-400"><HelpCircle className="size-3.5" aria-hidden="true" /><span className="sr-only">{info.help}</span></span>
                </p>
                <p className="text-xs text-slate-500">
                  {score === null || score === undefined
                    ? 'Not available: its weight was shared by the other parts'
                    : `${formatScore(score)} × ${Math.round(weight * 100)}% = `}
                  {score !== null && score !== undefined && (
                    <span className="font-semibold text-slate-900">{formatScore(score * weight)} points</span>
                  )}
                </p>
              </div>
              <ScoreBar score={score} />
              <p className="mt-1 text-xs text-slate-500">{info.help}</p>
            </li>
          )
        })}
        <li className="flex items-center justify-between bg-slate-50 px-5 py-3 text-sm">
          <span className="font-medium text-slate-900">Overall score</span>
          <span className="font-bold tabular-nums text-navy-900">{formatScore(match.final_score)} / 100</span>
        </li>
      </ul>
      {match.cosine_similarity !== null && (
        <p className="px-5 py-3 text-xs text-slate-500">
          Technical detail: cosine similarity of the AI embeddings = {match.cosine_similarity.toFixed(4)}.
        </p>
      )}
    </Card>
  )
}

/** Facts-only checklist for the interviewer, built from the analysis result. */
function InterviewChecklist({ match, candidate }) {
  const points = []
  match.missing_required_skills.forEach((s) => points.push(`Ask about ${s}: a required skill not found in the resume.`))
  if (match.experience_status === 'not_met') {
    points.push(`Experience: about ${formatYears(match.relevant_experience)} of relevant experience found; the role asks for ${formatYears(match.required_experience)}.`)
  }
  if (match.experience_status === 'unknown') points.push('Experience could not be determined from the resume. Confirm dates and roles.')
  if (match.missing_preferred_skills.length) points.push(`Nice-to-have skills not found: ${match.missing_preferred_skills.join(', ')}.`)
  if (!candidate.email || !candidate.phone) points.push('Contact details are incomplete in the resume.')
  return (
    <Card>
      <CardHeader icon={ClipboardList} title="Points to verify in the interview" description="Gaps found in the resume. The candidate may still have these skills." />
      {points.length ? (
        <ul className="space-y-2 px-5 py-4 text-sm text-slate-700">
          {points.map((p) => (
            <li key={p} className="flex gap-2"><AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-500" aria-hidden="true" />{p}</li>
          ))}
        </ul>
      ) : (
        <p className="flex items-center gap-2 px-5 py-4 text-sm text-emerald-800">
          <CheckCircle2 className="size-4" aria-hidden="true" /> No gaps found against the job requirements.
        </p>
      )}
    </Card>
  )
}

function SkillsCard({ match }) {
  const alternatives = Object.entries(match.satisfied_by).filter(([req, skill]) => req !== skill)
  return (
    <Card>
      <CardHeader icon={Sparkles} title="Skills" action={<SkillLegend />} />
      <div className="grid gap-5 p-5 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Required: found</p>
          <SkillChips skills={match.matched_required_skills} tone="matched" />
        </div>
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Required: not found</p>
          <SkillChips skills={match.missing_required_skills} tone="missing" empty="None, all required skills found" />
        </div>
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Preferred: found</p>
          <SkillChips skills={match.matched_preferred_skills} tone="matched" />
        </div>
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Preferred: not found</p>
          <SkillChips skills={match.missing_preferred_skills} tone="missing" />
        </div>
        <div className="sm:col-span-2">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Additional skills (not requested)</p>
          <SkillChips skills={match.additional_skills} />
        </div>
        {alternatives.length > 0 && (
          <p className="text-xs text-slate-500 sm:col-span-2">
            {alternatives.map(([req, skill]) => `“${req}” satisfied by ${skill}`).join(' · ')}
          </p>
        )}
      </div>
    </Card>
  )
}

function ExperienceCard({ match, candidate }) {
  const status = EXPERIENCE_STATUS[match.experience_status] || EXPERIENCE_STATUS.unknown
  const rows = [
    ['Required by the job', match.required_experience === null ? 'No requirement' : formatYears(match.required_experience)],
    ['Relevant experience', formatYears(match.relevant_experience)],
    ['Total experience', formatYears(candidate.total_experience)],
    ['Internships (not counted)', candidate.internship_experience ? formatYears(candidate.internship_experience) : 'None listed'],
  ]
  return (
    <Card>
      <CardHeader
        icon={BriefcaseBusiness}
        title="Experience comparison"
        action={<Badge className={status.badge}>{status.label}</Badge>}
      />
      <dl className="grid grid-cols-2 gap-px bg-slate-100 sm:grid-cols-4">
        {rows.map(([label, value]) => (
          <div key={label} className="bg-white px-5 py-4">
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="mt-1 text-lg font-semibold tabular-nums text-navy-900">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="px-5 py-4 text-sm text-slate-600">
        <p>Experience score: <span className="font-semibold text-slate-900">{formatScore(match.experience_score)}</span></p>
        {match.experience_method === 'estimated_from_total' && <p className="mt-1">No dated jobs in the resume; estimated from the total experience the candidate states.</p>}
        {match.relevant_experience_entries.length > 0 && (
          <>
            <p className="mt-2 text-xs font-medium uppercase tracking-wide text-slate-500">Counted as relevant</p>
            <ul className="mt-1 list-disc pl-5">{match.relevant_experience_entries.map((e) => <li key={e}>{e}</li>)}</ul>
          </>
        )}
      </div>
    </Card>
  )
}

function ProfileSection({ icon, title, children }) {
  return (
    <Card>
      <CardHeader icon={icon} title={title} />
      <div className="px-5 py-4 text-sm text-slate-700">{children}</div>
    </Card>
  )
}

export default function CandidateDetailPage() {
  const { candidateId, jobId } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const analysisId = params.get('analysisId') || ''
  const { data, loading, error, reload } = useApi(() => candidatesApi.analysis(candidateId, jobId, analysisId), [candidateId, jobId, analysisId])
  const backUrl = `/rankings?jobId=${jobId}${analysisId ? `&analysisId=${analysisId}` : ''}`

  const deleteCandidate = async () => {
    setDeleting(true)
    try {
      await candidatesApi.remove(candidateId)
      toast.success('Candidate data deleted.')
      navigate(backUrl)
    } catch (err) {
      toast.error(getErrorMessage(err))
      setDeleting(false)
    }
  }

  if (loading && !data) return <Spinner label="Loading candidate analysis…" />
  if (error && !data) return <><ButtonLink to={backUrl} variant="ghost" icon={ArrowLeft} className="mb-4">Back to rankings</ButtonLink><ErrorState message={error} onRetry={reload} /></>

  const { candidate, job, analysis, match } = data
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 print:hidden">
        <ButtonLink to={backUrl} variant="ghost" icon={ArrowLeft}>Back to rankings</ButtonLink>
        <div className="flex flex-wrap gap-2">
          <Button variant="dangerGhost" icon={Trash2} onClick={() => setConfirmDelete(true)}>Delete candidate data</Button>
          <Button variant="secondary" icon={Printer} onClick={() => window.print()}>Print / save as PDF</Button>
        </div>
      </div>
      <ConfirmDialog
        open={confirmDelete}
        title="Delete candidate data?"
        message={`All extracted resume data and every analysis result for ${candidate.name || 'this candidate'} will be permanently deleted (for example, after a data-removal request). Other candidates' results are not affected.`}
        confirmLabel="Delete permanently"
        danger
        loading={deleting}
        onConfirm={deleteCandidate}
        onCancel={() => setConfirmDelete(false)}
      />

      <Card className="mb-6 p-5">
        <div className="flex flex-wrap items-center gap-6">
          <ScoreRing score={match.final_score} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold text-navy-900">{orNotFound(candidate.name)}</h1>
              <ScoreBadge score={match.final_score} />
              <Badge>Rank #{match.rank} of {match.total_candidates}</Badge>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              {job.job_title} · analysed {formatDateTime(analysis.created_at)}
            </p>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-600">
              <span className="inline-flex items-center gap-1.5"><Mail className="size-4 text-slate-400" aria-hidden="true" />{orNotFound(candidate.email)}</span>
              <span className="inline-flex items-center gap-1.5"><Phone className="size-4 text-slate-400" aria-hidden="true" />{orNotFound(candidate.phone)}</span>
              <span className="inline-flex items-center gap-1.5"><FileText className="size-4 text-slate-400" aria-hidden="true" />{candidate.resume_filename}</span>
            </div>
          </div>
        </div>
        {match.status === 'incomplete' && (
          <div className="mt-4">
            <Notice tone="warning" title="Score based on partial information">
              {match.missing_components.join(' and ')} could not be calculated, so the overall score uses the remaining parts only.
            </Notice>
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-3">
          <Card>
            <CardHeader icon={MessageSquareText} title="Why this score?" />
            <p className="px-5 py-4 text-sm leading-relaxed text-slate-700">{match.explanation}</p>
          </Card>
          <ScoreBreakdown match={match} />
          <SkillsCard match={match} />
          <ExperienceCard match={match} candidate={candidate} />
        </div>

        <div className="space-y-6 lg:col-span-2">
          <InterviewChecklist match={match} candidate={candidate} />

          <ProfileSection icon={BriefcaseBusiness} title="Work experience">
            {candidate.experience.length ? (
              <ol className="space-y-4">
                {candidate.experience.map((entry, index) => (
                  <li key={index} className="border-l-2 border-brand-100 pl-3">
                    <p className="font-medium text-slate-900">{entry.title || entry.heading}</p>
                    {entry.company && <p className="text-slate-600">{entry.company}</p>}
                    <p className="text-xs text-slate-500">
                      {entry.start ? `${entry.start} – ${entry.end}` : 'Dates not stated'}
                      {entry.months ? ` · ${formatYears(entry.months / 12)}` : ''}
                      {entry.is_internship && ' · Internship'}
                    </p>
                    {entry.skills.length > 0 && <div className="mt-1.5"><SkillChips skills={entry.skills} limit={6} /></div>}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-slate-500">
                {candidate.is_fresher ? 'Fresher: no professional work experience listed.' : 'No dated work experience found in the resume.'}
              </p>
            )}
          </ProfileSection>

          <ProfileSection icon={GraduationCap} title="Education">
            {candidate.education.length ? (
              <ul className="space-y-1.5">{candidate.education.map((e) => <li key={e}>{e}</li>)}</ul>
            ) : <p className="text-slate-500">Not found</p>}
            {job.education_requirements && <p className="mt-3 text-xs text-slate-500">Job asks for: {job.education_requirements}</p>}
          </ProfileSection>

          <ProfileSection icon={Award} title="Certifications">
            {candidate.certifications.length ? (
              <ul className="list-disc space-y-1 pl-5">{candidate.certifications.map((c) => <li key={c}>{c}</li>)}</ul>
            ) : <p className="text-slate-500">None listed</p>}
          </ProfileSection>

          {candidate.projects.length > 0 && (
            <ProfileSection icon={FolderGit2} title="Projects">
              <ul className="space-y-3">
                {candidate.projects.map((p) => (
                  <li key={p.title}>
                    <p className="font-medium text-slate-900">{p.title}</p>
                    {p.description && <p className="text-slate-600">{p.description}</p>}
                  </li>
                ))}
              </ul>
            </ProfileSection>
          )}

          {(candidate.links.length > 0 || candidate.parse_warnings.length > 0) && (
            <ProfileSection icon={Link2} title="Other details">
              {candidate.links.length > 0 && <ul className="mb-3 space-y-1">{candidate.links.map((l) => <li key={l} className="break-all">{l}</li>)}</ul>}
              {candidate.parse_warnings.length > 0 && (
                <>
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Resume reading notes</p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-5 text-slate-600">{candidate.parse_warnings.map((w) => <li key={w}>{w}</li>)}</ul>
                </>
              )}
            </ProfileSection>
          )}
        </div>
      </div>

      <p className="mt-6 text-xs text-slate-500">
        This analysis supports, but does not replace, human judgement. Candidates are never rejected automatically, and
        personal characteristics such as age, gender or religion are not used in scoring.
      </p>
    </>
  )
}
