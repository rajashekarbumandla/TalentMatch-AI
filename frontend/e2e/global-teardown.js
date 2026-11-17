/** After the browser tests: delete every account the tests created, together with all of its data. */
import fs from 'node:fs'
import { ACCOUNTS_FILE, AUTH_DIR, manage } from './global-setup.js'

export default async function globalTeardown() {
  const accounts = fs.existsSync(ACCOUNTS_FILE) ? JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf8')) : []
  for (const email of accounts) {
    try {
      process.stdout.write(manage('delete-user', '--email', email))
    } catch {
      /* already gone */
    }
  }
  fs.rmSync(AUTH_DIR, { recursive: true, force: true })
}
