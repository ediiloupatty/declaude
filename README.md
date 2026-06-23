# declaude

**Remove Claude/AI attribution from a GitHub repo in one command.**

```bash
declaude OWNER/REPO
```

It clones the repo, strips Claude/AI traces from your **entire commit history**
(e.g. `Co-Authored-By: Claude <noreply@anthropic.com>` or _"Generated with
Claude Code"_), force-pushes the cleaned branches, and **refreshes GitHub's
Contributors graph** so `@claude` actually disappears — all without touching your
code or your commit authorship.

## Why `@claude` won't go away by itself

AI tools append a `Co-Authored-By: Claude …` trailer to commits, and GitHub's
**Insights → Contributors graph** counts those co-authors. That graph is a
**cached, background-computed view** — a force-push (or a flush, or a commit)
*on its own* doesn't reliably update it, so `@claude` lingers even after the
history and the REST API are clean.

What actually works is a specific **order**:

> **remove Claude → flush (rename the default branch) → push a fresh commit**

The flush resets GitHub's cached graph; the following commit triggers a
recompute against the now-clean history. `declaude` does all three for you (the
refresh commit is `chore: refresh GitHub contributors`, reusing your latest
commit's author so no new identity appears). It runs **even when the history is
already clean**, which is exactly what a previously-cleaned repo needs.

## Install

```bash
pip install declaude        # installs the `declaude` command + git-filter-repo
```

Not yet on PyPI? Install straight from GitHub:

```bash
pip install git+https://github.com/ediiloupatty/declaude
# or, from a local clone:
pip install .
```

`pip` puts a `declaude` command on your PATH and pulls in `git-filter-repo`
automatically — no manual setup. The one prerequisite pip can't install is the
**GitHub CLI**, used to flush GitHub's Contributors-graph cache:

```bash
# Windows (winget):
winget install GitHub.cli

# macOS (Homebrew):
brew install gh

# Linux: https://cli.github.com/manual/installation
```

> **Windows note:** after `winget install GitHub.cli`, **open a new terminal** before running `gh` — the current session won't see it yet.

Then log in:

```bash
gh auth login
```

declaude checks for `gh` and a valid login up front and tells you exactly what's
missing before it touches anything.

### After installing on Windows — how to run it

After `pip install declaude`, pip may print a warning that the `Scripts` folder
**isn't on your PATH**. That's normal and harmless — it only means typing
`declaude` directly might say *"command not found"*. Just run it like this and it
always works:

```cmd
python -m declaude OWNER/REPO
```

That's the whole trick: put `python -m` in front. For example:

```cmd
python -m declaude ediiloupatty/my-repo
python -m declaude --help
```

Prefer the short `declaude` command? Either install with **pipx**, which sets up
PATH for you:

```cmd
python -m pip install --user pipx
python -m pipx ensurepath
pipx install declaude
```

…or run the included `install.ps1` from a clone of this repo (it adds the
`Scripts` folder to your PATH automatically):

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -FromPyPI
```

Then **open a new terminal** and `declaude` works on its own.

## Usage

Run `declaude --help` (or `python -m declaude --help` on Windows) any time to
see the full reference:

```text
usage: declaude [-h] [--version] [-y] [--dry-run] [--no-refresh] [--no-backup]
                target

Remove Claude/AI attribution from a GitHub repo (clean history + force-push +
refresh Contributors graph).

positional arguments:
  target        GitHub URL or OWNER/REPO slug

options:
  -h, --help    show this help message and exit
  --version     show program's version number and exit
  -y, --yes     skip confirmation
  --dry-run     show the plan only
  --no-refresh  don't push the empty commit that refreshes the contributors
                graph
  --no-backup   skip the restorable backup bundle before rewriting (not
                recommended)

Other: `declaude prevent` turns off Claude Code attribution going forward.
```

Examples:

```bash
declaude ediiloupatty/my-repo                      # OWNER/REPO slug
declaude https://github.com/ediiloupatty/my-repo   # full GitHub URL

declaude my-repo --dry-run    # show the plan, change nothing
declaude my-repo -y           # skip the confirmation prompt
declaude my-repo --no-refresh # clean + push only, skip the refresh commit
declaude my-repo --no-backup  # skip the restorable backup bundle (not recommended)

declaude prevent              # turn off Claude Code attribution going forward
declaude --version            # print the installed version
```

The repo is cloned to a temp dir, cleaned, force-pushed, refreshed, then
discarded — you never clone by hand. Before any rewrite, a **backup bundle** is
written to `~/.declaude-backups/` and is fully restorable:

```bash
git -C <repo> fetch ~/.declaude-backups/<name>.bundle '*:*'
```

## Honest caveats

- **Claude authorship (rare).** If a commit's _author_ is Claude (not just a
  co-author), `declaude` warns but does not change it — use
  `git filter-repo --mailmap` to rewrite authorship.
- **The refresh commit.** declaude leaves one `chore: refresh GitHub contributors`
  empty commit on the default branch (authored as you). It's harmless; drop it
  later with `git rebase` if you like. Skip the whole refresh with `--no-refresh`.
- **Shared repos.** The flush renames the default branch and back. Collaborators
  with a local clone may see GitHub's "default branch renamed" notice. Use
  `--no-refresh` if that's a problem.
- **Graph lag.** Even after the flush + refresh push, the Contributors graph can
  take a few minutes to update. Recheck in Incognito.
- **Closed pull requests.** GitHub keeps old commits in `refs/pull/N/head`, which
  users can't delete. The Contributors graph is computed from the default branch
  (clean + refreshed), so `@claude` should still drop; if it persists, only
  GitHub Support can purge the PR-ref cache.

## Commands

| Command | Purpose |
|---|---|
| `declaude TARGET [-y] [--dry-run] [--no-refresh] [--no-backup]` | Clean history + force-push + refresh contributors graph. `TARGET` = GitHub URL or `OWNER/REPO`. |
| `declaude prevent` | Set `includeCoAuthoredBy:false` in `~/.claude/settings.json`. |
| `declaude --version` | Print the installed version. |

## Requirements

- Python 3.8+ and `pip`
- `git`
- `gh` (GitHub CLI, logged in) — install separately from <https://cli.github.com>
- `git-filter-repo` — installed automatically as a pip dependency

**Windows:** works in PowerShell and Windows Terminal (ANSI colors are enabled
automatically; set `NO_COLOR=1` to disable). `git`, `gh`, and Python must be on
your `PATH`.

## Development

```bash
pip install -e ".[dev]"   # editable install with test deps
python -m pytest          # run the scrubber tests
python -m declaude --help # run without installing the console script
```

## License

[MIT](LICENSE) © ediiloupatty
