import { useState, useEffect } from 'react'
import './App.css'

/* ── copy-to-clipboard button ── */
function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }
  return (
    <button className={`copy-btn${copied ? ' copied' : ''}`} onClick={copy}>
      {copied ? 'copied' : 'copy'}
    </button>
  )
}

/* ── animated contributor-removal demo ── */
function ContributorDemo() {
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

        <div className="demo-toast">@claude removed from this repo</div>
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
  return (
    <>
      <section className="hero">
        <div className="hero-left">
          <div className="badge"><span className="badge-dot" />v0.1.1 · open source</div>
          <h1>
            Remove <span className="strike mark">@claude</span> from your GitHub
          </h1>
          <p className="sub">
            Strip Claude/AI attribution from your entire commit history,
            force-push the clean branches, and flush GitHub's Contributors
            graph cache in one command.
          </p>
          <div className="install-box">
            <span className="prefix">$</span>
            pip install declaude
            <CopyBtn text="pip install declaude" />
          </div>
          <div className="hero-actions">
            <button className="btn btn-primary" onClick={onDocs}>Read the docs &rarr;</button>
            <a className="btn btn-outline" href="https://github.com/ediiloupatty/declaude"
               target="_blank" rel="noopener noreferrer">View on GitHub</a>
          </div>
        </div>
        <div className="hero-right">
          <ContributorDemo />
        </div>
      </section>

      <section className="how">
        <div className="how-inner">
          <div className="how-text">
            <span className="section-label">How it works</span>
            <h2>One command, the full sequence</h2>
            <p>
              GitHub's Contributors graph is a cached view, so a force-push alone
              won't update it. declaude runs the exact order that actually drops
              <code> @claude</code>.
            </p>
            <ul className="flow">
              <li><span className="tick">1</span><span><b>Strip history.</b> Removes every Claude co-author trailer from all commits.</span></li>
              <li><span className="tick">2</span><span><b>Flush cache.</b> Renames the default branch away and back to reset the graph.</span></li>
              <li><span className="tick">3</span><span><b>Recompute.</b> Pushes an empty commit so GitHub rebuilds against clean history.</span></li>
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
        <p>MIT License · built for cleaning up after Claude Code</p>
      </footer>
    </>
  )
}

/* ── docs page (with scroll-spy) ── */
const NAV = [
  { group: 'Getting Started', items: [
    ['install', 'Install'], ['usage', 'Usage'], ['commands', 'Commands'],
  ]},
  { group: 'Reference', items: [
    ['options', 'Options'], ['requirements', 'Requirements'], ['caveats', 'Caveats'],
    ['backup', 'Backup & Restore'], ['prevent', 'Prevent'],
  ]},
  { group: 'Development', items: [
    ['dev', 'Development'],
  ]},
]

