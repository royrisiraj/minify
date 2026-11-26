import { useEffect, useRef, useState } from 'react'
import { copyText } from '../services/clipboard'
import type { ShortLink } from '../types/links'
import { Icon } from './Icon'

export function ShortLinkResult({ link, onReset }: { link: ShortLink; onReset: () => void }) {
  const [copyState, setCopyState] = useState<'idle' | 'copying' | 'copied' | 'error'>('idle')
  const alive = useRef(true)
  const copying = useRef(false)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  async function copy() {
    if (copying.current) return
    copying.current = true
    setCopyState('copying')
    try {
      await copyText(link.short_url)
      if (alive.current) setCopyState('copied')
    } catch {
      if (alive.current) setCopyState('error')
    } finally { copying.current = false }
  }

  return (
    <section className="short-result" aria-label="Short link result">
      <div className="result-heading">
        <span className="result-check"><Icon name="check" /></span>
        <h2>Your short link is ready</h2>
        <span className="result-caption">Ready to go places.</span>
      </div>
      <label className="sr-only" htmlFor="short-url">Short URL</label>
      <div className="result-url-row">
        <input id="short-url" value={link.short_url} readOnly onFocus={event => event.target.select()} />
        <button className={`button-copy${copyState === 'copied' ? ' is-copied' : ''}`} type="button" onClick={() => { void copy() }} disabled={copyState === 'copying'}>
          <Icon name={copyState === 'copied' ? 'check' : 'copy'} />Copy link
        </button>
      </div>
      <div className="destination"><span className="destination-caption">Destination</span><p>{link.original_url}</p></div>
      <div className="result-actions">
        <a className="button-text open-link" href={link.short_url} target="_blank" rel="noopener noreferrer"><Icon name="open" />Open short link</a>
        <button className="button-text" type="button" onClick={onReset}><Icon name="reset" />Shorten another link</button>
      </div>
      <p className={`copy-feedback${copyState === 'error' ? ' copy-error' : ''}`} aria-live="polite">{copyState === 'copied' ? 'Copied to clipboard.' : copyState === 'error'
        ? 'Could not copy. Select the short URL above and copy it manually.' : ''}</p>
    </section>
  )
}
