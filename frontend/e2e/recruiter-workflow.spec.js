/**
 * The complete recruiter journey through the real UI, backend and database:
 * JD -> review requirements -> upload 12 resumes (+1 invalid file) -> analyse -> ranking ->
 * search/filters -> candidate details -> CSV export -> dashboard -> edit job -> history ->
 * delete a candidate -> delete the job. Every record created here is removed at the end.
 */
import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const ROOT = path.resolve(import.meta.dirname, '../..')
const RESUMES = fs
  .readdirSync(path.join(ROOT, 'sample_resumes'))
  .filter((name) => /\.(pdf|docx)$/.test(name))
  .map((name) => path.join(ROOT, 'sample_resumes', name))
const JD_TEXT = fs.readFileSync(path.join(ROOT, 'sample_jds', '01_python_developer.txt'), 'utf8')
const TITLE = `E2E Python Developer ${Date.now()}`

/** Fails if the page is wider than the screen (horizontal scrolling on phones). */
async function expectNoHorizontalScroll(page, where) {
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(scrollWidth, `${where}: page is ${scrollWidth}px wide on a ${clientWidth}px screen`).toBeLessThanOrEqual(clientWidth)
}

// Everything created here belongs to the temporary E2E admin and is deleted with that
// account in global-teardown.js, even if the test fails half-way.
const created = { candidateIds: [] }

