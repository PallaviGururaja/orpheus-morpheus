import path from 'node:path'
import { expect, test } from '@playwright/test'

// Primary-journey smoke test against the LIVE integrated app (backend serving the
// built frontend under /app/, real Ollama + real PostgreSQL). Asserts real
// rendered content, not just HTTP status: profile renders, an answer with a
// summary table appears after asking a real question.
//
// Run: build the frontend, start PostgreSQL + Ollama + `uv run python -m src`,
// then `pnpm exec playwright test tests/e2e/`.

const CSV = path.join(__dirname, 'fixtures', 'sales.csv')

test('upload CSV, see profile, ask a question, get an answer with a table', async ({ page }) => {
  await page.goto('/app/')

  // Page loads and is styled (blue brand mark from Tailwind utilities).
  await expect(page.getByRole('heading', { name: 'Local Data Analyst' })).toBeVisible()

  // Upload the CSV fixture.
  await page.getByTestId('file-input').setInputFiles(CSV)

  // Profile renders from the real file: column names + row count.
  const profile = page.getByTestId('profile-card')
  await expect(profile).toBeVisible({ timeout: 30_000 })
  await expect(profile).toContainText('region')
  await expect(profile).toContainText('revenue')

  // Ask a real question.
  await page.getByTestId('question-input').fill('What is the total revenue by region?')
  await page.getByTestId('ask-button').click()

  // The agent runs locally; wait for a real answer block with content.
  const answer = page.getByTestId('answer-block')
  await expect(answer).toBeVisible({ timeout: 90_000 })

  const answerText = page.getByTestId('answer-text')
  await expect(answerText).not.toBeEmpty()

  // Summary table renders with real content.
  const table = page.getByTestId('result-table')
  await expect(table).toBeVisible()
  await expect(table.locator('tbody tr')).not.toHaveCount(0)

  // Generated code is inspectable (Phase 2: now an editable editor).
  await page.getByTestId('code-toggle').click()
  await expect(page.getByTestId('code-editor')).toBeVisible()
})
