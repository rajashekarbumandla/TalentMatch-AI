/** System status and a transparent explanation of how scores are calculated (read-only; configured in backend/.env). */
import { Calculator, CheckCircle2, Cpu, Database, Server, ShieldCheck, XCircle } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { MyAccountCard, TeamAccountsCard } from '../components/AccountSettings'
import { Card, CardHeader, ErrorState, Spinner } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { API_BASE_URL, systemApi } from '../services/api'

function StatusRow({ icon: Icon, label, ok, detail }) {
  return (
    <li className="flex items-start gap-3 px-5 py-3">
      <Icon className="mt-0.5 size-5 text-slate-400" aria-hidden="true" />
      <div className="flex-1">
        <p className="text-sm font-medium text-slate-900">{label}</p>
        <p className="text-xs text-slate-500">{detail}</p>
      </div>
      {ok ? (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700"><CheckCircle2 className="size-4" aria-hidden="true" /> OK</span>
      ) : (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700"><XCircle className="size-4" aria-hidden="true" /> Problem</span>
      )}
    </li>
  )
}

export default function SettingsPage() {
  const { isAdmin } = useAuth()
  const health = useApi(() => systemApi.health(), [])
  const settings = useApi(() => systemApi.settings(), [])
  const s = settings.data
  const pct = (value) => `${Math.round(value * 100)}%`

  return (
    <>
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-navy-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">Your account, system status and scoring method. Scoring values are configured by an administrator in the backend environment file.</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <MyAccountCard />
        {isAdmin && <TeamAccountsCard />}
        <Card>
          <CardHeader icon={Server} title="System status" />
          {health.loading && !health.data ? (
            <Spinner />
          ) : health.error ? (
            <div className="p-5"><ErrorState message={health.error} onRetry={health.reload} /></div>
          ) : (
            <ul className="divide-y divide-slate-100">
              <StatusRow icon={Server} label="Backend API" ok detail={`${health.data.service} v${health.data.version} · ${API_BASE_URL}`} />
              <StatusRow icon={Database} label="Supabase database" ok={health.data.database.connected} detail={health.data.database.message} />
              <StatusRow
                icon={Cpu}
                label="AI model"
                ok={health.data.model.loaded || !health.data.model.error}
                detail={health.data.model.error || `${health.data.model.name} ${health.data.model.loaded ? 'loaded' : 'loads on first analysis'}`}
              />
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader icon={Calculator} title="How the match score is calculated" />
          {!s ? (
            settings.error ? <div className="p-5"><ErrorState message={settings.error} onRetry={settings.reload} /></div> : <Spinner />
          ) : (
            <div className="space-y-4 px-5 py-4 text-sm text-slate-700">
              <p className="rounded-lg bg-slate-50 px-3 py-2 font-mono text-xs text-slate-800">
                Final = {pct(s.weights.semantic)} × Semantic + {pct(s.weights.skills)} × Skills + {pct(s.weights.experience)} × Experience
              </p>
              <ul className="space-y-2">
                <li><strong>Semantic similarity ({pct(s.weights.semantic)}):</strong> meaning-based comparison of resume and JD using {s.semantic_model}. Cosine similarity {s.semantic_cosine_floor} → 0 points, {s.semantic_cosine_ceil} → 100 points.</li>
                <li><strong>Skills ({pct(s.weights.skills)}):</strong> share of JD skills found. Required skills weigh {s.required_skill_weight}, preferred skills {s.preferred_skill_weight}.</li>
                <li><strong>Experience ({pct(s.weights.experience)}):</strong> relevant years ÷ required years, capped at 100. Overlapping jobs are counted once; internships are excluded.</li>
              </ul>
              <p>When a part cannot be calculated (e.g. experience dates missing), the others share its weight and the result is marked <em>Verify</em>.</p>
              <p>Dashboard “high match” = score of {s.high_match_threshold} or more.</p>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader icon={ShieldCheck} title="Uploads & privacy" />
          {s && (
            <ul className="list-disc space-y-1.5 py-4 pl-10 pr-5 text-sm text-slate-700">
              <li>Accepted formats: {s.allowed_extensions.join(', ')} · maximum {s.max_file_size_mb} MB per file · {s.max_files_per_batch} files per batch.</li>
              <li>Original resume files are not stored; only extracted text and candidate details are saved.</li>
              <li>Age, gender, religion, ethnicity and other personal characteristics are never used for scoring.</li>
              <li>Candidates are never rejected automatically. Scores support, not replace, human review.</li>
            </ul>
          )}
        </Card>
      </div>
    </>
  )
}
