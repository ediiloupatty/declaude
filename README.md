# declaude

**Detect & remove Claude/AI attribution from git repositories** — strip traces
like `Co-Authored-By: Claude <noreply@anthropic.com>` or _"Generated with Claude
Code"_ lines from your **entire commit history**, **without touching your code**
or your **commit authorship**.

Built from real-world repo cleanups, so it already handles the traps that
usually cause trouble:

- 🔒 **Preserves uncommitted changes (WIP)** — backed up, then restored.
- 🌿 **Multi-branch repos** — force-pushes **every** affected branch, not just `main`.
- 💾 **Off-repo bundle backup** before rewriting (fully restorable).
- 🙈 **A token embedded in the remote URL is never printed.**
- ✅ **Server-side verification** via `gh` after pushing.

## Why does `@claude` show up in GitHub Contributors?

AI tools often append a `Co-Authored-By: Claude …` trailer to commit messages.
GitHub builds the **Contributors graph from commit messages on the default
branch**, so as long as that trailer exists in history, `@claude` stays listed.
Removing it requires a **history rewrite + force-push** — exactly what
`declaude clean` does.

## Install

```bash
# prerequisites
pipx install git-filter-repo      # or: pip install --user git-filter-repo
# gh (GitHub CLI) is optional — for account scans & server verification

# install declaude
git clone https://github.com/ediiloupatty/declaude ~/declaude && ~/declaude/install.sh
# or, from the project folder:
./install.sh
```

`install.sh` symlinks `declaude` into `~/.local/bin`.

## Usage

```bash
# 1) See which repos contain Claude traces (READ-ONLY, safe)
declaude scan ~/project            # scan all repos under a folder
declaude scan ~/project --branches # break down per branch

# 2) Preview the plan for one repo without changing anything
declaude clean ~/project/app --dry-run

# 3) Clean local history only (no push)
declaude clean ~/project/app

# 4) Clean + force-push every affected branch to GitHub
declaude clean ~/project/app --push

# 5) Prevent recurrence: turn off Claude Code attribution going forward
declaude prevent
```

Every `clean` first writes a **backup bundle** to `~/.declaude-backups/`.
Restore at any time:

```bash
git -C <repo> fetch ~/.declaude-backups/<name>.bundle '*:*'
```

## Honest caveats

- **Claude authorship (rare).** If a commit's _author_ is Claude (not just a
  co-author), `declaude` warns but does not change it — use
  `git filter-repo --mailmap` to rewrite authorship.
- **Closed pull requests.** GitHub keeps old commits in `refs/pull/N/head`,
  which **users cannot delete**. The Contributors graph is computed from the
  default branch (clean after `clean --push`), so `@claude` should still
  disappear; if it lingers, only GitHub Support can purge the PR-ref cache.
- **GitHub UI cache.** After `clean --push`, `@claude` may linger briefly in the
  UI due to caching. The force-push already triggers a regen; check in Incognito.

## Commands

| Command | Purpose |
|---|---|
| `declaude scan [PATH] [--branches] [--depth N]` | Find repos & report traces (read-only). |
| `declaude clean REPO [--push] [--yes] [--dry-run] [--backup-dir DIR]` | Rewrite history + (optionally) push. |
| `declaude prevent` | Set `includeCoAuthoredBy:false` in `~/.claude/settings.json`. |

## Requirements

- `git`
- `git-filter-repo` (for `clean`)
- `gh` (optional — GitHub account scans & server verification)
- Python 3.8+
