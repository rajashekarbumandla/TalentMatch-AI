/** "My account" (everyone) and "Team accounts" (admins) sections of the Settings page. */
import { KeyRound, Lock, Power, ShieldCheck, UserPlus, Users } from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { useApi } from '../hooks/useApi'
import { authApi, getErrorMessage, setToken, usersApi } from '../services/api'
import { formatDateTime } from '../utils/format'
import { useToast } from './Toast'
import { Badge, Button, Card, CardHeader, ConfirmDialog, ErrorState, Field, Modal, Notice, Spinner, inputClass } from './ui'

const PASSWORD_HINT = 'At least 8 characters, with a letter and a number.'

export function MyAccountCard() {
  const { user, logout } = useAuth()
  const toast = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const changePassword = async (event) => {
    event.preventDefault()
    setError('')
    if (next !== confirm) return setError('The new passwords do not match.')
    setSaving(true)
    try {
      await authApi.changePassword(current, next)
      // The server invalidates every existing session, including this one: sign in again with the new password.
      setToken(null)
      toast.success('Password changed. Please sign in with your new password.')
      logout()
    } catch (err) {
      setError(getErrorMessage(err))
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader icon={ShieldCheck} title="My account" />
      <dl className="grid gap-3 px-5 py-4 text-sm sm:grid-cols-2">
        <div><dt className="text-xs text-slate-500">Name</dt><dd className="font-medium text-slate-900">{user.full_name}</dd></div>
        <div><dt className="text-xs text-slate-500">Email</dt><dd className="font-medium text-slate-900">{user.email}</dd></div>
        <div><dt className="text-xs text-slate-500">Role</dt><dd><Badge>{user.role === 'admin' ? 'Admin' : 'HR recruiter'}</Badge></dd></div>
        <div><dt className="text-xs text-slate-500">Last sign-in</dt><dd className="text-slate-700">{formatDateTime(user.last_login_at)}</dd></div>
      </dl>
      <form onSubmit={changePassword} className="space-y-3 border-t border-slate-100 px-5 py-4">
        <p className="flex items-center gap-2 text-sm font-medium text-slate-900"><Lock className="size-4" aria-hidden="true" /> Change password</p>
        <Field label="Current password">
          {(id) => <input id={id} type="password" className={inputClass} value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />}
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="New password" hint={PASSWORD_HINT}>
            {(id) => <input id={id} type="password" className={inputClass} value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />}
          </Field>
          <Field label="Confirm new password">
            {(id) => <input id={id} type="password" className={inputClass} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />}
          </Field>
        </div>
        {error && <p className="text-sm text-red-600" role="alert">{error}</p>}
        <div className="flex justify-end">
          <Button type="submit" icon={KeyRound} loading={saving} disabled={!current || !next || !confirm}>Change password</Button>
        </div>
      </form>
    </Card>
  )
}

function AddAccountModal({ open, onClose, onCreated }) {
  const toast = useToast()
  const [form, setForm] = useState({ full_name: '', email: '', password: '', role: 'hr' })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  const submit = async () => {
    setError('')
    setSaving(true)
    try {
      const account = await usersApi.create(form)
      toast.success(`Account created for ${account.full_name}. Share the temporary password with them securely.`)
      setForm({ full_name: '', email: '', password: '', role: 'hr' })
      onCreated()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add HR account"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button icon={UserPlus} onClick={submit} loading={saving}>Create account</Button></>}
    >
      <div className="space-y-3">
        <Field label="Full name" required>{(id) => <input id={id} className={inputClass} value={form.full_name} onChange={set('full_name')} />}</Field>
        <Field label="Work email" required>{(id) => <input id={id} type="email" className={inputClass} value={form.email} onChange={set('email')} />}</Field>
        <Field label="Temporary password" required hint={`${PASSWORD_HINT} They can change it after signing in.`}>
          {(id) => <input id={id} type="text" className={inputClass} value={form.password} onChange={set('password')} autoComplete="off" />}
        </Field>
        <Field label="Role">
          {(id) => (
            <select id={id} className={inputClass} value={form.role} onChange={set('role')}>
              <option value="hr">HR recruiter: screens candidates</option>
              <option value="admin">Admin: also manages accounts</option>
            </select>
          )}
        </Field>
        <p className="text-xs text-slate-500">Each account only sees its own jobs, candidates and analyses.</p>
        {error && <p className="text-sm text-red-600" role="alert">{error}</p>}
      </div>
    </Modal>
  )
}

function ResetPasswordModal({ account, onClose }) {
  const toast = useToast()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async () => {
    setError('')
    setSaving(true)
    try {
      await usersApi.resetPassword(account.id, password)
      toast.success(`Password reset for ${account.full_name}. They have been signed out everywhere.`)
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }
  return (
    <Modal
      open={Boolean(account)}
      onClose={onClose}
      title={`Reset password: ${account?.full_name ?? ''}`}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button icon={KeyRound} onClick={submit} loading={saving} disabled={!password}>Reset password</Button></>}
    >
      <Field label="New temporary password" hint={PASSWORD_HINT}>
        {(id) => <input id={id} type="text" className={inputClass} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="off" />}
      </Field>
      {error && <p className="mt-2 text-sm text-red-600" role="alert">{error}</p>}
    </Modal>
  )
}

export function TeamAccountsCard() {
  const { user: me } = useAuth()
  const toast = useToast()
  const { data: accounts, loading, error, reload } = useApi(() => usersApi.list(), [])
  const [adding, setAdding] = useState(false)
  const [resetting, setResetting] = useState(null)
  const [disabling, setDisabling] = useState(null)
  const [busy, setBusy] = useState(false)

  const update = async (account, changes, message) => {
    setBusy(true)
    try {
      await usersApi.update(account.id, changes)
      toast.success(message)
      setDisabling(null)
      reload()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="lg:col-span-2">
      <CardHeader
        icon={Users}
        title="Team accounts"
        description="Only admins see this. There is no public sign-up; add each recruiter here."
        action={<Button size="sm" icon={UserPlus} onClick={() => setAdding(true)}>Add HR account</Button>}
      />
      {loading && !accounts ? (
        <Spinner />
      ) : error && !accounts ? (
        <div className="p-5"><ErrorState message={error} onRetry={reload} /></div>
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-2.5 font-medium">Name</th>
                <th className="px-3 py-2.5 font-medium">Role</th>
                <th className="px-3 py-2.5 font-medium">Status</th>
                <th className="px-3 py-2.5 font-medium">Last sign-in</th>
                <th className="px-5 py-2.5 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {accounts.map((account) => {
                const isMe = account.id === me.id
                return (
                  <tr key={account.id}>
                    <td className="px-5 py-3">
                      <p className="font-medium text-slate-900">{account.full_name}{isMe && <span className="text-slate-400"> (you)</span>}</p>
                      <p className="text-xs text-slate-500">{account.email}</p>
                    </td>
                    <td className="px-3 py-3">
                      <select
                        className={`${inputClass} w-32 py-1 text-xs`}
                        value={account.role}
                        disabled={isMe || busy}
                        aria-label={`Role of ${account.full_name}`}
                        onChange={(e) => update(account, { role: e.target.value }, `${account.full_name} is now ${e.target.value === 'admin' ? 'an admin' : 'an HR recruiter'}.`)}
                      >
                        <option value="hr">HR recruiter</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-3 py-3">
                      {account.is_active
                        ? <Badge className="bg-emerald-50 text-emerald-800 ring-emerald-600/20">Active</Badge>
                        : <Badge className="bg-slate-100 text-slate-600 ring-slate-500/20">Disabled</Badge>}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-slate-600">{account.last_login_at ? formatDateTime(account.last_login_at) : 'Never'}</td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" icon={KeyRound} onClick={() => setResetting(account)}>Reset password</Button>
                        {!isMe && (account.is_active ? (
                          <Button size="sm" variant="dangerGhost" icon={Power} onClick={() => setDisabling(account)}>Disable</Button>
                        ) : (
                          <Button size="sm" variant="ghost" icon={Power} disabled={busy} onClick={() => update(account, { is_active: true }, `${account.full_name} can sign in again.`)}>Enable</Button>
                        ))}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="px-5 py-3">
        <Notice>Disabling an account signs that person out immediately and keeps all their data. Passwords are stored only as secure hashes and can never be viewed.</Notice>
      </div>
      <AddAccountModal open={adding} onClose={() => setAdding(false)} onCreated={reload} />
      <ResetPasswordModal key={resetting?.id} account={resetting} onClose={() => setResetting(null)} />
      <ConfirmDialog
        open={Boolean(disabling)}
        title="Disable account?"
        message={disabling ? `${disabling.full_name} will be signed out and won't be able to sign in. Their jobs and candidates are kept, and you can re-enable the account at any time.` : ''}
        confirmLabel="Disable account"
        danger
        loading={busy}
        onConfirm={() => update(disabling, { is_active: false }, `${disabling.full_name}'s account was disabled.`)}
        onCancel={() => setDisabling(null)}
      />
    </Card>
  )
}
