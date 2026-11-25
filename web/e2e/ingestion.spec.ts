import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import { removeTestSources, signIn, TITLE_PREFIX, waitForApi } from './helpers.ts'

const here = path.dirname(fileURLToPath(import.meta.url))
const RECORDING = path.resolve(here, '../../evals/fixtures/synthetic/audio/two_voice_session.m4a')

test.beforeEach(async ({ request }) => {
  await waitForApi(request)
  await removeTestSources(request)
})

test.afterEach(async ({ request }) => {
  await removeTestSources(request)
})

test('an invented two-voice recording reaches a transcript with correct roles', async ({ page }) => {
  await signIn(page)
  await page.getByRole('link', { name: 'Sources' }).click()
  await page.getByLabel('Title').fill(`${TITLE_PREFIX}two-voice session`)
  await page.getByLabel('Audio or video file').setInputFiles(RECORDING)
  await page.getByRole('button', { name: 'Add' }).click()

  await expect(page.getByTestId('source-status')).toHaveText('Ready', { timeout: 60_000 })
  const transcript = page.getByRole('region', { name: 'Transcript' })
  const segments = transcript.getByRole('listitem')
  await expect(segments).toHaveCount(6)
  await expect(segments.nth(0)).toContainText('Therapist')
  await expect(segments.nth(0)).toContainText('So what has been on your mind')
  await expect(segments.nth(1)).toContainText('Me')
  await expect(segments.nth(1)).toContainText('I felt a lot of dread')
})

test('pasted text reaches segments', async ({ page }) => {
  await signIn(page)
  await page.getByRole('link', { name: 'Sources' }).click()
  await page.getByRole('radio', { name: 'Text' }).check()
  await page.getByLabel('Title').fill(`${TITLE_PREFIX}journal entry`)
  await page
    .getByRole('textbox', { name: 'Text' })
    .fill('I felt dread before the review.\n\nThen I went for a walk and it eased.')
  await page.getByRole('button', { name: 'Add' }).click()

  await expect(page.getByTestId('source-status')).toHaveText('Ready', { timeout: 60_000 })
  const segments = page.getByRole('region', { name: 'Transcript' }).getByRole('listitem')
  await expect(segments).toHaveCount(2)
  await expect(segments.nth(1)).toContainText('Then I went for a walk')
})
