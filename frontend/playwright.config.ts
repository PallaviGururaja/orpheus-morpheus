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
  // If a live backend is already serving on BASE_URL it is reused (Phase-2 flow).
  // Otherwise a static server hosts the exported `out/` build so the Phase-3
  // dashboard E2E — which mocks the API via page.route — can run standalone.
  webServer: {
    command: 'node tests/e2e/static-server.mjs',
    url: `${BASE_URL}/app/`,
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
