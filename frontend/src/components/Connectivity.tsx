import { useEffect, useRef, useState } from 'react'
import { getHealth } from '../services/api'

type State = 'connecting' | 'operational' | 'unavailable'

const messages: Record<State, string> = {
  connecting: 'Connecting',
  operational: 'Backend operational',
  unavailable: 'Backend unavailable',
}

async function check(signal: AbortSignal): Promise<State> {
  try {
    await getHealth(signal)
    return 'operational'
  } catch {
    return 'unavailable'
  }
}

export function Connectivity() {
  const [state, setState] = useState<State>('connecting')
  const activeRequest = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    activeRequest.current = controller
    void check(controller.signal).then(next => {
      if (!controller.signal.aborted) setState(next)
    })
    return () => activeRequest.current?.abort()
  }, [])

  function retry() {
    activeRequest.current?.abort()
    const controller = new AbortController()
    activeRequest.current = controller
    setState('connecting')
    void check(controller.signal).then(next => {
      if (!controller.signal.aborted) setState(next)
    })
  }

  return (
    <section className="connection" aria-label="Backend connection">
      <div>
        <p className="eyebrow">Live service status</p>
        <p className="status" role="status" aria-live="polite">
          <span className={`status-dot ${state}`} aria-hidden="true" />
          {messages[state]}
        </p>
        <p className="connection-note">
          {state === 'operational'
            ? 'The API is responding to health checks.'
            : state === 'unavailable'
              ? 'The API could not be reached. You can try again.'
              : 'Checking the connection to the Minify API.'}
        </p>
      </div>
      <button onClick={retry} disabled={state === 'connecting'}>
        {state === 'connecting' ? 'Checking…' : 'Check again'}
      </button>
    </section>
  )
}
