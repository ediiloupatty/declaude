#!/usr/bin/env python3
"""
declaude — detect & remove Claude/AI attribution from git repositories.

Strips traces left by AI tools (e.g. "Co-Authored-By: Claude
<noreply@anthropic.com>" or "Generated with Claude Code" lines) from the ENTIRE
commit history, without touching your code or your commit authorship.

Subcommands:
  scan    — (read-only) find git repos and report Claude traces per repo/branch.
  clean   — rewrite a repo's history to strip traces (git-filter-repo), keep a
            backup, optionally force-push every affected branch.
  prevent — set "includeCoAuthoredBy": false in ~/.claude/settings.json.

Designed from real-world repo cleanups, so it already handles the usual traps:
  • preserves uncommitted changes (WIP) — backed up then restored,
  • multi-branch repos — pushes ALL affected branches, not just main,
  • off-repo bundle backup before rewriting (fully restorable),
  • a token embedded in the remote URL is never printed,
  • server-side verification via `gh` after pushing.

Requires: git, git-filter-repo (for `clean`), and gh (optional, for server
verification and GitHub account scans).
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

# Commit-message lines considered a "Claude trace".
DETECT_RE = re.compile(
    r"(co-authored-by:.*(claude|anthropic))|(generated with claude)|(noreply@anthropic)",
    re.IGNORECASE,
)

# Function body for `git filter-repo --message-callback`. Receives `message`
# (bytes), returns bytes. Drops Claude/anthropic co-author lines and
# "Generated with Claude Code" lines, then collapses extra blank lines.
SCRUB_CALLBACK = (
    "import re\n"
    "text = message.decode('utf-8', 'replace')\n"
    "out = []\n"
    "for line in text.split('\\n'):\n"
    "    low = line.strip().lower()\n"
    "    if low.startswith('co-authored-by:') and ('claude' in low or 'anthropic' in low):\n"
    "        continue\n"
    "    if 'generated with claude code' in low:\n"
    "        continue\n"
    "    if low.startswith('\U0001f916 generated with') or low.startswith('generated with claude'):\n"
    "        continue\n"
    "    out.append(line)\n"
    "result = re.sub(r'\\n{3,}', '\\n\\n', '\\n'.join(out)).rstrip('\\n') + '\\n'\n"
    "return result.encode('utf-8')\n"
)

# ── tiny color helpers ────────────────────────────────────────────────────────
C = {
    "g": "\033[32m", "r": "\033[31m", "y": "\033[33m",
    "c": "\033[36m", "d": "\033[90m", "b": "\033[1m", "x": "\033[0m",
}
if not sys.stdout.isatty() or os.getenv("NO_COLOR"):
    C = {k: "" for k in C}


def col(s: str, k: str) -> str:
    return f"{C[k]}{s}{C['x']}"


def info(msg: str) -> None:
    print(f"  {msg}")


def die(msg: str, code: int = 1):
    print(col(f"✗ {msg}", "r"), file=sys.stderr)
    sys.exit(code)


# ── process helpers ───────────────────────────────────────────────────────────
def run(cmd, cwd=None, check=False, capture=True):
    """Run a command; return (rc, stdout). Never raises unless check=True."""
    res = subprocess.run(
        cmd, cwd=cwd, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    if check and res.returncode != 0:
        die(f"command failed: {' '.join(cmd)}\n{res.stdout or ''}")
    return res.returncode, (res.stdout or "")


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def git(repo: str, *args, check=False, capture=True):
    return run(["git", "-C", repo, *args], check=check, capture=capture)


# ── repo & trace detection ────────────────────────────────────────────────────
def find_repos(root: str, max_depth: int = 5) -> list[str]:
    """Find every git working tree under `root` (by locating .git)."""
    root = os.path.abspath(root)
    repos = []
    root_depth = root.rstrip("/").count("/")
    for dirpath, dirnames, _ in os.walk(root):
        if dirpath.count("/") - root_depth > max_depth:
            dirnames[:] = []
            continue
        if ".git" in dirnames or os.path.isfile(os.path.join(dirpath, ".git")):
            repos.append(dirpath)
            # don't descend into .git, but keep scanning for nested repos
            if ".git" in dirnames:
                dirnames.remove(".git")
    return sorted(repos)


def remote_slug(repo: str) -> str | None:
    """OWNER/REPO from the origin remote (None if not github / missing)."""
    rc, url = git(repo, "remote", "get-url", "origin")
    if rc != 0 or "github.com" not in url:
        return None
    slug = re.sub(r"\.git\s*$", "", url.strip())
    slug = re.sub(r"^.*github\.com[/:]", "", slug)
    return slug or None


def local_branches(repo: str) -> list[str]:
    rc, out = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    return [b for b in out.split("\n") if b.strip()] if rc == 0 else []


def remote_branches(repo: str) -> list[str]:
    rc, out = git(repo, "ls-remote", "--heads", "origin")
    if rc != 0:
        return []
    return [ln.split("refs/heads/", 1)[1] for ln in out.split("\n") if "refs/heads/" in ln]


def count_hits(repo: str, ref: str = "--all") -> int:
    """Number of commits containing a Claude trace on `ref` (or all refs)."""
    rc, out = git(
        repo, "log", ref, "-i", "-E",
        "--grep=co-authored-by:.*(claude|anthropic)",
        "--grep=generated with claude", "--format=%H",
    )
    return len([h for h in out.split("\n") if h.strip()]) if rc == 0 else 0


def author_hits(repo: str) -> int:
    """Commits whose AUTHOR/COMMITTER is Claude/anthropic (rare, more serious)."""
    rc, out = git(repo, "log", "--all", "--format=%an <%ae>|%cn <%ce>")
    if rc != 0:
        return 0
    return len([ln for ln in out.split("\n") if re.search(r"claude|anthropic", ln, re.I)])


def is_dirty(repo: str) -> int:
    rc, out = git(repo, "status", "--porcelain")
    return len([ln for ln in out.split("\n") if ln.strip()]) if rc == 0 else 0


# ── scan ──────────────────────────────────────────────────────────────────────
def default_branch_hits(slug: str) -> int:
    """Traced commits on a repo's default branch (via gh). -1 if unreadable/empty."""
    rc, o = run(["gh", "api", f"repos/{slug}/commits", "--paginate", "--jq",
                 '[.[]|select(.commit.message|test("(?i)co-authored-by:.*(claude|anthropic)|generated with claude"))]|length'])
    if rc != 0:
        return -1
    return sum(int(x) for x in o.split("\n") if x.strip().lstrip("-").isdigit())


