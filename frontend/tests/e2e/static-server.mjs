// Minimal static file server for the Next.js static export (`out/`), used by
// Playwright's `webServer` so the Phase-3 dashboard E2E can run WITHOUT a live
// backend (the test mocks the API via page.route). When a real backend is
// already serving on the port, Playwright reuses it instead (reuseExistingServer).
import { createServer } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { join, extname, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', 'out')
const PORT = Number(process.env.PORT ?? 8001)

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
}

async function resolveFile(pathname) {
  let rel = decodeURIComponent(pathname.split('?')[0])
  const candidate = normalize(join(ROOT, rel))
  if (!candidate.startsWith(ROOT)) return null
  try {
    const s = await stat(candidate)
    if (s.isDirectory()) return join(candidate, 'index.html')
    return candidate
  } catch {
    // try trailing-slash export layout (foo -> foo/index.html) then foo.html
    for (const alt of [join(candidate, 'index.html'), candidate + '.html']) {
      try {
        await stat(alt)
        return alt
      } catch {
        // keep trying
      }
    }
    return null
  }
}

const server = createServer(async (req, res) => {
  const file = await resolveFile(req.url ?? '/')
  if (!file) {
    res.statusCode = 404
    res.end('Not found')
    return
  }
  try {
    const body = await readFile(file)
    res.setHeader('Content-Type', TYPES[extname(file)] ?? 'application/octet-stream')
    res.end(body)
  } catch {
    res.statusCode = 500
    res.end('Server error')
  }
})

server.listen(PORT, () => {
  console.log(`static export served on http://localhost:${PORT}`)
})
