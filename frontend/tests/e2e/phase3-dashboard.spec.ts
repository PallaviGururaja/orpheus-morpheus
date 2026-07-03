import path from 'node:path'
import { expect, test, type Page, type Route } from '@playwright/test'

// Phase-3 dashboard-builder E2E. Runs standalone against the static export (the
// Playwright webServer) with the API mocked via page.route, so no live backend /
// LLM is required — the dashboard is deterministic and LLM-free by design. It
// exercises the headline flow: switch to the Dashboard tab, drag a dimension +
// measure onto a widget, watch a chart render, switch chart types (pie/table),
// and save + reload a dashboard.

const CSV = path.join(__dirname, 'fixtures', 'sales.csv')

const DATASET = {
  session_id: 'sess-1',
  dataset_id: 'ds-1',
  name: 'sales.csv',
  row_count: 8,
  column_count: 5,
  profile: {
    columns: [
      { name: 'region', dtype: 'string', null_pct: 0, distinct: 4 },
      { name: 'product', dtype: 'string', null_pct: 0, distinct: 2 },
      { name: 'revenue', dtype: 'int64', null_pct: 0, distinct: 8 },
      { name: 'units', dtype: 'int64', null_pct: 0, distinct: 8 },
      { name: 'date', dtype: 'string', null_pct: 0, distinct: 8 },
    ],
    duplicate_rows: 0,
    flags: [],
  },
}

// In-memory saved-dashboard store for the mocked CRUD endpoints.
const saved: Record<string, { id: string; session_id: string; name: string; widgets: unknown[]; created_at: string }> = {}
let seq = 0

async function setupMocks(page: Page) {
  await page.route('**/datasets', async (route: Route) => {
    if (route.request().method() !== 'POST') return route.continue()
    await route.fulfill({ json: { data: DATASET } })
  })

  await page.route('**/dashboard/aggregate', async (route: Route) => {
    const req = route.request().postDataJSON() as {
      dimensions: string[]
      measure: string | null
      agg: string
      chart_type: string
    }
    const valueKey = req.measure ?? 'count'
    const dim = req.dimensions[0]
    const rows = dim
      ? [
          { [dim]: 'West', [valueKey]: 600000 },
          { [dim]: 'East', [valueKey]: 510000 },
          { [dim]: 'North', [valueKey]: 325000 },
          { [dim]: 'South', [valueKey]: 175000 },
        ]
      : [{ [valueKey]: 1610000 }]
    await route.fulfill({
      json: {
        data: {
          columns: [...req.dimensions, valueKey],
          rows,
          agg: req.agg,
          measure: req.measure,
          dimensions: req.dimensions,
          chart_type: req.chart_type,
          row_count: rows.length,
          truncated: false,
        },
      },
    })
  })

  await page.route('**/dashboards**', async (route: Route) => {
    const method = route.request().method()
    const url = new URL(route.request().url())
    const idMatch = url.pathname.match(/\/dashboards\/([^/]+)$/)

    if (method === 'POST') {
      const body = route.request().postDataJSON() as { session_id: string; name: string; widgets: unknown[] }
      seq += 1
      const id = `dash-${seq}`
      saved[id] = { id, session_id: body.session_id, name: body.name, widgets: body.widgets, created_at: '2026-07-03T00:00:00Z' }
      return route.fulfill({ json: { data: saved[id] } })
    }
    if (method === 'PUT' && idMatch) {
      const id = idMatch[1]
      const body = route.request().postDataJSON() as { name: string; widgets: unknown[] }
      saved[id] = { ...saved[id], name: body.name, widgets: body.widgets }
      return route.fulfill({ json: { data: saved[id] } })
    }
    if (method === 'DELETE' && idMatch) {
      delete saved[idMatch[1]]
      return route.fulfill({ json: { data: { deleted: true } } })
    }
    if (method === 'GET' && idMatch) {
      return route.fulfill({ json: { data: saved[idMatch[1]] } })
    }
    // GET list
    return route.fulfill({ json: { data: { dashboards: Object.values(saved) } } })
  })
}

// Simulate native HTML5 drag-and-drop with a shared DataTransfer so React's
// onDragStart/onDrop handlers fire exactly as they do for a real drag.
async function dragChip(page: Page, column: string, zoneTestId: string) {
  await page.evaluate(
    ({ column, zoneTestId }) => {
      const chip = document.querySelector(
        `[data-testid="column-chip"][data-column="${column}"]`,
      )
      const zone = document.querySelector(`[data-testid="${zoneTestId}"]`)
      if (!chip || !zone) throw new Error(`missing ${column} / ${zoneTestId}`)
      const dt = new DataTransfer()
      chip.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt }))
      zone.dispatchEvent(new DragEvent('dragenter', { bubbles: true, dataTransfer: dt }))
      zone.dispatchEvent(new DragEvent('dragover', { bubbles: true, dataTransfer: dt }))
      zone.dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: dt }))
      chip.dispatchEvent(new DragEvent('dragend', { bubbles: true, dataTransfer: dt }))
    },
    { column, zoneTestId },
  )
}