def scan_user(user: str):
    """Scan every repo of a GitHub account server-side (default branch)."""
    if not have("gh"):
        die("scan --user requires the GitHub CLI 'gh' (and `gh auth login`).")
    rc, out = run(["gh", "repo", "list", user, "--limit", "1000",
                   "--json", "nameWithOwner", "--jq", ".[].nameWithOwner"])
    if rc != 0:
        die(f"failed to list repos for {user}:\n{out}")
    slugs = [s for s in out.split("\n") if s.strip()]
    if not slugs:
        info(f"no repositories found for {user}.")
        return
    print(col(f"\nScanning {len(slugs)} repo(s) for @{user} (server-side, default branch)\n", "b"))
    dirty = 0
    for slug in slugs:
        n = default_branch_hits(slug)
        if n < 0:
            tag = col("empty/—", "d")
        elif n == 0:
            tag = col("CLEAN", "g")
        else:
            tag = col(f"{n} co-author", "y")
            dirty += 1
        print(f"  {tag:>22}  {col(slug, 'c')}")
    print()
    if dirty:
        print(col(f"{dirty} repo(s) contain Claude traces on their default branch.", "y"))
        print("Clone + clean each, e.g.:",
              col("gh repo clone <slug> && declaude clean <slug> --push", "b"))
    else:
        print(col("All repositories are clean. 🎉", "g"))


