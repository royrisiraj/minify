import { afterEach, expect, it, vi } from 'vitest'
import { createLink, isShortLink } from './api'

export const link = {
  id: '00e06a48-e7bf-4b0c-a188-a1055ef9112c', original_url: 'https://example.com/Case?q=a&q=b#fragment',
  short_code: 'Ab12Zxy', short_url: 'http://localhost:8000/Ab12Zxy', is_active: true as const,
  created_at: '2026-11-26T00:00:00Z', expires_at: null,
}

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.useRealTimers() })

it('sends a real JSON POST to the configured versioned API with credentials omitted', async () => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com/api/v1/')
  const fetcher = vi.fn().mockResolvedValue(Response.json(link, { status: 201 }))
  vi.stubGlobal('fetch', fetcher)
  expect(await createLink({ original_url: link.original_url })).toEqual(link)
  expect(fetcher).toHaveBeenCalledExactlyOnceWith('https://api.example.com/api/v1/links', expect.objectContaining({
    method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ original_url: link.original_url }), credentials: 'omit', cache: 'no-store',
  }))
})

it.each([
  null, {}, { ...link, id: 'bad' }, { ...link, short_code: 'short' }, { ...link, short_code: 'abc-def' },
  { ...link, short_url: 'javascript:alert(1)' }, { ...link, short_url: 'https://evil.example/Wrong12' },
  { ...link, short_url: `${link.short_url}?override=1` }, { ...link, short_url: `${link.short_url}#evil` },
  { ...link, short_url: 'https://user:secret@example.com/Ab12Zxy' }, { ...link, is_active: false },
  { ...link, expires_at: 'tomorrow' }, { ...link, created_at: 'invalid' }, { ...link, created_at: '2026-01-01' },
  { ...link, original_url: 'data:text/html,unsafe' },
  { ...link, short_code: 'Ab12Zxy\n' }, { ...link, original_url: 'https:example.com' },
])('rejects malformed successful payload %j', async payload => {
  expect(isShortLink(payload)).toBe(false)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(payload, { status: 201 })))
  await expect(createLink({ original_url: link.original_url })).rejects.toThrow('unexpected link response')
})

it.each([['INVALID_URL', 'valid public'], ['INVALID_URL_SCHEME', 'http://'], ['CREATION_DISABLED', 'disabled'],
  ['DATABASE_UNAVAILABLE', 'temporarily unavailable'], ['INTERNAL_ERROR', 'unexpected service error'],
  ['SHORT_CODE_GENERATION_EXHAUSTED', 'allocate'], ['REQUEST_TOO_LARGE', 'too large'],
  ['FEATURE_NOT_SUPPORTED', 'not supported'], ['SELF_REFERENTIAL_URL', 'outside'], ['VALIDATION_ERROR', '4,096']])(
  'maps %s to safe actionable feedback', async (code, message) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ error: { code, message: 'private SQL password' } }, { status: 503 })))
    await expect(createLink({ original_url: link.original_url })).rejects.toThrow(message)
  },
)

it.each([200, 202, 400, 500])('rejects unexpected HTTP %s without retries or private response data', async status => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({ private: 'password' }, { status }))
  vi.stubGlobal('fetch', fetcher)
  await expect(createLink({ original_url: link.original_url })).rejects.toThrow('backend is unavailable')
  expect(fetcher).toHaveBeenCalledTimes(1)
})

it('times out POST without retrying and explains the uncertain creation outcome', async () => {
  vi.useFakeTimers()
  const fetcher = vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => {
    options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
  }))
  vi.stubGlobal('fetch', fetcher)
  const assertion = expect(createLink({ original_url: link.original_url }, { timeoutMs: 100 }))
    .rejects.toThrow('may have succeeded')
  await vi.advanceTimersByTimeAsync(100)
  await assertion
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(vi.getTimerCount()).toBe(0)
})
