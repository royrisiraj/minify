import type { Health } from '../types/system'

export function createApiUrls(baseUrl: string) {
  const base = new URL(baseUrl)
  if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password ||
      base.search || base.hash || !/^\/api\/v\d+\/?$/.test(base.pathname)) {
    throw new Error('API configuration must be an HTTP(S) URL ending in /api/v<number>.')
  }
  return {
    operational: (path: string) => new URL(path.replace(/^\/+/, ''), `${base.origin}/`).href,
    versioned: (path: string) => new URL(path.replace(/^\/+/, ''), `${base.href.replace(/\/$/, '')}/`).href,
  }
}

interface RequestOptions {
  signal?: AbortSignal
  timeoutMs?: number
}

export async function getJson<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (options.signal?.aborted) controller.abort()
  options.signal?.addEventListener('abort', abort, { once: true })
  const timer = setTimeout(abort, options.timeoutMs ?? 5000)
  try {
    const response = await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
      credentials: 'omit',
      cache: 'no-store',
    })
    if (!response.ok) throw new Error('The backend is unavailable.')
    return await response.json() as T
  } catch {
    if (controller.signal.aborted) throw new Error('The request was cancelled or timed out.')
    throw new Error('The backend is unavailable.')
  } finally {
    clearTimeout(timer)
    options.signal?.removeEventListener('abort', abort)
  }
}

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const urls = createApiUrls(import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1')
  const result = await getJson<Health>(urls.operational('/health'), { signal })
  if (!result || result.status !== 'healthy' || result.service !== 'minify-api') {
    throw new Error('The backend returned an unexpected response.')
  }
  return result
}