def cmd_scan(args):
    if args.user:
        return scan_user(args.user)
    root = args.path or os.getcwd()
    if not os.path.isdir(root):
        die(f"folder not found: {root}")
    repos = find_repos(root, args.depth)
    if not repos:
        info("no git repositories found.")
        return
    print(col(f"\nScanning {len(repos)} repo(s) under {root}\n", "b"))
    dirty_total = 0
    for repo in repos:
        rel = os.path.relpath(repo, root)
        slug = remote_slug(repo)
        hits = count_hits(repo)
        ah = author_hits(repo)
        tag = col("CLEAN", "g") if hits == 0 and ah == 0 else col(f"{hits} co-author"
                  + (f", {ah} author" if ah else ""), "y")
        loc = slug or col("(local/non-github)", "d")
        print(f"  {tag:>22}  {col(rel, 'c')}  {col(loc, 'd')}")
        if hits or ah:
            dirty_total += 1
            if args.branches:
                for b in local_branches(repo):
                    n = count_hits(repo, b)
                    if n:
                        print(f"        └ {b}: {n}")
    print()
    if dirty_total:
        print(col(f"{dirty_total} repo(s) contain Claude traces.", "y"),
              "Clean with:", col("declaude clean <repo-path> --push", "b"))
    else:
        print(col("All repositories are clean. 🎉", "g"))


# ── clean ─────────────────────────────────────────────────────────────────────
def backup_repo(repo: str, backup_dir: str) -> tuple[str, str | None]:
    """Create a bundle of all refs + (if dirty) a WIP archive. Return (bundle, wip)."""
    os.makedirs(backup_dir, exist_ok=True)
    name = os.path.basename(os.path.abspath(repo)) or "repo"
    ts = time.strftime("%Y%m%d-%H%M%S")
    bundle = os.path.join(backup_dir, f"{name}-{ts}.bundle")
    rc, out = git(repo, "bundle", "create", bundle, "--all")
    if rc != 0:
        die(f"failed to create backup bundle:\n{out}")
    wip = None
    if is_dirty(repo):
        # changed files (tracked + untracked, non-deleted)
        _, d1 = git(repo, "diff", "--name-only", "HEAD")
        _, d2 = git(repo, "ls-files", "--others", "--exclude-standard")
        files = sorted({f for f in (d1 + "\n" + d2).split("\n")
                        if f.strip() and os.path.exists(os.path.join(repo, f))})
        if files:
            wip = os.path.join(backup_dir, f"{name}-{ts}-WIP.tar.gz")
            with tarfile.open(wip, "w:gz") as t:
                for f in files:
                    t.add(os.path.join(repo, f), arcname=f)
    return bundle, wip


def cmd_clean(args):
    repo = os.path.abspath(args.repo)
    if not os.path.isdir(os.path.join(repo, ".git")) and not os.path.isfile(os.path.join(repo, ".git")):
        die(f"not a git repo: {repo}")
    if not have("git-filter-repo"):
        die("git-filter-repo is not installed. Install: pipx install git-filter-repo "
            "(or pip install --user git-filter-repo)")

    hits = count_hits(repo)
    ah = author_hits(repo)
    if hits == 0 and ah == 0:
        info(col("Repo is already clean — no Claude traces.", "g"))
        return
    slug = remote_slug(repo)
    affected = [b for b in local_branches(repo) if count_hits(repo, b)]
    rbranches = set(remote_branches(repo)) if slug else set()

    print(col(f"\nRepo   : {repo}", "b"))
    print(f"  remote : {slug or '(none / non-github)'}")
    print(f"  traces : {col(str(hits), 'y')} co-author commit(s)"
          + (f", {col(str(ah),'y')} Claude author/committer" if ah else ""))
    print(f"  affected branches (local): {', '.join(affected) or '-'}")
    if ah:
        print(col("  ⚠ some commits have a Claude AUTHOR — declaude only cleans "
                  "message trailers, NOT authorship. Use git-filter-repo --mailmap for that.", "y"))
    if args.dry_run:
        print(col("\n[dry-run] nothing changed. Drop --dry-run to execute.", "c"))
        return
    if not args.yes:
        print(col("\nThis REWRITES history (all SHAs change)"
                  + (" and then FORCE-PUSHES." if args.push else "."), "y"))
        if input("  Continue? type 'yes': ").strip().lower() not in ("yes", "y"):
            die("aborted.", 0)

    # 1) backup
    bundle, wip = backup_repo(repo, args.backup_dir)
    info(f"backup bundle: {col(bundle, 'd')}")
    if wip:
        info(f"backup WIP   : {col(wip, 'd')}")

    # 2) remember the origin URL (may contain a token — NOT printed)
    _, origin_url = git(repo, "remote", "get-url", "origin")
    origin_url = origin_url.strip()

    # 3) rewrite
    info("rewriting history (git filter-repo)…")
    rc, out = run(["git", "filter-repo", "--force", "--message-callback", SCRUB_CALLBACK],
                  cwd=repo)
    if rc != 0:
        die(f"filter-repo failed:\n{out}\n\nRestore from bundle:\n"
            f"  git -C {repo} fetch {bundle} '*:*'")
    # filter-repo drops origin → re-add it
    if origin_url:
        git(repo, "remote", "remove", "origin")
        git(repo, "remote", "add", "origin", origin_url)

    # 4) restore WIP
    if wip:
        with tarfile.open(wip, "r:gz") as t:
            t.extractall(repo)
        info("WIP restored.")

    left = count_hits(repo)
    if left:
        die(f"still {left} trace(s) after rewrite — check manually.")
    info(col("local history is clean (0 traces).", "g"))

    # 5) push
    if not args.push:
        print(col("\nLocal is clean. Not pushed yet (add --push to push to GitHub).", "c"))
        return
    if not slug:
        info("no github remote — skipping push.")
        return
    push_branches = [b for b in affected if b in rbranches] or \
                    [b for b in local_branches(repo) if b in rbranches]
    info(f"force-pushing branches: {', '.join(push_branches)}")
    for b in push_branches:
        rc, out = git(repo, "push", "origin", b, "--force", capture=True)
        ok = "forced update" in out or "->" in out
        print(f"    {col('✓','g') if ok else col('✗','r')} {b}")
    # server verification (if gh is available)
    if have("gh"):
        n = server_hits(slug)
        print(col(f"\nServer {slug}: {n} traced commit(s) across all branches.",
                  "g" if n == 0 else "y"))
        if n == 0:
            print(col("Done. Check the repo page in Incognito; @claude will drop "
                      "once GitHub regenerates contributors.", "g"))
    else:
        info("(install `gh` for automatic server-side verification)")


