import { Connectivity } from './components/Connectivity'
import { ShortenForm } from './components/ShortenForm'

export default function App() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="site-header">
        <a className="wordmark" href="/" aria-label="Minify home">minify<span>.</span></a>
        <span className="header-caption">A little less goes a long way.</span>
        <span className="header-edition">The URL shortener</span>
      </header>
      <main id="main">
        <section className="hero" aria-labelledby="hero-title">
          <p className="eyebrow hero-eyebrow"><span className="accent-rule" />Small by design.</p>
          <div className="hero-composition">
            <h1 id="hero-title">Less link.<br />More impact<span className="accent-period">.</span></h1>
            <div className="hero-aside">
              <p className="hero-tagline">Shorter links. <br />Smarter connections.</p>
              <p className="hero-description">Give your next big idea<br /> a smaller address.</p>
            </div>
          </div>
        </section>
        <div className="workspace">
          <ShortenForm />
          <Connectivity />
        </div>
        <div className="closing-note" aria-hidden="true">
          <span>Less noise. More possibility.</span>
          <span className="precision-mark"><i /><i /><i /></span>
        </div>
      </main>
      <footer className="site-footer">
        <p className="footer-signature">minify<span>.</span> <span className="footer-motto">Keep it short.</span></p>
        <p className="footer-license">Open source <span aria-hidden="true">/</span> MIT License</p>
      </footer>
    </div>
  )
}
