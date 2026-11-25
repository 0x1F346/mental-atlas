import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const EMAIL = process.env.ATLAS_SEED_USER_EMAIL ?? 'owner@example.com'
export const PASSWORD = process.env.ATLAS_SEED_USER_PASSWORD ?? 'atlas-dev'
export const TITLE_PREFIX = 'E2E '

/** Wait for the API behind the web server's proxy. */
export async function waitForApi(request: APIRequestContext) {
  await expect
    .poll(async () => (await request.get('/api/v1/health').catch(() => null))?.status() ?? 0, {
      timeout: 60_000,
    })
    .toBe(200)
}

/** Retract sources left behind by an earlier run, so the duplicate check does not trip. */
export async function removeTestSources(request: APIRequestContext) {
  const login = await request.post('/api/v1/auth/login', { data: { email: EMAIL, password: PASSWORD } })
  expect(login.ok()).toBeTruthy()
  const headers = { 'x-csrf-token': (await login.json()).csrf_token as string }
  const sources = (await (await request.get('/api/v1/sources')).json()) as { id: string; title: string }[]
  for (const source of sources.filter((row) => row.title.startsWith(TITLE_PREFIX))) {
    await request.delete(`/api/v1/sources/${source.id}`, { headers })
  }
  await request.post('/api/v1/auth/logout', { headers })
}

export async function signIn(page: Page) {
  await page.goto('/')
  await page.getByLabel('Email').fill(EMAIL)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('link', { name: 'Sources' })).toBeVisible()
}
