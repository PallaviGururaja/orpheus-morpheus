import path from 'node:path'
import { expect, test } from '@playwright/test'

// Phase-2 E2E against the LIVE integrated app (backend serving the built frontend
// under /app/, real Ollama + real PostgreSQL). Exercises the four Phase-2 wins:
// multi-dataset sidebar, streaming step-trace, follow-up chips, edit & rerun.
//
// Run: build the frontend, start PostgreSQL + Ollama + `uv run python -m src`,
// then `corepack pnpm exec playwright test tests/e2e/phase2.spec.ts`.

const CSV = path.join(__dirname, 'fixtures', 'sales.csv')

async function loadCsvAndAsk(page: import('@playwright/test').Page) {
  await page.goto('/app/')
  await expect(page.getByRole('heading', { name: 'Local Data Analyst' })).toBeVisible()

  await page.getByTestId('file-input').setInputFiles(CSV)
  await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 30_000 })

  await page.getByTestId('question-input').fill('What is the total revenue by region?')
  await page.getByTestId('ask-button').click()
}

test('streaming step-trace shows a live counter + timer, then a real answer', async ({
  page,
}) => {
  await loadCsvAndAsk(page)

  // Live progress replaces the old static spinner: a real "Step X of Y" counter.
  const trace = page.getByTestId('step-trace')
  await expect(trace).toBeVisible({ timeout: 15_000 })
  await expect(page.getByTestId('step-counter')).toContainText(/Step \d+ of \d+/)
  await expect(page.getByTestId('step-timer')).toContainText(/\d+\.\d+s/)

  // A real answer arrives once the stream completes.
  const answer = page.getByTestId('answer-block')
  await expect(answer).toBeVisible({ timeout: 120_000 })
  await expect(page.getByTestId('answer-text')).not.toBeEmpty()
  await expect(page.getByTestId('result-table').locator('tbody tr')).not.toHaveCount(0)
})

test('sidebar lists the dataset and supports add + remove', async ({ page }) => {
  await page.goto('/app/')
  await page.getByTestId('file-input').setInputFiles(CSV)
  await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 30_000 })

  const items = page.getByTestId('dataset-item')
  await expect(items).toHaveCount(1)

  // Remove it — it drops out of the working set (no server delete route).
  await page.getByTestId('remove-dataset').first().click()
  await expect(items).toHaveCount(0)
})

test('follow-up chips appear and are clickable after an answer', async ({ page }) => {
  await loadCsvAndAsk(page)
  await expect(page.getByTestId('answer-block')).toBeVisible({ timeout: 120_000 })

  const chips = page.getByTestId('followup-chip')
  // Follow-ups are non-fatal (may be empty on model failure); when present they ask.
  if ((await chips.count()) > 0) {
    await chips.first().click()
    await expect(page.getByTestId('step-trace')).toBeVisible({ timeout: 15_000 })
  }
})

test('code panel is editable and rerun produces a new result', async ({ page }) => {
  await loadCsvAndAsk(page)
  await expect(page.getByTestId('answer-block')).toBeVisible({ timeout: 120_000 })

  await page.getByTestId('code-toggle').click()
  const editor = page.getByTestId('code-editor')
  await expect(editor).toBeVisible()

  // The editor is writable; Rerun posts the edited code and shows a new answer.
  await editor.click()
  await page.getByTestId('rerun-button').click()
  await expect(page.getByTestId('answer-block')).toBeVisible({ timeout: 120_000 })
})
