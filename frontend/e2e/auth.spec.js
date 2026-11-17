/**
 * Login and HR accounts: sign-in, protected pages, admin creating an HR account,
 * each HR seeing only their own data, and disabling an account (immediate sign-out).
 */
import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { AUTH_DIR, rememberAccount } from './global-setup.js'

const admin = () => JSON.parse(fs.readFileSync(path.join(AUTH_DIR, 'admin.json'), 'utf8'))

test.describe('signed out', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('demo account details are shown and "Use demo account" signs in', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible() // wait until the page has loaded
    const demo = page.getByLabel('Demo account')
    test.skip(!(await demo.isVisible().catch(() => false)), 'No demo account configured in frontend/.env')
    const email = (await demo.locator('dd').first().textContent()).trim()
    await demo.getByRole('button', { name: 'Use demo account' }).click()
    await expect(page.getByLabel('Email')).toHaveValue(email)
    await expect(page.getByLabel('Password')).not.toHaveValue('')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('button', { name: /Account menu for/ })).toBeVisible()
    await expect(page.getByText('HR recruiter')).toBeVisible() // the demo account is not an admin
  })

  test('protected pages redirect to sign-in, wrong passwords are rejected, then sign-in returns to the page', async ({ page }) => {
    await page.goto('/rankings')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()

    await page.getByLabel('Email').fill(admin().email)
    await page.getByLabel('Password').fill('WrongPassword1')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('alert')).toHaveText('Invalid email or password.')

    await page.getByLabel('Password').fill(admin().password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/rankings$/)
    await expect(page.getByRole('button', { name: `Account menu for ${admin().name}` })).toBeVisible()
  })
})

test('admin adds an HR account; the HR only sees their own data; disabling signs them out', async ({ page, browser }) => {
  const hr = { name: 'E2E Recruiter', email: `e2e-hr-${Date.now()}@example.com`, password: 'TempPass123' }
  rememberAccount(hr.email) // deleted (with its data) after the tests

  await test.step('Admin creates the account in Settings', async () => {
    await page.goto('/settings')
    await expect(page.getByRole('heading', { name: 'Team accounts' })).toBeVisible()
    await page.getByRole('button', { name: 'Add HR account' }).click()
    const dialog = page.getByRole('dialog', { name: 'Add HR account' })
    await dialog.getByLabel('Full name').fill(hr.name)
    await dialog.getByLabel('Work email').fill(hr.email)
    await dialog.getByLabel('Temporary password').fill(hr.password)
    await dialog.getByRole('button', { name: 'Create account' }).click()
    await expect(page.getByText(`Account created for ${hr.name}.`)).toBeVisible()
    await expect(page.getByRole('cell', { name: new RegExp(hr.email) })).toBeVisible()
  })

  const hrContext = await browser.newContext({ storageState: { cookies: [], origins: [] } })
  const hrPage = await hrContext.newPage()

  await test.step('The new HR signs in and sees an empty workspace', async () => {
    await hrPage.goto('/login')
    await hrPage.getByLabel('Email').fill(hr.email)
    await hrPage.getByLabel('Password').fill(hr.password)
    await hrPage.getByRole('button', { name: 'Sign in' }).click()
    await expect(hrPage.getByRole('heading', { name: 'Welcome to TalentMatch AI' })).toBeVisible()
    await expect(hrPage.getByText('No analyses yet')).toBeVisible()
    await hrPage.goto('/settings')
    await expect(hrPage.getByRole('heading', { name: 'My account' })).toBeVisible()
    await expect(hrPage.getByRole('heading', { name: 'Team accounts' })).toHaveCount(0) // not an admin
    await hrPage.goto('/jobs')
    await expect(hrPage.getByText('No job descriptions yet')).toBeVisible()
  })

  await test.step('Admin disables the account; the HR is signed out on their next action', async () => {
    await page.reload()
    const row = page.getByRole('row', { name: new RegExp(hr.email) })
    await row.getByRole('button', { name: 'Disable' }).click()
    await page.getByRole('button', { name: 'Disable account' }).click()
    await expect(page.getByText(`${hr.name}'s account was disabled.`)).toBeVisible()
    await expect(row.getByText('Disabled')).toBeVisible()

    await hrPage.goto('/history')
    await expect(hrPage).toHaveURL(/\/login$/)
    await expect(hrPage.getByText(/session has expired or your account was changed/)).toBeVisible()
    await hrPage.getByLabel('Email').fill(hr.email)
    await hrPage.getByLabel('Password').fill(hr.password)
    await hrPage.getByRole('button', { name: 'Sign in' }).click()
    await expect(hrPage.getByRole('alert')).toContainText('disabled')
  })
  await hrContext.close()

  await test.step('Admin signs out', async () => {
    await page.getByRole('button', { name: `Account menu for ${admin().name}` }).click()
    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page).toHaveURL(/\/login$/)
  })
})
