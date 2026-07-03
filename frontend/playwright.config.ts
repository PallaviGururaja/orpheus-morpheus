import { defineConfig, devices } from '@playwright/test'

// E2E runs against the LIVE integrated app: the FastAPI backend serving the
// built frontend under /app/. Start PostgreSQL + Ollama + `uv run python -m src`
// and build the frontend before running `pnpm exec playwright test`.
const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:8001'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
