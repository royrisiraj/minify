import { useEffect, useRef } from 'react'
import { useShortener } from '../hooks/useShortener'
import { ShortLinkResult } from './ShortLinkResult'
import { Icon } from './Icon'

export function ShortenForm() {
  const { value, setValue, state, submit, reset } = useShortener()
  const input = useRef<HTMLInputElement>(null)
  const focusAfterReset = useRef(false)
  const busy = state.status === 'submitting' || state.status === 'validating'
  useEffect(() => {
    if (state.status === 'idle' && focusAfterReset.current) {
      focusAfterReset.current = false
      input.current?.focus()
    }
  }, [state.status])
  function startAgain() { focusAfterReset.current = true; reset() }

  return (
    <section className={`shortener is-${state.status}`} aria-label="URL shortener">
      <form className="shorten-form" noValidate onSubmit={event => { event.preventDefault(); void submit() }} aria-busy={busy}>
        <p className="sr-only" aria-live="polite">{state.status === 'success' ? 'Your short link is ready.' : ''}</p>
        <div className="form-heading">
          <label htmlFor="destination-url">Destination URL</label>
          <span className="form-instruction">Long URL in. Short link out.</span>
        </div>
        <div className={`short-input-row${state.status === 'error' ? ' has-error' : ''}`}>
          <div className="destination-field">
            <Icon name="link" />
            <input ref={input} id="destination-url" type="url" inputMode="url" autoComplete="url"
              placeholder="Paste your long URL here" value={value} disabled={busy}
              onChange={event => setValue(event.target.value)}
              aria-invalid={state.status === 'error'} aria-describedby={`destination-help${state.status === 'error' ? ' shorten-error' : ''}`} />
          </div>
          <button className="button-primary shorten-button" type="submit" disabled={busy}>
            {busy && <span className="spinner" aria-hidden="true" />}
            {busy ? 'Shortening…' : 'Shorten URL'}
          </button>
        </div>
        <div className="form-footnote">
          <p id="destination-help">Public HTTP or HTTPS URLs. Up to 4,096 characters.</p>
          <span className="enter-hint" aria-hidden="true">Press <kbd>Enter ↵</kbd></span>
        </div>
        <div className="request-feedback" aria-live="polite">
          {busy && <p className="loading-message">Creating your short link…</p>}
        </div>
        {state.status === 'error' && <p className="error-message" id="shorten-error" role="alert"><Icon name="alert" />{state.message}</p>}
        {state.status !== 'idle' && state.status !== 'success' && <button className="button-text reset-request" type="button" onClick={startAgain}><Icon name="reset" />Reset</button>}
      </form>
      {state.status === 'success' && <ShortLinkResult key={state.link.id} link={state.link} onReset={startAgain} />}
    </section>
  )
}
