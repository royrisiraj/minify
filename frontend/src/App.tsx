import { Connectivity } from './components/Connectivity'

export default function App() {
  return (
    <div className="shell mx-auto flex min-h-screen max-w-6xl flex-col px-6 sm:px-12">
      <header className="flex items-center justify-between gap-5 py-8">
        <a className="wordmark" href="/" aria-label="Minify home">minify<span>.</span></a>
        <span className="phase">Phase 01 — Foundation</span>
      </header>
      <main className="flex flex-1 flex-col justify-center py-16 sm:py-24">
        <p className="eyebrow">Small links. Big possibilities.</p>
        <h1>Shorter links.<br /><span>Smarter connections.</span></h1>
        <p className="description">
          An open-source platform for simple, reliable link management.
          We’re building the foundation. URL shortening and link tools are coming in future phases.
        </p>
        <Connectivity />
      </main>
      <footer className="flex flex-wrap items-center justify-between gap-4 py-7">
        <p>Minify · Minimal links. Maximum utility.</p>
        <p>Open source · MIT License</p>
      </footer>
    </div>
  )
}