async function loadDatasetAndOpenDashboard(page: Page) {
  await page.goto('/app/')
  await page.getByTestId('file-input').setInputFiles(CSV)
  await expect(page.getByTestId('profile-card')).toBeVisible()
  await page.getByTestId('tab-dashboard').click()
  await expect(page.getByTestId('dashboard-view')).toBeVisible()
}

test.beforeEach(async ({ page }) => {
  await setupMocks(page)
})

test('dashboard tab shows a typed column palette from the active dataset', async ({ page }) => {
  await loadDatasetAndOpenDashboard(page)

  const palette = page.getByTestId('column-palette')
  await expect(palette).toBeVisible()
  // string columns → dimensions, numeric → measures.
  await expect(palette.locator('[data-role="dimension"][data-column="region"]')).toBeVisible()
  await expect(palette.locator('[data-role="measure"][data-column="revenue"]')).toBeVisible()
})

test('drag a dimension + measure onto a widget and a bar chart renders', async ({ page }) => {
  await loadDatasetAndOpenDashboard(page)

  await page.getByTestId('add-widget-empty').click()
  await expect(page.getByTestId('widget')).toHaveCount(1)

  await dragChip(page, 'region', 'dimension-dropzone')
  await expect(page.getByTestId('widget-dimension')).toContainText('region')

  await dragChip(page, 'revenue', 'measure-dropzone')
  await expect(page.getByTestId('widget-measure')).toContainText('revenue')

  // A chart renders from the mocked aggregate response.
  const chart = page.getByTestId('answer-chart')
  await expect(chart).toBeVisible()
  await expect(chart.locator('svg')).toBeVisible()
})

test('a non-numeric column dropped as a measure is rejected inline', async ({ page }) => {
  await loadDatasetAndOpenDashboard(page)
  await page.getByTestId('add-widget-empty').click()

  await dragChip(page, 'product', 'measure-dropzone')
  await expect(page.getByTestId('widget-error')).toContainText(/numeric measure/i)
})

test('count aggregation needs no measure and renders', async ({ page }) => {
  await loadDatasetAndOpenDashboard(page)
  await page.getByTestId('add-widget-empty').click()

  await dragChip(page, 'region', 'dimension-dropzone')
  await page.getByTestId('widget-agg').selectOption('count')
  await expect(page.getByTestId('answer-chart')).toBeVisible()
})

test('switch chart types to pie and table', async ({ page }) => {
  await loadDatasetAndOpenDashboard(page)
  await page.getByTestId('add-widget-empty').click()
  await dragChip(page, 'region', 'dimension-dropzone')
  await dragChip(page, 'revenue', 'measure-dropzone')
  await expect(page.getByTestId('answer-chart')).toBeVisible()

  await page.getByTestId('widget-chart-type').selectOption('table')
  await expect(page.getByTestId('chart-table')).toBeVisible()
  await expect(page.getByTestId('chart-table').locator('tbody tr')).not.toHaveCount(0)

  await page.getByTestId('widget-chart-type').selectOption('pie')
  await expect(page.getByTestId('answer-chart').locator('.recharts-pie')).toBeVisible()
})

test('add multiple widgets, save, reload the page, and reopen the dashboard', async ({ page }) => {
  await loadDatasetAndOpenDashboard(page)

  await page.getByTestId('add-widget-empty').click()
  await dragChip(page, 'region', 'dimension-dropzone')
  await dragChip(page, 'revenue', 'measure-dropzone')

  await page.getByTestId('add-widget').click()
  await expect(page.getByTestId('widget')).toHaveCount(2)

  await page.getByTestId('dashboard-name').fill('Sales overview')
  await page.getByTestId('save-dashboard').click()
  await expect(page.getByTestId('save-dashboard')).toHaveText('Update')

  // Reload the page (fresh state) then reopen the saved dashboard from the picker.
  await page.reload()
  await page.getByTestId('file-input').setInputFiles(CSV)
  await expect(page.getByTestId('profile-card')).toBeVisible()
  await page.getByTestId('tab-dashboard').click()

  await page.getByTestId('dashboard-picker-toggle').click()
  await page.getByTestId('saved-dashboard').first().click()
  await expect(page.getByTestId('dashboard-name')).toHaveValue('Sales overview')
  await expect(page.getByTestId('widget')).toHaveCount(2)
})