function DocsPage({ onHome }) {
  const [active, setActive] = useState('install')

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
            <div className="docs-sidebar-label">{g.group}</div>
            <nav>
              {g.items.map(([id, label]) => (
                <a key={id} href={`#${id}`}
                   className={active === id ? 'active' : ''}
                   onClick={() => setActive(id)}>
                  {label}
                </a>
              ))}
            </nav>
          </div>
        ))}
      </aside>

      <main className="docs-content">
        <button className="btn btn-ghost docs-mobile-back" onClick={onHome}>&larr; Back home</button>

        <h1>declaude</h1>
        <p className="lead">
          Remove Claude/AI attribution from a GitHub repo in one command.
          Strips co-author trailers from commit history, force-pushes clean branches,
          and flushes GitHub's Contributors graph cache so <code>@claude</code> actually disappears.
        </p>

        <h2 id="install">Install</h2>
        <pre><code>pip install declaude</code></pre>
        <p>Not yet on PyPI? Install straight from GitHub:</p>
        <pre><code>pip install git+https://github.com/ediiloupatty/declaude{'\n'}# or, from a local clone:{'\n'}pip install .</code></pre>
        <p>
          <code>pip</code> puts a <code>declaude</code> command on your PATH and
          pulls in <code>git-filter-repo</code> automatically. The one prerequisite
          pip can't install is the <strong>GitHub CLI</strong>, used to flush GitHub's
          Contributors-graph cache:
        </p>
        <pre><code># Windows (winget):{'\n'}winget install GitHub.cli{'\n'}{'\n'}# macOS (Homebrew):{'\n'}brew install gh{'\n'}{'\n'}# Linux: https://cli.github.com/manual/installation</code></pre>
        <div className="callout">
          <strong>Windows note:</strong> after <code>winget install GitHub.cli</code>,
          open a <strong>new terminal</strong> before running <code>gh</code>; the
          current session won't see it yet.
        </div>
        <p>Then log in:</p>
        <pre><code>gh auth login</code></pre>

        <h3>After installing on Windows</h3>
        <p>
          After <code>pip install declaude</code>, pip may warn that the Scripts
          folder isn't on your PATH. Run it like this and it always works:
        </p>
        <pre><code>python -m declaude OWNER/REPO{'\n'}python -m declaude --help</code></pre>
        <p>Prefer the short <code>declaude</code> command? Install with pipx:</p>
        <pre><code>python -m pip install --user pipx{'\n'}python -m pipx ensurepath{'\n'}pipx install declaude</code></pre>

        <h2 id="usage">Usage</h2>
        <pre><code>declaude OWNER/REPO{'\n'}declaude https://github.com/OWNER/REPO{'\n'}{'\n'}declaude my-repo --dry-run     # show the plan, change nothing{'\n'}declaude my-repo -y            # skip the confirmation prompt{'\n'}declaude my-repo --no-refresh  # clean + push only, skip refresh commit{'\n'}declaude my-repo --no-backup   # skip backup bundle (not recommended){'\n'}{'\n'}declaude prevent               # turn off attribution going forward{'\n'}declaude --version             # print the installed version</code></pre>
        <p>
          The repo is cloned to a temp dir, cleaned, force-pushed, refreshed, then
          discarded. You never clone by hand.
        </p>

        <h2 id="commands">Commands</h2>
        <div className="docs-table-wrap">
          <table className="docs-table">
            <thead><tr><th>Command</th><th>Purpose</th></tr></thead>
            <tbody>
              <tr><td><code>declaude TARGET [flags]</code></td><td>Clean history + force-push + refresh contributors graph. TARGET = GitHub URL or OWNER/REPO.</td></tr>
              <tr><td><code>declaude prevent</code></td><td>Set <code>includeCoAuthoredBy:false</code> in <code>~/.claude/settings.json</code>.</td></tr>
              <tr><td><code>declaude --version</code></td><td>Print the installed version.</td></tr>
            </tbody>
          </table>
        </div>

        <h2 id="options">Options</h2>
        <div className="docs-table-wrap">
          <table className="docs-table">
            <thead><tr><th>Flag</th><th>Description</th></tr></thead>
            <tbody>
              <tr><td><code>-y, --yes</code></td><td>Skip the confirmation prompt.</td></tr>
              <tr><td><code>--dry-run</code></td><td>Show the plan only; change nothing.</td></tr>
              <tr><td><code>--no-refresh</code></td><td>Clean + force-push only; skip the branch rename and refresh commit.</td></tr>
              <tr><td><code>--no-backup</code></td><td>Skip the restorable backup bundle (not recommended).</td></tr>
              <tr><td><code>--version</code></td><td>Print the installed version.</td></tr>
            </tbody>
          </table>
        </div>

        <h2 id="requirements">Requirements</h2>
        <ul>
          <li>Python 3.8+ and <code>pip</code></li>
          <li><code>git</code></li>
          <li><code>gh</code> (GitHub CLI, logged in). Install separately from <a href="https://cli.github.com" target="_blank" rel="noopener noreferrer">cli.github.com</a></li>
          <li><code>git-filter-repo</code>, installed automatically as a pip dependency</li>
        </ul>
        <p>
          <strong>Windows:</strong> works in PowerShell and Windows Terminal. ANSI
          colors are enabled automatically; set <code>NO_COLOR=1</code> to disable.
          <code>git</code>, <code>gh</code>, and Python must be on your PATH.
        </p>

        <h2 id="caveats">Honest caveats</h2>
        <ul>
          <li><strong>Claude authorship (rare).</strong> If a commit's author is Claude (not just a co-author), declaude warns but does not change it. Use <code>git filter-repo --mailmap</code> to rewrite authorship.</li>
          <li><strong>The refresh commit.</strong> declaude leaves one <code>chore: refresh GitHub contributors</code> empty commit on the default branch. It's harmless; drop it later with <code>git rebase</code>. Skip with <code>--no-refresh</code>.</li>
          <li><strong>Shared repos.</strong> The flush renames the default branch and back. Collaborators may see GitHub's "default branch renamed" notice. Use <code>--no-refresh</code> if that's a problem.</li>
          <li><strong>Graph lag.</strong> Even after the flush + refresh push, the Contributors graph can take a few minutes to update. Recheck in Incognito.</li>
          <li><strong>Closed pull requests.</strong> GitHub keeps old commits in <code>refs/pull/N/head</code>, which users can't delete. If <code>@claude</code> persists after cleaning, only GitHub Support can purge the PR-ref cache.</li>
        </ul>

        <h2 id="backup">Backup & Restore</h2>
        <p>
          Before any rewrite, a backup bundle is written to{' '}
          <code>~/.declaude-backups/</code> and is fully restorable:
        </p>
        <pre><code>git -C &lt;repo&gt; fetch ~/.declaude-backups/&lt;name&gt;.bundle '*:*'</code></pre>
        <p>Skip the backup with <code>--no-backup</code> (not recommended; you lose the restore point).</p>

        <h2 id="prevent">Prevent future attribution</h2>
        <pre><code>declaude prevent</code></pre>
        <p>
          Sets <code>includeCoAuthoredBy: false</code> in{' '}
          <code>~/.claude/settings.json</code>. Future Claude Code commits and PRs
          won't add an attribution trailer.
        </p>

        <h2 id="dev">Development</h2>
        <pre><code>pip install -e ".[dev]"   # editable install with test deps{'\n'}python -m pytest          # run the scrubber tests{'\n'}python -m declaude --help # run without installing the console script</code></pre>
      </main>
    </div>
  )
}

/* ── app shell ── */
export default function App() {
  const [page, setPage] = useState('home')

  return (
    <>
      <nav className="nav">
        <div className="nav-inner">
          <div className="nav-logo" onClick={() => setPage('home')}>
            <span className="lg-de">de</span><span className="lg-claude">claude</span>
          </div>
          <div className="nav-actions">
            <button className="btn btn-primary"
                    onClick={() => setPage(page === 'docs' ? 'home' : 'docs')}>
              {page === 'docs' ? 'Home' : 'Docs'}
            </button>
          </div>
        </div>
      </nav>

      {page === 'home'
        ? <LandingPage onDocs={() => setPage('docs')} />
        : <DocsPage onHome={() => setPage('home')} />}
    </>
  )
}
