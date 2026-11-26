import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { chromium } from 'playwright-core'

// This scenario owns a separate Compose project. Never stops the development project.
const root = fileURLToPath(new URL('../..', import.meta.url))
const project = 'minify-links-smoke'
const api = 'http://localhost:18001'
const web = 'http://localhost:15174'
const composeEnv = { ...process.env, COMPOSE_PROJECT_NAME: project, BACKEND_PORT: '18001',
  FRONTEND_PORT: '15174', DATABASE_PORT: '15433', POSTGRES_USER: 'minify', POSTGRES_PASSWORD: 'minify',
  POSTGRES_DB: 'minify', DATABASE_TIMEOUT_SECONDS: '1', DATABASE_URL: 'postgresql+psycopg://minify:minify@database:5432/minify' }
let browser
let owned = false

function compose(args, output = false) {
  return execFileSync('docker', ['compose', '-p', project, ...args], {
    cwd: root, env: composeEnv, encoding: 'utf8', windowsHide: true,
    stdio: output ? 'pipe' : ['ignore', 'pipe', 'pipe'], timeout: 180000,
  }).trim()
}

async function ready() {
  for (let i = 0; i < 80; i++) {
    try { if ((await fetch(`${api}/ready`, { signal: AbortSignal.timeout(2000) })).ok) return } catch { /* Starting. */ }
    await delay(250)
  }
  throw new Error('Owned stack did not become ready')
}

