import { useState, useEffect, createContext, useContext } from 'react'
import './App.css'
import { LANGS, SNIPPETS, makeT, detectLang } from './i18n'

/* ── language context ── */
const LangCtx = createContext({ lang: 'en', setLang: () => {}, t: (k) => k })
const useT = () => useContext(LangCtx)

/* ── tiny markup renderer: **bold**, `code`, [label](url) ── */
function RichText({ children }) {
  const text = children || ''
  const re = /\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)/g
  const parts = []
  let last = 0, m, key = 0
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    if (m[1] != null) parts.push(<strong key={key++}>{m[1]}</strong>)
    else if (m[2] != null) parts.push(<code key={key++}>{m[2]}</code>)
    else parts.push(
      <a key={key++} href={m[4]} target="_blank" rel="noopener noreferrer">{m[3]}</a>
    )
    last = re.lastIndex
  }
  if (last < text.length) parts.push(text.slice(last))
  return <>{parts}</>
}

/* ── language picker ── */
function LangPicker() {
  const { lang, setLang } = useT()
  return (
    <select className="lang-picker" value={lang}
            onChange={(e) => setLang(e.target.value)} aria-label="Language">
      {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
    </select>
  )
}

/* ── copy-to-clipboard button ── */
function CopyBtn({ text }) {
  const { t } = useT()
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }
  return (
    <button className={`copy-btn${copied ? ' copied' : ''}`} onClick={copy}>
      {copied ? t('common.copied') : t('common.copy')}
    </button>
  )
}

/* ── animated contributor-removal demo ── */
function ContributorDemo() {
  const { t } = useT()
  return (
    <div className="demo" aria-hidden="true">
      <div className="demo-bar">
        <span className="dot r" /><span className="dot y" /><span className="dot g" />
        <span className="url">github.com/you/repo · Insights</span>
      </div>
      <div className="demo-body">
        <div className="demo-title">
          Contributors <span className="count">2 &rarr; 1</span>
        </div>

        <div className="crow">
          <div className="ava u1">Y</div>
          <div className="meta">
            <span className="uname">you</span>
            <span className="ccount">47 commits</span>
          </div>
          <div className="bars">
            <i style={{ height: '60%' }} /><i style={{ height: '90%' }} />
            <i style={{ height: '45%' }} /><i style={{ height: '75%' }} />
          </div>
        </div>

        <div className="crow claude">
          <div className="ava">C</div>
          <div className="meta">
            <span className="uname">@claude</span>
            <span className="ccount">12 commits</span>
          </div>
          <div className="bars">
            <i style={{ height: '40%' }} /><i style={{ height: '55%' }} />
            <i style={{ height: '30%' }} /><i style={{ height: '50%' }} />
          </div>
        </div>

        <div className="demo-toast">{t('demo.toast')}</div>
      </div>
    </div>
  )
}

/* ── animated terminal (loops the declaude run) ── */
const LINES = [
  { t: '$ declaude you/repo', cls: 'cmd', pr: true },
  { t: '  cloning you/repo …', cls: 'dim' },
  { t: '  traces : 12 co-author commit(s)', cls: 'warn' },
  { t: '  rewriting history (git filter-repo)…', cls: 'dim' },
  { t: '  local history is clean (0 traces)', cls: 'ok' },
  { t: '  force-pushing branches: main ✓', cls: 'ok' },
  { t: '  flushing contributor cache…', cls: 'dim' },
  { t: '  contributor cache flushed', cls: 'ok' },
  { t: '  refreshing contributors graph…', cls: 'dim' },
  { t: '  ✓ Done. @claude removed', cls: 'done' },
]

function Terminal() {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (n < LINES.length) {
      const id = setTimeout(() => setN(n + 1), 600)
      return () => clearTimeout(id)
    }
    const id = setTimeout(() => setN(0), 2800)
    return () => clearTimeout(id)
  }, [n])

  return (
    <div className="terminal">
      <div className="terminal-bar">
        <span className="dot r" /><span className="dot y" /><span className="dot g" />
        <span className="title">declaude · PowerShell</span>
      </div>
      <div className="terminal-body">
        {LINES.slice(0, n).map((l, i) => (
          <div key={i} className={`tline ${l.cls}`}>
            {l.pr ? <><span className="pr">$</span>{l.t.slice(1)}</> : l.t}
            {i === n - 1 && n < LINES.length && <span className="cursor" />}
          </div>
        ))}
        {n === LINES.length && (
          <div className="tline cmd"><span className="pr">$</span> <span className="cursor" /></div>
        )}
      </div>
    </div>
  )
}

