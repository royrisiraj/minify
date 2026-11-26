import type { Health } from '../types/system'
import type { CreateLinkRequest, ShortLink } from '../types/links'

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

const linkErrors: Record<string, string> = {
  VALIDATION_ERROR: 'Enter a destination URL of at most 4,096 characters.',
  INVALID_URL: 'Enter a valid public HTTP or HTTPS URL without credentials.',
  INVALID_URL_SCHEME: 'Start your URL with http:// or https://.',
  SELF_REFERENTIAL_URL: 'Use a destination outside this Minify service.',
  FEATURE_NOT_SUPPORTED: 'Custom aliases and expiration are not supported yet.',
  CREATION_DISABLED: 'Link creation is disabled in this environment.',
  REQUEST_TOO_LARGE: 'The request is too large. Use a shorter destination URL.',
  SHORT_CODE_GENERATION_EXHAUSTED: 'Unable to allocate a short link. Try again later.',
  DATABASE_UNAVAILABLE: 'The link service is temporarily unavailable. Try again later.',
  INTERNAL_ERROR: 'An unexpected service error occurred. Try again later.',
}

export class ApiError extends Error {}

async function requestJson<T>(url: string, options: RequestOptions = {}, body?: CreateLinkRequest): Promise<T> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (options.signal?.aborted) controller.abort()
  options.signal?.addEventListener('abort', abort, { once: true })
  const timer = setTimeout(abort, options.timeoutMs ?? 5000)
  try {
    const response = await fetch(url, {
      method: body ? 'POST' : 'GET',
      headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
      signal: controller.signal,
      credentials: 'omit',
      cache: 'no-store',
    })
    if (!response.ok || (body && response.status !== 201)) {
      if (body) {
        const payload: unknown = await response.json().catch(() => null)
        const error = payload && typeof payload === 'object' && 'error' in payload ? payload.error : null
        const code = error && typeof error === 'object' && 'code' in error ? error.code : null
        if (typeof code === 'string' && Object.hasOwn(linkErrors, code)) throw new ApiError(linkErrors[code])
      }
      throw new ApiError('The backend is unavailable.')
    }
    return await response.json() as T
  } catch (error) {
    if (controller.signal.aborted) throw new Error(body
      ? 'The request was cancelled or timed out. It may have succeeded; check before trying again.'
      : 'The request was cancelled or timed out.', { cause: error })
    if (error instanceof ApiError) throw error
    throw new Error('The backend is unavailable.', { cause: error })
  } finally {
    clearTimeout(timer)
    options.signal?.removeEventListener('abort', abort)
  }
}

export function getJson<T>(url: string, options: RequestOptions = {}): Promise<T> {
  return requestJson<T>(url, options)
}

function publicHttpUrl(value: unknown): value is string {
  if (typeof value !== 'string' || value.length > 4096 || !/^https?:\/\//i.test(value) ||
      [...value].some(c => c.charCodeAt(0) <= 32 || c.charCodeAt(0) === 127)) return false
  try {
    const parsed = new URL(value)
    return ['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password
  } catch { return false }
}

export function isShortLink(value: unknown): value is ShortLink {
  if (!value || typeof value !== 'object') return false
  const link = value as Partial<ShortLink>
  if (typeof link.id !== 'string' || !/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(link.id) ||
      typeof link.short_code !== 'string' || link.short_code.length !== 7 || !/^[a-zA-Z0-9]{7}$/.test(link.short_code) ||
      !publicHttpUrl(link.original_url) || !publicHttpUrl(link.short_url) ||
      link.is_active !== true || link.expires_at !== null || typeof link.created_at !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(link.created_at) ||
      !Number.isFinite(Date.parse(link.created_at))) return false
  const shortUrl = new URL(link.short_url)
  return shortUrl.pathname === `/${link.short_code}` && !shortUrl.search && !shortUrl.hash
}

export async function createLink(body: CreateLinkRequest, options: RequestOptions = {}): Promise<ShortLink> {
  const urls = createApiUrls(import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1')
  const result = await requestJson<unknown>(urls.versioned('/links'), options, body)
  if (!isShortLink(result)) throw new ApiError('The backend returned an unexpected link response.')
  return result
}

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const urls = createApiUrls(import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1')
  const result = await getJson<Health>(urls.operational('/health'), { signal })
  if (!result || result.status !== 'healthy' || result.service !== 'minify-api') {
    throw new Error('The backend returned an unexpected response.')
  }
  return result
}