def server_hits(slug: str) -> int:
    """Total traced commits across all branches of a repo (via gh)."""
    rc, out = run(["gh", "api", f"repos/{slug}/branches", "--jq", ".[].name"])
    if rc != 0:
        return -1
    total = 0
    for b in [x for x in out.split("\n") if x.strip()]:
        rc, o = run(["gh", "api", f"repos/{slug}/commits?sha={b}", "--paginate",
                     "--jq", '[.[]|select(.commit.message|test("(?i)co-authored-by:.*(claude|anthropic)"))]|length'])
        if rc == 0:
            total += sum(int(x) for x in o.split("\n") if x.strip().isdigit())
    return total


# ── prevent ───────────────────────────────────────────────────────────────────
def cmd_prevent(args):
    import json
    path = Path(os.path.expanduser("~/.claude/settings.json"))
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except Exception:
            die(f"failed to read {path} (invalid JSON).")
    if data.get("includeCoAuthoredBy") is False:
        info(col("Already set: includeCoAuthoredBy=false.", "g"))
        return
    data["includeCoAuthoredBy"] = False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    info(col(f"Set includeCoAuthoredBy=false in {path}.", "g"))
    info("Future Claude Code commits/PRs won't add an attribution trailer.")


# ── cli ───────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        prog="declaude",
        description="Detect & remove Claude/AI attribution from git repositories.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="find repos + report Claude traces (read-only)")
    s.add_argument("path", nargs="?", help="root folder (default: cwd)")
    s.add_argument("--user", help="scan a GitHub account's repos server-side (needs gh)")
    s.add_argument("--branches", action="store_true", help="break down per branch (local scan)")
    s.add_argument("--depth", type=int, default=5, help="repo search depth (local scan)")
    s.set_defaults(func=cmd_scan)

    c = sub.add_parser("clean", help="rewrite a repo's history & (optionally) push")
    c.add_argument("repo", help="path to the git repo")
    c.add_argument("--push", action="store_true", help="force-push affected branches")
    c.add_argument("--yes", action="store_true", help="skip confirmation")
    c.add_argument("--dry-run", action="store_true", help="show the plan only")
    c.add_argument("--backup-dir", default=os.path.expanduser("~/.declaude-backups"),
                   help="folder for backup bundles + WIP")
    c.set_defaults(func=cmd_clean)

    pr = sub.add_parser("prevent", help="set includeCoAuthoredBy=false (prevent recurrence)")
    pr.set_defaults(func=cmd_prevent)

    args = p.parse_args()
    if not have("git"):
        die("git not found in PATH.")
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        die("aborted.", 130)