/* ── landing page ── */
function LandingPage({ onDocs }) {
  const { t } = useT()
  return (
    <>
      <section className="hero">
        <div className="hero-left">
          <div className="badge"><span className="badge-dot" />v0.1.2 · {t('hero.badge')}</div>
          <h1>
            {t('hero.titlePre')} <span className="strike mark">@claude</span> {t('hero.titlePost')}
          </h1>
          <p className="sub">{t('hero.sub')}</p>
          <div className="install-box">
            <span className="prefix">$</span>
            {SNIPPETS.install}
            <CopyBtn text={SNIPPETS.install} />
          </div>
          <div className="hero-actions">
            <button className="btn btn-primary" onClick={onDocs}>{t('hero.docsBtn')} &rarr;</button>
            <a className="btn btn-outline" href="https://github.com/ediiloupatty/declaude"
               target="_blank" rel="noopener noreferrer">{t('hero.ghBtn')}</a>
          </div>
        </div>
        <div className="hero-right">
          <ContributorDemo />
        </div>
      </section>

      <section className="how">
        <div className="how-inner">
          <div className="how-text">
            <span className="section-label">{t('how.label')}</span>
            <h2>{t('how.title')}</h2>
            <p><RichText>{t('how.p')}</RichText></p>
            <ul className="flow">
              <li><span className="tick">1</span><span><RichText>{t('how.step1')}</RichText></span></li>
              <li><span className="tick">2</span><span><RichText>{t('how.step2')}</RichText></span></li>
              <li><span className="tick">3</span><span><RichText>{t('how.step3')}</RichText></span></li>
            </ul>
          </div>
          <Terminal />
        </div>
      </section>

      <footer className="footer">
        <a className="footer-gh" href="https://github.com/ediiloupatty/declaude"
           target="_blank" rel="noopener noreferrer">
          <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/>
          </svg>
          github.com/ediiloupatty/declaude
        </a>
        <p>{t('footer.note')}</p>
      </footer>
    </>
  )
}

/* ── docs page (with scroll-spy) ── */
const NAV = [
  { group: 'nav.group.start', items: [
    ['why', 'nav.why'], ['install', 'nav.install'], ['usage', 'nav.usage'], ['commands', 'nav.commands'],
  ]},
  { group: 'nav.group.ref', items: [
    ['options', 'nav.options'], ['requirements', 'nav.requirements'], ['caveats', 'nav.caveats'],
    ['backup', 'nav.backup'], ['prevent', 'nav.prevent'],
  ]},
  { group: 'nav.group.dev', items: [
    ['dev', 'nav.development'],
  ]},
]

