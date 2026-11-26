import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ShortenForm } from './ShortenForm'

const link = {
  id: '00e06a48-e7bf-4b0c-a188-a1055ef9112c', original_url: 'https://example.com/Case?q=a&q=b#fragment',
  short_code: 'Ab12Zxy', short_url: 'http://localhost:8000/Ab12Zxy', is_active: true,
  created_at: '2026-11-26T00:00:00Z', expires_at: null,
}

afterEach(() => vi.unstubAllGlobals())

it.each(['', 'javascript:alert(1)', 'https://', 'https://user:secret@example.com', 'https://example.com/' + 'x'.repeat(4096)])(
  'validates before sending %s', async value => {
    const fetcher = vi.fn()
    vi.stubGlobal('fetch', fetcher)
    render(<ShortenForm />)
    fireEvent.change(screen.getByLabelText('Destination URL'), { target: { value } })
    await userEvent.click(screen.getByRole('button', { name: 'Shorten URL' }))
    expect(screen.getByRole('alert')).toHaveTextContent(/Enter|Start|Use/)
    expect(fetcher).not.toHaveBeenCalled()
  },
)

it('creates on Enter, renders actual result, copies, opens, and resets for another creation', async () => {
  const user = userEvent.setup()
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  const fetcher = vi.fn().mockImplementation(() => Promise.resolve(Response.json(link, { status: 201 })))
  vi.stubGlobal('fetch', fetcher)
  render(<ShortenForm />)
  const input = screen.getByLabelText('Destination URL')
  await user.type(input, `${link.original_url}{Enter}`)
  expect(await screen.findByRole('heading', { name: 'Your short link is ready' })).toBeInTheDocument()
  expect(screen.getByLabelText('Short URL')).toHaveValue(link.short_url)
  expect(screen.getByText('Your short link is ready.')).toHaveAttribute('aria-live', 'polite')
  const open = screen.getByRole('link', { name: 'Open short link' })
  expect(open).toHaveAttribute('href', link.short_url)
  expect(open).toHaveAttribute('target', '_blank')
  expect(open).toHaveAttribute('rel', 'noopener noreferrer')
  await user.click(screen.getByRole('button', { name: 'Copy link' }))
  await screen.findByText('Copied to clipboard.')
  expect(writeText).toHaveBeenCalledWith(link.short_url)
  await user.click(screen.getByRole('button', { name: 'Shorten another link' }))
  expect(input).toHaveValue('')
  expect(input).toHaveFocus()
  expect(screen.queryByLabelText('Short URL')).not.toBeInTheDocument()
  await user.type(input, `${link.original_url}{Enter}`)
  await screen.findByLabelText('Short URL')
  expect(fetcher).toHaveBeenCalledTimes(2)
})

it.each(['denied', 'unsupported'])('handles %s clipboard with selectable manual fallback', async mode => {
  const user = userEvent.setup()
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: mode === 'unsupported'
    ? undefined : { writeText: vi.fn().mockRejectedValue(new Error('denied')) } })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(link, { status: 201 })))
  render(<ShortenForm />)
  await user.type(screen.getByLabelText('Destination URL'), `${link.original_url}{Enter}`)
  await user.click(await screen.findByRole('button', { name: 'Copy link' }))
  await screen.findByText('Could not copy. Select the short URL above and copy it manually.')
  expect(screen.queryByText('Copied to clipboard.')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Short URL')).toHaveAttribute('readonly')
})

it('guards duplicate submits, aborts on reset, and ignores a stale response', async () => {
  let resolve!: (value: Response) => void
  let signal!: AbortSignal
  const fetcher = vi.fn((_url, options: RequestInit) => {
    signal = options.signal as AbortSignal
    return new Promise<Response>(done => { resolve = done })
  })
  vi.stubGlobal('fetch', fetcher)
  render(<ShortenForm />)
  fireEvent.change(screen.getByLabelText('Destination URL'), { target: { value: link.original_url } })
  const form = screen.getByRole('button', { name: 'Shorten URL' }).closest('form')!
  fireEvent.submit(form)
  fireEvent.submit(form)
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('button', { name: 'Shortening…' })).toBeDisabled()
  expect(screen.getByLabelText('Destination URL')).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Reset' }))
  expect(signal.aborted).toBe(true)
  await act(async () => resolve(Response.json(link, { status: 201 })))
  expect(screen.queryByLabelText('Short URL')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Destination URL')).toHaveValue('')
})

it('aborts creation on unmount', async () => {
  let signal!: AbortSignal
  vi.stubGlobal('fetch', vi.fn((_url, options: RequestInit) => {
    signal = options.signal as AbortSignal
    return new Promise(() => {})
  }))
  const view = render(<ShortenForm />)
  fireEvent.change(screen.getByLabelText('Destination URL'), { target: { value: link.original_url } })
  fireEvent.submit(screen.getByRole('button', { name: 'Shorten URL' }).closest('form')!)
  view.unmount()
  expect(signal.aborted).toBe(true)
})

it.each(['network', 'validation', 'database', 'malformed'])('renders %s errors, clears old results, and supports a manual retry', async mode => {
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(link, { status: 201 }))
  if (mode === 'network') fetcher.mockRejectedValueOnce(new Error('private host'))
  else if (mode === 'malformed') fetcher.mockResolvedValueOnce(Response.json({}, { status: 201 }))
  else fetcher.mockResolvedValueOnce(Response.json({ error: { code: mode === 'database' ? 'DATABASE_UNAVAILABLE' : 'INVALID_URL', message: 'private data' } }, { status: 503 }))
  fetcher.mockResolvedValueOnce(Response.json(link, { status: 201 }))
  vi.stubGlobal('fetch', fetcher)
  render(<ShortenForm />)
  const input = screen.getByLabelText('Destination URL')
  await userEvent.type(input, link.original_url)
  await userEvent.click(screen.getByRole('button', { name: 'Shorten URL' }))
  await screen.findByLabelText('Short URL')
  await userEvent.click(screen.getByRole('button', { name: 'Shorten URL' }))
  expect(await screen.findByRole('alert')).not.toHaveTextContent('private')
  expect(screen.queryByLabelText('Short URL')).not.toBeInTheDocument()
  expect(input).toHaveValue(link.original_url)
  await userEvent.click(screen.getByRole('button', { name: 'Shorten URL' }))
  await screen.findByLabelText('Short URL')
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3))
})