test('complete recruiter workflow', async ({ page }, testInfo) => {
  await test.step('1. Enter a job description and extract requirements', async () => {
    await page.goto('/analysis/new')
    await page.getByLabel('Job title').fill(TITLE)
    await page.getByRole('textbox', { name: 'Job description' }).fill(JD_TEXT)
    await page.getByRole('button', { name: 'Extract requirements' }).click()
    await expect(page.getByText('Review before saving')).toBeVisible()
    for (const skill of ['Python', 'FastAPI', 'SQL', 'REST APIs', 'Machine Learning', 'Docker']) {
      await expect(page.getByRole('button', { name: `Remove ${skill}`, exact: true })).toBeVisible()
    }
    await expect(page.getByLabel('Minimum experience (years)')).toHaveValue('3')
  })

  await test.step('2. Correct the requirements and save the job', async () => {
    await page.getByLabel('Preferred skills').fill('k8s')
    await page.getByLabel('Preferred skills').press('Enter')
    await page.getByRole('button', { name: 'Save job and continue' }).click()
    await expect(page.getByText(`"${TITLE}" saved.`)).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Upload candidate resumes' })).toBeVisible()
  })

  await test.step('3. Upload 12 resumes plus one invalid file', async () => {
    const invalid = testInfo.outputPath('notes.txt')
    fs.writeFileSync(invalid, 'not a resume')
    await page.locator('input[type=file]').setInputFiles([...RESUMES, invalid])
    await expect(page.getByText('13 files selected')).toBeVisible()
    await expect(page.getByText('12 ready')).toBeVisible()
    await expect(page.getByText('1 cannot be used')).toBeVisible()
    await page.getByRole('button', { name: 'Remove notes.txt' }).click()
    await expect(page.getByText('12 files selected')).toBeVisible()
  })

  await test.step('4. Run the analysis', async () => {
    const uploadResponse = page.waitForResponse((r) => r.url().includes('/api/resumes/upload'))
    await page.getByRole('button', { name: 'Analyse 12 resumes' }).click()
    const upload = await (await uploadResponse).json()
    created.candidateIds = upload.candidate_ids
    expect(upload.parsed).toBe(12)
    await expect(page.getByText(/Top match: (Priya Nair|Arjun Mehta)/)).toBeVisible({ timeout: 180_000 })
    await page.getByRole('button', { name: 'View candidate ranking' }).click()
  })

  await test.step('5. Review the ranking', async () => {
    await expect(page.getByText('Showing 12 of 12 candidates')).toBeVisible()
    await expect(page.getByText('Top match', { exact: true })).toBeVisible()
    const rows = page.locator('tbody tr')
    await expect(rows).toHaveCount(12)
    await expect(rows.first()).toContainText(/Priya Nair|Arjun Mehta/)
    await expect(rows.last()).toContainText('Fatima Sheikh')
    await expect(rows.first().locator('td').first()).toHaveText('1')
  })

  await test.step('6. Search, filter and open a candidate with missing contact details', async () => {
    await page.getByRole('radio', { name: 'Top 5' }).click()
    await expect(page.getByText('Showing 5 of 12 candidates')).toBeVisible()
    await page.getByRole('radio', { name: 'All' }).last().click()
    // ("neha" would also match "Sneha Kulkarni": search is a case-insensitive "contains" match.)
    await page.getByLabel('Search candidates by name or email').fill('patil')
    await expect(page.getByText('Showing 1 of 12 candidates')).toBeVisible()
    await expect(page.locator('tbody tr')).toContainText('Not found')
    await page.getByRole('link', { name: 'Details' }).click()
    await expect(page.getByRole('heading', { name: 'Neha Patil' })).toBeVisible()
    await expect(page.getByText('Contact details are incomplete in the resume.')).toBeVisible()
    await expect(page.getByText('Score breakdown')).toBeVisible()
    await expect(page.getByText(/estimated from the total experience stated in the resume/)).toBeVisible()
  })

  await test.step('7. Candidate details and ranking work on a phone screen', async () => {
    await page.setViewportSize({ width: 390, height: 844 })
    await expectNoHorizontalScroll(page, 'candidate details')
    await page.getByRole('link', { name: 'Back to rankings' }).click()
    await expect(page.getByText(/Showing \d+ of 12 candidates/)).toBeVisible()
    await expectNoHorizontalScroll(page, 'rankings')
    await page.setViewportSize({ width: 1440, height: 900 })
  })

  await test.step('8. Export the ranking as CSV', async () => {
    await page.getByLabel('Search candidates by name or email').fill('')
    await expect(page.getByText('Showing 12 of 12 candidates')).toBeVisible()
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Export CSV' }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toMatch(/^talentmatch_e2e_python_developer_\d+_\d{8}_\d{4}\.csv$/)
    const csv = fs.readFileSync(await download.path(), 'utf8')
    const lines = csv.trim().split(/\r?\n/)
    expect(lines[0].replace(/^\uFEFF/, '')).toMatch(/^Rank,Candidate Name,Email/)
    expect(lines).toHaveLength(13)
  })

  await test.step('9. Dashboard and history show the new analysis', async () => {
    await page.getByRole('link', { name: 'Dashboard' }).click()
    await expect(page.getByText(`Top candidates for ${TITLE}.`, { exact: false })).toBeVisible()
    await expect(page.getByRole('cell', { name: TITLE })).toBeVisible()
    await page.getByRole('link', { name: 'Analysis History' }).click()
    await expect(page.getByRole('cell', { name: TITLE })).toBeVisible()
  })

  await test.step('10. Edit the job requirements', async () => {
    await page.getByRole('link', { name: 'Job Descriptions' }).click()
    const card = page.locator('section', { has: page.getByRole('heading', { name: TITLE }) })
    await expect(card.getByText('Kubernetes')).toBeVisible() // "k8s" was normalised by the backend
    await card.getByRole('link', { name: 'Edit' }).click()
    await page.getByLabel('Minimum experience (years)').fill('5')
    await page.getByRole('button', { name: 'Save changes' }).click()
    await expect(page.getByText('Job description updated.')).toBeVisible()
    await expect(card.getByText('5 yrs+')).toBeVisible()
  })

  await test.step('11. Delete a candidate, then the job', async () => {
    const card = page.locator('section', { has: page.getByRole('heading', { name: TITLE }) })
    await card.getByRole('link', { name: 'View results' }).click()
    await page.getByLabel('Search candidates by name or email').fill('fatima')
    await expect(page.getByText('Showing 1 of 12 candidates')).toBeVisible() // wait for the debounced search
    await page.getByRole('link', { name: 'Details' }).click()
    await page.getByRole('button', { name: 'Delete candidate data' }).click()
    await page.getByRole('button', { name: 'Delete permanently' }).click()
    await expect(page.getByText('Candidate data deleted.')).toBeVisible()
    await page.getByLabel('Search candidates by name or email').fill('')
    await expect(page.getByText('Showing 11 of 11 candidates')).toBeVisible()

    await page.getByRole('link', { name: 'Job Descriptions' }).click()
    await page.locator('section', { has: page.getByRole('heading', { name: TITLE }) }).getByRole('button', { name: 'Delete' }).click()
    await page.getByRole('button', { name: 'Delete', exact: true }).last().click()
    await expect(page.getByText(`"${TITLE}" deleted.`)).toBeVisible()
    await expect(page.getByRole('heading', { name: TITLE })).toHaveCount(0)
  })
})
