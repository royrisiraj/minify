import { useEffect, useRef, useState } from 'react'
import { createLink } from '../services/api'
import type { ShortenerState } from '../types/links'

export function validateInput(value: string): string | null {
  if (!value.trim()) return 'Enter a destination URL.'
  if (value.length > 4096) return 'Use a URL of at most 4,096 characters.'
  if (!/^https?:\/\//i.test(value.trim())) return 'Start your URL with http:// or https://.'
  try {
    const url = new URL(value.trim())
    if (!url.hostname || url.username || url.password || [...value].some(c => c.charCodeAt(0) < 32 || c.charCodeAt(0) === 127)) {
      return 'Enter a valid HTTP or HTTPS URL without credentials.'
    }
  } catch { return 'Enter a valid HTTP or HTTPS URL.' }
  return null
}

export function useShortener() {
  const [value, setValue] = useState('')
  const [state, setState] = useState<ShortenerState>({ status: 'idle' })
  const request = useRef<AbortController | null>(null)
  useEffect(() => () => request.current?.abort(), [])

  async function submit() {
    if (request.current) return
    setState({ status: 'validating' })
    const message = validateInput(value)
    if (message) { setState({ status: 'error', message }); return }
    const controller = new AbortController()
    request.current = controller
    setState({ status: 'submitting' })
    try {
      const link = await createLink({ original_url: value }, { signal: controller.signal })
      if (!controller.signal.aborted && request.current === controller) setState({ status: 'success', link })
    } catch (error) {
      if (!controller.signal.aborted && request.current === controller) setState({
        status: 'error', message: error instanceof Error ? error.message : 'The request failed. Try again later.',
      })
    } finally {
      if (request.current === controller) request.current = null
    }
  }

  function reset() {
    request.current?.abort()
    request.current = null
    setValue('')
    setState({ status: 'idle' })
  }

  return { value, setValue, state, submit, reset }
}
