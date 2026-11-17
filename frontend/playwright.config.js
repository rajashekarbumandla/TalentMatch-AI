/**
 * End-to-end tests: a real browser (the installed Microsoft Edge) drives the React app,
 * which talks to the real FastAPI backend and Supabase database.
 *
 *   npm run test:e2e          (starts both servers automatically if they are not running)
 *
 * Tests clean up every record they create.
 */
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 300_000, // the full workflow uploads 12 resumes and runs an AI analysis
  expect: { timeout: 30_000 },
  workers: 1, // tests share one database, so run them one at a time
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'e2e-report' }]],
  // A temporary admin account is created before the tests and deleted (with all its data) afterwards.
  globalSetup: './e2e/global-setup.js',
  globalTeardown: './e2e/global-teardown.js',
  use: {
    baseURL: 'http://localhost:5173',
    storageState: './e2e/.auth/state.json', // every test starts signed in as that admin
    channel: 'msedge', // use the Edge already installed on Windows (no browser download needed)
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: '.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000',
      cwd: '../backend',
      url: 'http://localhost:8000/api/health',
      reuseExistingServer: true,
      timeout: 180_000,
    },
    {
      command: 'npm run dev -- --port 5173 --strictPort',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