function DocsPage({ onHome }) {
  const { t } = useT()
  const [active, setActive] = useState('why')

  useEffect(() => {
    const ids = NAV.flatMap(g => g.items.map(([id]) => id))
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => { if (e.isIntersecting) setActive(e.target.id) })
      },
      { rootMargin: '-12% 0px -78% 0px' }
    )
    ids.forEach((id) => {
      const el = document.getElementById(id)
      if (el) obs.observe(el)
    })
    return () => obs.disconnect()
  }, [])

  return (
    <div className="docs-wrap">
      <aside className="docs-sidebar">
        {NAV.map((g) => (
          <div key={g.group}>
            <div className="docs-sidebar-label">{t(g.group)}</div>
            <nav>
              {g.items.map(([id, label]) => (
                <a key={id} href={`#${id}`}
                   className={active === id ? 'active' : ''}
                   onClick={() => setActive(id)}>
                  {t(label)}
                </a>
              ))}
            </nav>
          </div>
        ))}
      </aside>

      <main className="docs-content">
        <button className="btn btn-ghost docs-mobile-back" onClick={onHome}>&larr; {t('docs.back')}</button>

        <h1>declaude</h1>
        <p className="lead"><RichText>{t('docs.lead')}</RichText></p>

        <h2 id="why">{t('docs.why.h')}</h2>
        <p><RichText>{t('docs.why.p1')}</RichText></p>
        <pre><code>{SNIPPETS.trailer}</code></pre>
        <p><RichText>{t('docs.why.p2')}</RichText></p>
        <p><RichText>{t('docs.why.p3')}</RichText></p>

        <h2 id="install">{t('nav.install')}</h2>
        <pre><code>{SNIPPETS.install}</code></pre>
        <p>{t('docs.install.p1')}</p>
        <pre><code>{SNIPPETS.installGit}</code></pre>
        <p><RichText>{t('docs.install.p2')}</RichText></p>
        <pre><code>{SNIPPETS.ghInstall}</code></pre>
        <div className="callout">
          <strong>{t('docs.install.calloutLabel')}</strong> <RichText>{t('docs.install.callout')}</RichText>
        </div>
        <p>{t('docs.install.p3')}</p>
        <pre><code>{SNIPPETS.ghLogin}</code></pre>

        <h3>{t('docs.install.h3')}</h3>
        <p><RichText>{t('docs.install.p4')}</RichText></p>
        <pre><code>{SNIPPETS.winRun}</code></pre>
        <p><RichText>{t('docs.install.p5')}</RichText></p>
        <pre><code>{SNIPPETS.path}</code></pre>
        <p>{t('docs.install.p6')}</p>
        <pre><code>{SNIPPETS.pipx}</code></pre>

        <h2 id="usage">{t('nav.usage')}</h2>
        <pre><code>{SNIPPETS.usage}</code></pre>
        <p>{t('docs.usage.p')}</p>

        <h2 id="commands">{t('nav.commands')}</h2>
        <div className="docs-table-wrap">
          <table className="docs-table">
            <thead><tr><th>{t('docs.th.command')}</th><th>{t('docs.th.purpose')}</th></tr></thead>
            <tbody>
              <tr><td><code>declaude TARGET [flags]</code></td><td><RichText>{t('docs.cmd.main')}</RichText></td></tr>
              <tr><td><code>declaude path</code></td><td><RichText>{t('docs.cmd.path')}</RichText></td></tr>
              <tr><td><code>declaude prevent</code></td><td><RichText>{t('docs.cmd.prevent')}</RichText></td></tr>
              <tr><td><code>declaude --version</code></td><td>{t('docs.cmd.version')}</td></tr>
            </tbody>
          </table>
        </div>

        <h2 id="options">{t('nav.options')}</h2>
        <div className="docs-table-wrap">
          <table className="docs-table">
            <thead><tr><th>{t('docs.th.flag')}</th><th>{t('docs.th.desc')}</th></tr></thead>
            <tbody>
              <tr><td><code>-y, --yes</code></td><td>{t('docs.opt.yes')}</td></tr>
              <tr><td><code>--dry-run</code></td><td>{t('docs.opt.dryrun')}</td></tr>
              <tr><td><code>--no-refresh</code></td><td>{t('docs.opt.norefresh')}</td></tr>
              <tr><td><code>--no-backup</code></td><td>{t('docs.opt.nobackup')}</td></tr>
              <tr><td><code>--version</code></td><td>{t('docs.cmd.version')}</td></tr>
            </tbody>
          </table>
        </div>

        <h2 id="requirements">{t('nav.requirements')}</h2>
        <ul>
          <li><RichText>{t('docs.req.li1')}</RichText></li>
          <li><RichText>{t('docs.req.li2')}</RichText></li>
          <li><RichText>{t('docs.req.li3')}</RichText></li>
          <li><RichText>{t('docs.req.li4')}</RichText></li>
        </ul>
        <p><RichText>{t('docs.req.p')}</RichText></p>

        <h2 id="caveats">{t('docs.caveats.h')}</h2>
        <ul>
          <li><RichText>{t('docs.cav.1')}</RichText></li>
          <li><RichText>{t('docs.cav.2')}</RichText></li>
          <li><RichText>{t('docs.cav.3')}</RichText></li>
          <li><RichText>{t('docs.cav.4')}</RichText></li>
          <li><RichText>{t('docs.cav.5')}</RichText></li>
        </ul>

        <h2 id="backup">{t('nav.backup')}</h2>
        <p><RichText>{t('docs.backup.p1')}</RichText></p>
        <pre><code>{SNIPPETS.backup}</code></pre>
        <p><RichText>{t('docs.backup.p2')}</RichText></p>

        <h2 id="prevent">{t('docs.prevent.h')}</h2>
        <pre><code>{SNIPPETS.prevent}</code></pre>
        <p><RichText>{t('docs.prevent.p')}</RichText></p>

        <h2 id="dev">{t('nav.development')}</h2>
        <pre><code>{SNIPPETS.dev}</code></pre>
      </main>
    </div>
  )
}

/* ── app shell ── */
export default function App() {
  const [page, setPage] = useState('home')
  const [lang, setLang] = useState(() => {
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('declaude-lang')
      if (saved && LANGS.some((l) => l.code === saved)) return saved
    }
    return detectLang()
  })

  useEffect(() => {
    if (typeof localStorage !== 'undefined') localStorage.setItem('declaude-lang', lang)
    if (typeof document !== 'undefined') document.documentElement.lang = lang
  }, [lang])

  const ctx = { lang, setLang, t: makeT(lang) }

  return (
    <LangCtx.Provider value={ctx}>
      <nav className="nav">
        <div className="nav-inner">
          <div className="nav-logo" onClick={() => setPage('home')}>
            <span className="lg-de">de</span><span className="lg-claude">claude</span>
          </div>
          <div className="nav-actions">
            <LangPicker />
            <button className="btn btn-primary"
                    onClick={() => setPage(page === 'docs' ? 'home' : 'docs')}>
              {page === 'docs' ? ctx.t('nav.home') : ctx.t('nav.docs')}
            </button>
          </div>
        </div>
      </nav>

      {page === 'home'
        ? <LandingPage onDocs={() => setPage('docs')} />
        : <DocsPage onHome={() => setPage('home')} />}
    </LangCtx.Provider>
  )
}
