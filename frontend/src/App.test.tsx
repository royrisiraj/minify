import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => vi.unstubAllGlobals())

it('renders branding, phase, and the loading state', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
  const view = render(<App />)
  expect(screen.getByRole('link', { name: 'Minify home' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Shorter links.Smarter connections.')
  expect(screen.getByText('Phase 01 — Foundation')).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('Connecting')
  expect(screen.getByRole('button')).toBeDisabled()
  view.unmount()
})

it('renders the actual successful health response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ status: 'healthy', service: 'minify-api' })))
  render(<App />)
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Backend operational'))
})

it.each(['http', 'network'])('handles %s failure and recovers on retry', async failure => {
  const fetchMock = vi.fn()
  if (failure === 'http') fetchMock.mockResolvedValueOnce(new Response(null, { status: 503 }))
  else fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
  fetchMock.mockResolvedValueOnce(Response.json({ status: 'healthy', service: 'minify-api' }))
  vi.stubGlobal('fetch', fetchMock)
  render(<App />)
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Backend unavailable'))
  await userEvent.click(screen.getByRole('button', { name: 'Check again' }))
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Backend operational'))
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('aborts the request on unmount and ignores its later response', async () => {
  let resolve!: (response: Response) => void
  let signal: AbortSignal | undefined
  vi.stubGlobal('fetch', vi.fn((_url, options: RequestInit) => {
    signal = options.signal ?? undefined
    return new Promise<Response>(done => { resolve = done })
  }))
  const view = render(<App />)
  view.unmount()
  expect(signal?.aborted).toBe(true)
  await act(async () => resolve(Response.json({ status: 'healthy', service: 'minify-api' })))
})
