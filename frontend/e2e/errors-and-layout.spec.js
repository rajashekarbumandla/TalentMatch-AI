/** Error handling, input validation and phone-screen layout (no data is created). */
import { expect, test } from '@playwright/test'

test('shows a clear message and a retry button when the backend is unreachable', async ({ page }) => {
  await page.route('**/api/dashboard/stats', (route) => route.abort('connectionrefused'))
  await page.goto('/')
  await expect(page.getByText(/Cannot reach the TalentMatch AI server/)).toBeVisible()
  await page.unroute('**/api/dashboard/stats')
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByRole('heading', { name: /Dashboard|Welcome to TalentMatch AI/ })).toBeVisible()
})

test('shows the server validation message for an unusable JD file', async ({ page }) => {
  await page.goto('/analysis/new')
  await page.getByRole('radio', { name: 'Upload PDF / DOCX' }).click()
  // A file with a .pdf name but non-PDF content passes the browser check and is rejected by the server.
  await page.locator('input[type=file]').setInputFiles({ name: 'jd.pdf', mimeType: 'application/pdf', buffer: Buffer.from('not really a pdf') })
  await page.getByRole('button', { name: 'Extract requirements' }).click()
  await expect(page.getByText('The file has a .pdf extension but is not a valid PDF.')).toBeVisible()
})

test('blocks a too-short job description and unsupported files before sending', async ({ page }) => {
  await page.goto('/analysis/new')
  await page.getByRole('textbox', { name: 'Job description' }).fill('Python dev')
  await expect(page.getByRole('button', { name: 'Extract requirements' })).toBeDisabled()
  await page.getByRole('radio', { name: 'Upload PDF / DOCX' }).click()
  await page.locator('input[type=file]').setInputFiles({ name: 'jd.txt', mimeType: 'text/plain', buffer: Buffer.from('text') })
  await expect(page.getByText(/Unsupported format/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Extract requirements' })).toBeDisabled()
})

test('unknown pages show a friendly 404', async ({ page }) => {
  await page.goto('/does-not-exist')
  await expect(page.getByText('Page not found')).toBeVisible()
  await page.getByRole('link', { name: 'Go to dashboard' }).click()
  await expect(page).toHaveURL('/')
})

test.describe('phone screen (390 × 844)', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  for (const route of ['/', '/analysis/new', '/rankings', '/jobs', '/history', '/settings']) {
    test(`${route} fits the screen and the menu works`, async ({ page }) => {
      await page.goto(route)
      await expect(page.locator('main')).not.toContainText('Loading…', { timeout: 30_000 })
      const { scrollWidth, clientWidth } = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }))
      expect(scrollWidth, `page is ${scrollWidth}px wide on a ${clientWidth}px screen`).toBeLessThanOrEqual(clientWidth)
      await page.getByRole('button', { name: 'Open menu' }).click()
      await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Settings' })).toBeVisible()
    })
  }
})
