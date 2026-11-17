/**
 * Sign-in page. While no account exists yet, it shows a one-time form to create the admin
 * account instead (the admin then adds the other HRs from Settings; there is no public sign-up).
 */
import { KeyRound, Loader2, LogIn, MousePointerClick, ShieldCheck, Sparkles, UserPlus } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Button, ErrorState, Field, Notice, inputClass } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { authApi, getErrorMessage } from '../services/api'

// Optional demo sign-in shown on the login page. Configured in frontend/.env; remove to hide.
// It should be a regular HR account: data isolation keeps it away from everyone else's candidates.
const DEMO = {
  email: import.meta.env.VITE_DEMO_EMAIL || '',
  password: import.meta.env.VITE_DEMO_PASSWORD || '',
}

function DemoAccountBox({ onUse }) {
  return (
    <div className="mt-6 rounded-xl border border-brand-100 bg-brand-50 p-4" aria-label="Demo account">
      <p className="text-sm font-semibold text-navy-900">Demo account</p>
      <p className="mt-0.5 text-xs text-slate-600">Try TalentMatch AI with a sample recruiter account.</p>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-slate-500">Email</dt>
        <dd className="font-mono text-slate-900">{DEMO.email}</dd>
        <dt className="text-slate-500">Password</dt>
        <dd className="font-mono text-slate-900">{DEMO.password}</dd>
      </dl>
      <button
        type="button"
        onClick={onUse}
        className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline"
      >
        <MousePointerClick className="size-4" aria-hidden="true" /> Use demo account
      </button>
    </div>
  )
}

function BrandPanel() {
  return (
    <div className="hidden flex-col justify-between bg-navy-900 p-10 text-white lg:flex">
      <div className="flex items-center gap-2.5">
        <div className="flex size-10 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-accent-600">
          <Sparkles className="size-5" aria-hidden="true" />
        </div>
        <span className="text-lg font-bold">TalentMatch AI</span>
      </div>
      <div>
        <h2 className="text-3xl font-bold leading-tight">Intelligent Resume Screening.<br />Smarter Hiring Decisions.</h2>
        <p className="mt-4 max-w-md text-brand-100/80">
          Rank candidates against your job descriptions with explainable AI scores, then decide with confidence.
        </p>
      </div>
      <p className="flex items-center gap-2 text-sm text-brand-100/70">
        <ShieldCheck className="size-4" aria-hidden="true" /> Each recruiter only sees their own jobs and candidates.
      </p>
    </div>
  )
}

export default function LoginPage() {
  const auth = useAuth()
  const location = useLocation()
  const setup = useApi(() => authApi.setupStatus(), [])
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (auth.status === 'signed-in') return <Navigate to={location.state?.from || '/'} replace />

  const needsSetup = setup.data?.needs_setup
  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (needsSetup && password !== confirm) {
      setError('The two passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      if (needsSetup) await auth.setupAdmin(fullName, email, password)
      else await auth.login(email, password)
    } catch (err) {
      setError(getErrorMessage(err))
      setSubmitting(false)
    }
  }

  return (
    <div className="grid min-h-screen bg-slate-50 lg:grid-cols-2">
      <BrandPanel />
      <main className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <div className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-accent-600">
              <Sparkles className="size-5 text-white" aria-hidden="true" />
            </div>
            <span className="text-lg font-bold text-navy-900">TalentMatch AI</span>
          </div>

          {setup.loading && !setup.data ? (
            <p className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="size-4 animate-spin" /> Connecting…</p>
          ) : setup.error ? (
            <ErrorState message={setup.error} onRetry={setup.reload} />
          ) : (
            <>
              <h1 className="text-2xl font-bold text-navy-900">{needsSetup ? 'Create the admin account' : 'Sign in'}</h1>
              <p className="mt-1 text-sm text-slate-500">
                {needsSetup
                  ? 'First-time setup. This account can add the other HR accounts. Any existing data is assigned to it.'
                  : 'Use the account your admin created for you.'}
              </p>
              {auth.notice && <div className="mt-4"><Notice tone="warning">{auth.notice}</Notice></div>}
              <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
                {needsSetup && (
                  <Field label="Full name" required>
                    {(id) => <input id={id} className={inputClass} value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" required />}
                  </Field>
                )}
                <Field label="Email" required>
                  {(id) => <input id={id} type="email" className={inputClass} value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />}
                </Field>
                <Field label="Password" required hint={needsSetup ? 'At least 8 characters, with a letter and a number.' : undefined}>
                  {(id) => (
                    <input id={id} type="password" className={inputClass} value={password} onChange={(e) => setPassword(e.target.value)}
                      autoComplete={needsSetup ? 'new-password' : 'current-password'} required />
                  )}
                </Field>
                {needsSetup && (
                  <Field label="Confirm password" required>
                    {(id) => <input id={id} type="password" className={inputClass} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" required />}
                  </Field>
                )}
                {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{error}</p>}
                <Button type="submit" className="w-full" size="lg" loading={submitting} icon={needsSetup ? UserPlus : LogIn}
                  disabled={!email || !password || (needsSetup && (!fullName || !confirm))}>
                  {needsSetup ? 'Create admin account' : 'Sign in'}
                </Button>
              </form>
              {!needsSetup && DEMO.email && DEMO.password && (
                <DemoAccountBox
                  onUse={() => {
                    setEmail(DEMO.email)
                    setPassword(DEMO.password)
                    setError('')
                  }}
                />
              )}
              {!needsSetup && (
                <p className="mt-6 flex items-start gap-2 text-xs text-slate-500">
                  <KeyRound className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                  Forgot your password? Ask your admin to reset it in Settings → Team accounts.
                </p>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  )
}
