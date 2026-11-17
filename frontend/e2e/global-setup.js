/**
 * Before the browser tests: create a temporary admin account (through the server's
 * account-maintenance command), sign in once through the API, and save the session so
 * every test starts logged in. global-teardown.js deletes the account, and with it
 * (ON DELETE CASCADE) every job, resume and analysis the tests created.
 */
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

export const AUTH_DIR = path.join(import.meta.dirname, '.auth')
export const STATE_FILE = path.join(AUTH_DIR, 'state.json')
export const ACCOUNTS_FILE = path.join(AUTH_DIR, 'accounts.json')
export const BACKEND_DIR = path.resolve(import.meta.dirname, '../../backend')
export const PYTHON = path.join(BACKEND_DIR, '.venv', 'Scripts', 'python.exe')

export function manage(...args) {
  return execFileSync(PYTHON, ['-m', 'app.manage', ...args], { cwd: BACKEND_DIR, encoding: 'utf8' })
}

export function rememberAccount(email) {
  const accounts = fs.existsSync(ACCOUNTS_FILE) ? JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf8')) : []
  fs.writeFileSync(ACCOUNTS_FILE, JSON.stringify([...new Set([...accounts, email])], null, 1))
}

export default async function globalSetup() {
  fs.mkdirSync(AUTH_DIR, { recursive: true })
  const admin = { email: `e2e-admin-${Date.now()}@example.com`, password: `E2eAdmin${Date.now() % 100000}`, name: 'E2E Admin' }
  manage('create-user', '--email', admin.email, '--name', admin.name, '--password', admin.password, '--admin')
  rememberAccount(admin.email)
  fs.writeFileSync(path.join(AUTH_DIR, 'admin.json'), JSON.stringify(admin))

  const response = await fetch('http://localhost:8000/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: admin.email, password: admin.password }),
  })
  if (!response.ok) throw new Error(`E2E admin login failed: ${response.status} ${await response.text()}`)
  const { access_token: token } = await response.json()
  fs.writeFileSync(STATE_FILE, JSON.stringify({
    cookies: [],
    origins: [{ origin: 'http://localhost:5173', localStorage: [{ name: 'talentmatch:token', value: token }] }],
  }))
}
