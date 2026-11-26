import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { chromium } from 'playwright-core'

// Owns only its child services. Uses real HTTP and a locally installed browser.
const frontend = fileURLToPath(new URL('..', import.meta.url))
const backend = resolve(frontend, '..', 'backend')
const apiPort = process.env.SMOKE_API_PORT ?? '18000'
const webPort = process.env.SMOKE_WEB_PORT ?? '15173'
const apiOrigin = `http://localhost:${apiPort}`
const webOrigin = `http://localhost:${webPort}`
const python = process.env.SMOKE_PYTHON ?? resolve(backend,
  process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python')
const errors = []
let browser
let api
let web

function launch(command, args, cwd, env) {
  const child = spawn(command, args, {
    cwd, env: { ...process.env, ...env }, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
  })
  child.on('error', error => errors.push(error.message))
  child.stderr.on('data', data => errors.push(data.toString()))
  // Drain output; normal server logs are not verification results.
  child.stdout.resume()
  return child
}

function startApi() {
  return launch(python, ['-m', 'app'], backend, {
    APP_ENV: 'testing', DEBUG: 'false', HOST: '127.0.0.1', PORT: apiPort,
    FRONTEND_URL: webOrigin,
    // Deliberately unavailable local database to verify liveness independently.
    DATABASE_URL: 'postgresql+psycopg://test:test@127.0.0.1:1/minify_test',
    DATABASE_TIMEOUT_SECONDS: '1',
  })
}

async function waitForHttp(url) {
  for (let attempt = 0; attempt < 80; attempt++) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1000) })
      if (response.ok) return response
    } catch { /* Retry while the owned service starts. */ }
    await delay(250)
  }
  throw new Error(`Service did not start: ${url}\n${errors.join('\n')}`)
}

async function stop(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return
  const exited = new Promise(done => child.once('exit', done))
  child.kill()
  await Promise.race([exited, delay(5000).then(() => {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL')
  })])
}

try {
  // Refuse to accidentally test an existing service instead of the owned process.
  for (const origin of [apiOrigin, webOrigin]) {
    let occupied = false
    try { await fetch(origin, { signal: AbortSignal.timeout(500) }); occupied = true } catch { /* Free. */ }
    assert.equal(occupied, false, `Smoke-test port is already in use: ${origin}`)
  }
  api = startApi()
  web = launch(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', webPort],
    frontend, { VITE_API_BASE_URL: `${apiOrigin}/api/v1` })
  await waitForHttp(`${apiOrigin}/health`)
  await waitForHttp(webOrigin)
  assert.equal((await fetch(`${apiOrigin}/`)).status, 200)
  assert.equal((await fetch(`${apiOrigin}/ready`)).status, 503)
  assert.equal((await fetch(`${apiOrigin}/health`)).status, 200)
  browser = await chromium.launch({
    headless: true,
    ...(process.env.SMOKE_BROWSER ? { executablePath: process.env.SMOKE_BROWSER }
      : { channel: process.platform === 'win32' ? 'msedge' : 'chrome' }),
  })
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  const pageErrors = []
  page.on('pageerror', error => pageErrors.push(error.message))
  const healthResponse = page.waitForResponse(`${apiOrigin}/health`)
  await page.goto(webOrigin)
  assert.equal((await healthResponse).status(), 200)
  await page.getByRole('status').filter({ hasText: 'Backend operational' }).waitFor()
  await page.getByRole('heading', { name: 'Less link. More impact.' }).waitFor()
  const artifactPath = resolve(frontend, '..', '.local')
  await mkdir(artifactPath, { recursive: true })
  await page.screenshot({ path: resolve(artifactPath, 'foundation-desktop.png'), fullPage: true })
  console.log('PASS: real frontend/backend startup, health response, and rendered operational state')
  console.log('PASS: readiness failure returns 503 while liveness remains 200')

  await stop(api)
  await page.getByRole('button', { name: 'Check again' }).click()
  await page.getByRole('status').filter({ hasText: 'Backend unavailable' }).waitFor()
  console.log('PASS: stopping the real backend renders its unavailable state')

  api = startApi()
  await waitForHttp(`${apiOrigin}/health`)
  await page.getByRole('button', { name: 'Check again' }).click()
  await page.getByRole('status').filter({ hasText: 'Backend operational' }).waitFor()
  console.log('PASS: restarting the real backend and retrying renders recovery')

  await page.setViewportSize({ width: 375, height: 812 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true)
  await page.screenshot({ path: resolve(artifactPath, 'foundation-mobile.png'), fullPage: true })
  assert.deepEqual(pageErrors, [])
  console.log('PASS: 375px mobile layout fits; no uncaught browser exceptions')
} finally {
  await browser?.close()
  await stop(web)
  await stop(api)
}