try {
  assert.equal(compose(['ps', '--all', '--quiet'], true), '', 'Smoke project already has containers; refusing to take ownership')
  for (const origin of [api, web]) {
    let occupied = false
    try { await fetch(origin, { signal: AbortSignal.timeout(500) }); occupied = true } catch { /* Free. */ }
    assert.equal(occupied, false, `Smoke port already in use: ${origin}`)
  }
  owned = true
  // Reuse the built images; project-specific tags keep Compose ownership explicit.
  execFileSync('docker', ['image', 'tag', 'minify-backend', `${project}-backend`], { windowsHide: true })
  execFileSync('docker', ['image', 'tag', 'minify-frontend', `${project}-frontend`], { windowsHide: true })
  compose(['up', '-d', 'database', '--wait', '--wait-timeout', '120'])
  // Pin the owned database IP so stopping it tests PostgreSQL availability rather than
  // Docker's DNS retry latency, which can exceed the browser's five-second timeout.
  const databaseId = compose(['ps', '-q', 'database'], true)
  const metadata = JSON.parse(execFileSync('docker', ['inspect', databaseId], { encoding: 'utf8', windowsHide: true }))[0]
  const databaseIp = Object.values(metadata.NetworkSettings.Networks)[0].IPAddress
  composeEnv.DATABASE_URL = `postgresql+psycopg://minify:minify@${databaseIp}:5432/minify`
  compose(['up', '-d', '--no-build', '--wait', '--wait-timeout', '120'])
  compose(['exec', '-T', 'backend', 'python', '-m', 'alembic', 'upgrade', 'head'])
  await ready()
  browser = await chromium.launch({ headless: true, ...(process.env.SMOKE_BROWSER
    ? { executablePath: process.env.SMOKE_BROWSER } : { channel: process.platform === 'win32' ? 'msedge' : 'chrome' }) })
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 }, permissions: ['clipboard-read', 'clipboard-write'] })
  const page = await context.newPage()
  const pageErrors = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.goto(web)
  await page.getByRole('status').filter({ hasText: 'Backend operational' }).waitFor()
  const destination = `https://example.com/Browser%2FCase?q=one&q=two#${Date.now()}`
  const input = page.getByLabel('Destination URL')

  async function create(value = destination) {
    await input.fill(value)
    const response = page.waitForResponse(response => response.url() === `${api}/api/v1/links` && response.request().method() === 'POST')
    await input.press('Enter')
    const actual = await response
    assert.equal(actual.status(), 201)
    const result = await actual.json()
    await page.getByLabel('Short URL', { exact: true }).waitFor()
    assert.equal(await page.getByLabel('Short URL', { exact: true }).inputValue(), result.short_url)
    assert.match(result.short_code, /^[A-Za-z0-9]{7}$/)
    return result
  }

  const link = await create()
  const databaseCheck = "from uuid import UUID; import sys; from app.database import Database; from app.core.config import Settings; from app.models import Link; db=Database(Settings()); s=db.sessions(); row=s.get(Link, UUID(sys.argv[1])); assert row and row.short_code==sys.argv[2] and row.original_url==sys.argv[3]; s.close(); db.dispose()"
  compose(['exec', '-T', 'backend', 'python', '-c', databaseCheck, link.id, link.short_code, destination])
  console.log('PASS: real browser POST 201, rendered short URL, and committed PostgreSQL row')
  await page.getByRole('button', { name: 'Copy link', exact: true }).click()
  await page.getByText('Copied to clipboard.', { exact: true }).waitFor()
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), link.short_url)
  console.log('PASS: actual browser clipboard content matches the returned short URL')

  // Follow the local short URL, intercepting only the final external navigation.
  await context.route('https://example.com/**', route => route.fulfill({ status: 200, contentType: 'text/plain', body: 'Controlled destination' }))
  const redirectObserved = context.waitForEvent('response', { predicate: response => response.url() === link.short_url && response.status() === 302 })
  const popupPromise = context.waitForEvent('page')
  await page.getByRole('link', { name: 'Open short link' }).click()
  const popup = await popupPromise
  const redirect = await redirectObserved
  assert.equal(redirect.headers()['location'], destination)
  assert.equal(redirect.headers()['cache-control'], 'no-store')
  await popup.waitForURL(destination)
  await popup.close()
  console.log('PASS: open-link action reached actual 302 with exact Location; external navigation intercepted')

  await input.fill('javascript:alert(1)')
  await page.getByRole('button', { name: 'Shorten URL', exact: true }).click()
  await page.getByRole('alert').waitFor()
  assert.equal(await page.getByLabel('Short URL', { exact: true }).count(), 0)
  await page.getByRole('button', { name: 'Reset', exact: true }).click()
  assert.equal(await input.inputValue(), '')
  const second = await create()
  assert.notEqual(second.short_code, link.short_code)
  await page.setViewportSize({ width: 375, height: 812 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  const artifacts = resolve(root, '.local')
  await mkdir(artifacts, { recursive: true })
  await page.screenshot({ path: resolve(artifacts, 'links-mobile.png'), fullPage: true })
  console.log('PASS: visible invalid-input feedback, no false result, reset, repeat creation, and 375px layout')

  compose(['stop', 'backend'])
  await page.getByRole('button', { name: 'Check again' }).click()
  await page.getByRole('status').filter({ hasText: 'Backend unavailable' }).waitFor()
  await page.getByRole('button', { name: 'Shorten URL', exact: true }).click()
  await page.getByRole('alert').waitFor()
  assert.equal(await page.getByLabel('Short URL', { exact: true }).count(), 0)
  await assert.rejects(fetch(link.short_url, { redirect: 'manual', signal: AbortSignal.timeout(5000) }))
  compose(['start', 'backend'])
  await ready()
  await page.getByRole('button', { name: 'Check again' }).click()
  await page.getByRole('status').filter({ hasText: 'Backend operational' }).waitFor()
  await create()
  console.log('PASS: actual backend outage, creation and redirect failure, and recovery')

  compose(['stop', 'database'])
  const failure = page.waitForResponse(response => response.url() === `${api}/api/v1/links` && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Shorten URL', exact: true }).click()
  assert.equal((await failure).status(), 503)
  await page.getByRole('alert').filter({ hasText: 'temporarily unavailable' }).waitFor()
  assert.equal(await page.getByLabel('Short URL', { exact: true }).count(), 0)
  const unavailable = await fetch(link.short_url, { redirect: 'manual', signal: AbortSignal.timeout(10000) })
  assert.equal(unavailable.status, 503)
  assert.equal((await unavailable.json()).error.code, 'DATABASE_UNAVAILABLE')
  assert.equal((await fetch(`${api}/health`)).status, 200)
  assert.equal((await fetch(`${api}/ready`)).status, 503)
  compose(['start', 'database'])
  await ready()
  await create()
  assert.equal((await fetch(link.short_url, { redirect: 'manual' })).status, 302)
  console.log('PASS: actual PostgreSQL outage yields safe 503 for create/resolve; liveness and recovery verified')
  assert.deepEqual(pageErrors, [])
  console.log('PASS: no uncaught browser exceptions')
} finally {
  await browser?.close()
  if (owned) compose(['down'])
}
