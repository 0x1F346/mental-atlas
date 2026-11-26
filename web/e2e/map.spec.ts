import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import { removeTestSources, signIn, TITLE_PREFIX, waitForApi } from './helpers.ts'

const here = path.dirname(fileURLToPath(import.meta.url))
const fixture = JSON.parse(
  readFileSync(path.resolve(here, '../../evals/fixtures/synthetic/journal_one.transcript.json'), 'utf8'),
) as { paragraphs: string[] }

test.beforeEach(async ({ request }) => {
  await waitForApi(request)
  await removeTestSources(request)
})

test.afterEach(async ({ request }) => {
  await removeTestSources(request)
})

// M5-T5: sign in, upload fixture text, wait for ready, open the map, select a landmark, read a quote.
test('from uploaded text to a quote on the map', async ({ page }, testInfo) => {
  await signIn(page)
  await page.getByRole('link', { name: 'Sources' }).click()
  await page.getByRole('radio', { name: 'Text' }).check()
  await page.getByLabel('Title').fill(`${TITLE_PREFIX}journal on the map`)
  await page.getByRole('textbox', { name: 'Text' }).fill(fixture.paragraphs.join('\n\n'))
  await page.getByRole('button', { name: 'Add' }).click()
  await expect(page.getByTestId('source-status')).toHaveText('Ready', { timeout: 60_000 })

  await page.getByRole('link', { name: 'Open the map' }).click()
  // The map is a WebGL canvas; the same landmarks are mirrored as buttons for the keyboard.
  await expect(page.locator('.map-frame.space canvas')).toBeVisible()
  const landmark = page.getByRole('button', { name: /^Sensation: stomach in knots/ })
  await landmark.focus()
  await page.keyboard.press('Enter')
  await expect(landmark).toHaveAttribute('aria-pressed', 'true')

  const panel = page.getByRole('complementary', { name: 'Evidence' })
  await expect(panel.getByRole('heading', { name: 'stomach in knots' })).toBeVisible()
  await expect(panel.getByTestId('status-line')).toHaveText(/^Stated/)
  // The atlas may already hold other quotes for this concept; find the one from this upload.
  const quote = panel
    .getByRole('region', { name: 'Quotes' })
    .getByRole('listitem')
    .filter({ hasText: 'my stomach has been in knots since Monday' })
  await expect(quote).toHaveCount(1)
  await expect(quote).toContainText('Said directly')
  await page.screenshot({ path: testInfo.outputPath('map.png') })

  // The quote links back to its place in the transcript.
  await quote.getByRole('link', { name: 'In the transcript' }).click()
  await expect(page.locator('.segment.target')).toContainText('my stomach has been in knots')
})
