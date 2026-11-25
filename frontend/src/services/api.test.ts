import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApiUrls, getHealth, getJson } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.useRealTimers()
})

describe('API URL construction', () => {
  it.each(['https://api.example.com/api/v1', 'https://api.example.com/api/v1/'])(
    'separates operational and versioned paths with %s', base => {
      const urls = createApiUrls(base)
      expect(urls.operational('/health')).toBe('https://api.example.com/health')
      expect(urls.versioned('/links')).toBe('https://api.example.com/api/v1/links')
    },
  )
  it.each(['invalid', 'ftp://api.example.com/api/v1', 'https://api.example.com',
    'https://user:secret@api.example.com/api/v1', 'https://api.example.com/api/v1?secret=x'])(
    'rejects malformed configuration %s', base => expect(() => createApiUrls(base)).toThrow(),
  )
})

describe('HTTP client', () => {
  it('uses the configured backend origin and verifies the health contract', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://backend.example.com/api/v2')
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ status: 'healthy', service: 'minify-api' }))
    vi.stubGlobal('fetch', fetchMock)
    expect(await getHealth()).toEqual({ status: 'healthy', service: 'minify-api' })
    expect(fetchMock).toHaveBeenCalledWith('https://backend.example.com/health', expect.objectContaining({ credentials: 'omit' }))
  })
  it('sanitizes HTTP errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('private-error', { status: 503 })))
    await expect(getJson('/health')).rejects.toThrow('The backend is unavailable.')
  })
  it('sanitizes network errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private-hostname')))
    await expect(getJson('/health')).rejects.toThrow('The backend is unavailable.')
  })
  it('handles invalid JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('not json')))
    await expect(getJson('/health')).rejects.toThrow('The backend is unavailable.')
  })
  it('rejects a successful response with the wrong health contract', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ status: 'unhealthy' })))
    await expect(getHealth()).rejects.toThrow('unexpected response')
  })
  it('times out a pending request and releases its timer', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })))
    const request = getJson('/health', { timeoutMs: 100 })
    const assertion = expect(request).rejects.toThrow('cancelled or timed out')
    await vi.advanceTimersByTimeAsync(100)
    await assertion
    expect(vi.getTimerCount()).toBe(0)
  })
  it('supports caller cancellation', async () => {
    const controller = new AbortController()
    vi.stubGlobal('fetch', vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })))
    const request = getJson('/health', { signal: controller.signal })
    controller.abort()
    await expect(request).rejects.toThrow('cancelled or timed out')
  })
})
