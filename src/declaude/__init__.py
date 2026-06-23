#!/usr/bin/env python3
"""
declaude — remove Claude/AI attribution from a GitHub repository.

One command does everything needed to get @claude off a repo:

    declaude OWNER/REPO            # or a full GitHub URL

It clones the repo, strips Claude/AI traces from the ENTIRE commit history
(e.g. "Co-Authored-By: Claude <noreply@anthropic.com>" or "Generated with
Claude Code"), force-pushes the cleaned branches, then refreshes GitHub's
Contributors graph in the order that actually works:

    remove Claude  →  FLUSH (rename the default branch)  →  push a fresh commit

Neither the flush nor the commit alone updates the cached graph; doing the flush
first (to reset the cache) and THEN pushing a commit (to trigger the recompute
against the clean history) is what makes @claude finally drop.

It runs even when the history is already clean: in that case it just does the
flush + refresh commit, which is exactly what a previously-cleaned repo needs.

Also:
    declaude path                 # add declaude's install dir to PATH (so `declaude` runs)
    declaude prevent              # stop Claude Code adding the trailer going forward

Requires: git and gh (GitHub CLI, logged in). git-filter-repo ships as a
dependency, so a plain `pip install declaude` is enough.
"""
from __future__ import annotations

import argparse
import inspect
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

__version__ = "0.1.2"

# Commit-message text considered a "Claude trace".
DETECT_RE = re.compile(
    r"(co-authored-by:.*(claude|anthropic))|(generated with claude)|(noreply@anthropic)",
    re.IGNORECASE,
)


def scrub_message(message: bytes) -> bytes:
    """Strip Claude/AI traces from a single commit message (bytes -> bytes).

    Drops Claude/anthropic co-author lines and "Generated with Claude Code"
    lines (whether on their own line or appended inline to another line), then
    collapses extra blank lines. Kept consistent with DETECT_RE, which matches
    traces anywhere. This is the single source of truth: it is unit-tested
    directly AND its source is reused verbatim as the git-filter-repo callback
    (see SCRUB_CALLBACK), so the two can never drift apart.
    """
    import re
    text = message.decode("utf-8", "replace")
    out = []
    for line in text.split("\n"):
        low = line.strip().lower()
        if low.startswith("co-authored-by:") and ("claude" in low or "anthropic" in low):
            continue
        if low.startswith("🤖 generated with") or low.startswith("generated with claude"):
            continue
        line = re.sub(r"(?i)\s*co-authored-by:\s*[^\n]*(?:claude|anthropic)[^\n]*$", "", line)
        line = re.sub(r"(?i)\s*🤖?\s*generated with claude(?: code)?[^\n]*", "", line)
        line = re.sub(r"(?i)\s*<?noreply@anthropic\.com>?", "", line)
        if low and not line.strip():
            continue
        out.append(line)
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).rstrip("\n") + "\n"
    return result.encode("utf-8")


# Body for `git filter-repo --message-callback`. Reuses scrub_message's exact
# source (so the tested function and the callback are byte-for-byte identical),
# then calls it on the `message` the callback receives.
SCRUB_CALLBACK = inspect.getsource(scrub_message) + "return scrub_message(message)\n"

BACKUP_DIR = os.path.expanduser("~/.declaude-backups")

# ── tiny color helpers ────────────────────────────────────────────────────────
if sys.platform == "win32":
    os.system("")  # enable ANSI escape processing on Windows 10+ terminals

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
def run(cmd, cwd=None, capture=True):
    """Run a command; return (rc, stdout). Never raises."""
    res = subprocess.run(
        cmd, cwd=cwd, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    return res.returncode, (res.stdout or "")


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def gh_authed() -> bool:
    """True if `gh` is installed and logged in to github.com."""
    if not have("gh"):
        return False
    rc, _ = run(["gh", "auth", "status"])
    return rc == 0


def git(repo: str, *args, capture=True):
    return run(["git", "-C", repo, *args], capture=capture)


# ── trace detection ───────────────────────────────────────────────────────────
def count_hits(repo: str, ref: str = "--all") -> int:
    """Commits containing a Claude trace on `ref` (or all refs)."""
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


def local_branches(repo: str) -> list[str]:
    rc, out = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    return [b for b in out.split("\n") if b.strip()] if rc == 0 else []


def remote_branches(repo: str) -> list[str]:
    rc, out = git(repo, "ls-remote", "--heads", "origin")
    if rc != 0:
        return []
    return [ln.split("refs/heads/", 1)[1] for ln in out.split("\n") if "refs/heads/" in ln]


# ── target → clone ────────────────────────────────────────────────────────────
def normalize_remote(target: str) -> tuple[str | None, str | None]:
    """Return (clone_url, slug) for a GitHub URL or OWNER/REPO slug, else (None, None)."""
    t = target.strip().rstrip("/")
    if re.match(r"^(https?://|git@|ssh://)", t):
        m = re.search(r"github\.com[/:]([\w.-]+/[\w.-]+?)(?:\.git)?$", t)
        return t, (m.group(1) if m else None)
    if re.match(r"^[\w-][\w.-]*/[\w.-]+$", t):
        return f"https://github.com/{t}.git", t
    return None, None


def materialize_branches(repo: str) -> None:
    """Create a local branch for every remote head so clean + push cover them all."""
    _, cur = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    cur = cur.strip()
    for b in remote_branches(repo):
        if b != cur:
            git(repo, "branch", "--force", b, f"origin/{b}")


def clone_target(url: str, slug: str | None) -> tuple[str, str]:
    """Clone a remote into a temp dir. Returns (repo_path, tmpdir)."""
    tmp = tempfile.mkdtemp(prefix="declaude-")
    dest = os.path.join(tmp, (slug or "repo").split("/")[-1])
    info(f"cloning {col(slug or url, 'c')} …")
    if have("gh") and slug:
        rc, out = run(["gh", "repo", "clone", slug, dest, "--", "--no-single-branch"])
    else:
        rc, out = run(["git", "clone", "--no-single-branch", url, dest])
    if rc != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        die(f"clone failed:\n{out}")
    materialize_branches(dest)
    return dest, tmp


def backup_bundle(repo: str, name: str) -> str:
    """Bundle all refs to BACKUP_DIR (fully restorable). Returns the path."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    bundle = os.path.join(BACKUP_DIR, f"{name}-{ts}.bundle")
    rc, out = git(repo, "bundle", "create", bundle, "--all")
    if rc != 0:
        die(f"failed to create backup bundle:\n{out}")
    return bundle


# ── server-side (gh) ──────────────────────────────────────────────────────────
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


def _branch_rename(slug: str, old: str, new: str) -> tuple[int, str]:
    return run(["gh", "api", "-X", "POST",
                f"repos/{slug}/branches/{old}/rename", "-f", f"new_name={new}"])


def _branch_exists(slug: str, name: str) -> bool:
    rc, _ = run(["gh", "api", f"repos/{slug}/branches/{name}"])
    return rc == 0


def _default_branch(slug: str) -> str | None:
    rc, out = run(["gh", "api", f"repos/{slug}", "--jq", ".default_branch"])
    return out.strip() if rc == 0 and out.strip() else None


def flush_cache(slug: str) -> bool:
    """Flush GitHub's cached Contributors graph by renaming the default branch
    away and back. On its own this isn't enough — but doing it BEFORE pushing a
    fresh commit is what makes the recompute pick up the cleaned history (the
    flush resets the cache, the following commit triggers the rebuild).
    Non-destructive: the branch ends up with its original name. Needs gh.
    """
    if not have("gh"):
        info("(install `gh` to flush GitHub's contributor cache)")
        return False
    default = _default_branch(slug)
    if not default:
        info(col("could not read default branch — skipping cache flush.", "y"))
        return False
    tmp = f"{default}-cflushtmp"
    info(f"flushing contributor cache (rename {default} → {tmp} → {default})…")

    # Clear any leftover temp branch from a previous interrupted run.
    if _branch_exists(slug, tmp):
        run(["gh", "api", "-X", "DELETE", f"repos/{slug}/git/refs/heads/{tmp}"])
        time.sleep(1)

    rc, out = _branch_rename(slug, default, tmp)
    if rc != 0:
        info(col(f"  rename to temp failed: {out.strip()[:140]}", "y"))
        return False
    # Let GitHub's branch index settle, then rename back (retry through the lag
    # that otherwise yields a spurious 422 "branch already exists").
    time.sleep(2)
    for _ in range(5):
        rc, _o = _branch_rename(slug, tmp, default)
        if rc == 0:
            break
        time.sleep(2)

    # Reconcile to the invariant {default name is the default branch, tmp gone}.
    # Idempotent ops that don't hit the rename race, run unconditionally.
    if _branch_exists(slug, tmp) and not _branch_exists(slug, default):
        _branch_rename(slug, tmp, default)
    run(["gh", "api", "-X", "PATCH", f"repos/{slug}", "-f", f"default_branch={default}"])
    run(["gh", "api", "-X", "DELETE", f"repos/{slug}/git/refs/heads/{tmp}"])

    for _ in range(5):
        if _default_branch(slug) == default:
            info(col("contributor cache flushed.", "g"))
            return True
        time.sleep(2)
    info(col(f"  ⚠ flush left an inconsistent state. Fix manually:\n"
             f"      gh api -X PATCH repos/{slug} -f default_branch={default}\n"
             f"      gh api -X DELETE repos/{slug}/git/refs/heads/{tmp}", "y"))
    return False


def refresh_contributors(repo: str) -> bool:
    """Push an empty commit to the default branch. Run AFTER flush_cache: the
    flush resets GitHub's cached Contributors graph, and this fresh push is what
    triggers the recompute against the cleaned history (so @claude drops).
    The commit reuses the latest commit's author, so no new identity appears.
    """
    _, branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch.strip()
    _, an = git(repo, "log", "-1", "--format=%an")
    _, ae = git(repo, "log", "-1", "--format=%ae")
    info(f"refreshing contributors graph (empty commit on {branch})…")
    rc, out = git(repo, "-c", f"user.name={an.strip()}", "-c", f"user.email={ae.strip()}",
                  "commit", "--allow-empty", "-m", "chore: refresh GitHub contributors")
    if rc != 0:
        info(col(f"  could not create refresh commit:\n{out.strip()[:160]}", "y"))
        return False
    rc, out = git(repo, "push", "origin", branch)
    if rc != 0:
        info(col(f"  push failed:\n{out.strip()[:160]}", "y"))
        return False
    info(col("contributors-graph refresh pushed — updates shortly.", "g"))
    return True


# ── main action ───────────────────────────────────────────────────────────────
def declaude(target: str, *, yes: bool, dry_run: bool, no_refresh: bool, no_backup: bool):
    """Clone TARGET, strip Claude traces, force-push, and refresh the graph."""
    if not have("git"):
        die("git not found in PATH.")
    if not have("git-filter-repo"):
        die("git-filter-repo is not installed. Reinstall declaude (pip install "
            "declaude) or run: pipx install git-filter-repo")
    # Preflight: gh drives the clone, the cache flush and the server-side check.
    # Fail early with a clear message instead of cryptic errors mid-run.
    if have("gh"):
        if not gh_authed():
            die("GitHub CLI 'gh' is installed but not logged in.\n"
                "  Run:  gh auth login")
    else:
        info(col("note: GitHub CLI 'gh' not found — private-repo clone may prompt "
                 "for credentials and the Contributors-graph flush will be skipped.\n"
                 "  Install it from https://cli.github.com and run 'gh auth login'.", "y"))

    url, slug = normalize_remote(target)
    if not url:
        die(f"need a GitHub URL or OWNER/REPO slug (got: {target})")
    if not slug:
        die("only github.com repositories are supported.")

    repo, tmp = clone_target(url, slug)
    try:
        hits = count_hits(repo)
        ah = author_hits(repo)
        affected = [b for b in local_branches(repo) if count_hits(repo, b)]
        rbranches = set(remote_branches(repo))

        print(col(f"\nRepo   : {slug}", "b"))
        print(f"  traces : {col(str(hits), 'y')} co-author commit(s)"
              + (f", {col(str(ah), 'y')} Claude author/committer" if ah else ""))
        if hits:
            print(f"  affected branches: {', '.join(affected) or '-'}")
        else:
            print(col("  history already clean — will refresh GitHub's graph only.", "c"))
        if ah:
            print(col("  ⚠ some commits have a Claude AUTHOR — declaude only cleans "
                      "message trailers, NOT authorship. Use git-filter-repo --mailmap for that.", "y"))

        if dry_run:
            print(col("\n[dry-run] nothing changed. Drop --dry-run to execute.", "c"))
            return
        if not yes:
            act = "REWRITES history, FORCE-PUSHES, " if hits else ""
            print(col(f"\nThis {act}flushes GitHub's contributor cache (renames the "
                      "default branch) and pushes an empty refresh commit.", "y"))
            if input("  Continue? type 'yes': ").strip().lower() not in ("yes", "y"):
                die("aborted.", 0)

        # 1) rewrite + push (only if there are traces to strip)
        if hits:
            if no_backup:
                info(col("⚠ --no-backup: skipping backup bundle (no restore point).", "y"))
            else:
                bundle = backup_bundle(repo, slug.split("/")[-1])
                info(f"backup bundle: {col(bundle, 'd')}")
            _, origin_url = git(repo, "remote", "get-url", "origin")
            origin_url = origin_url.strip()

            info("rewriting history (git filter-repo)…")
            rc, out = run(["git", "filter-repo", "--force",
                           "--message-callback", SCRUB_CALLBACK], cwd=repo)
            if rc != 0:
                restore = "" if no_backup else (
                    f"\n\nRestore from bundle:\n  git -C <repo> fetch {bundle} '*:*'")
                die(f"filter-repo failed:\n{out}{restore}")
            if origin_url:
                git(repo, "remote", "remove", "origin")
                git(repo, "remote", "add", "origin", origin_url)

            left = count_hits(repo)
            if left:
                die(f"still {left} trace(s) after rewrite — check manually.")
            info(col("local history is clean (0 traces).", "g"))

            push_branches = [b for b in affected if b in rbranches] or \
                            [b for b in local_branches(repo) if b in rbranches]
            info(f"force-pushing branches: {', '.join(push_branches)}")
            failed = []
            for b in push_branches:
                rc, out = git(repo, "push", "origin", b, "--force")
                ok = rc == 0
                print(f"    {col('✓', 'g') if ok else col('✗', 'r')} {b}")
                if not ok:
                    failed.append(b)
                    info(col(f"      {out.strip()[:160]}", "y"))
            if failed:
                die(f"force-push failed for: {', '.join(failed)} "
                    "(branch protection?). Local history is clean; fix and retry.")
            if have("gh"):
                n = server_hits(slug)
                print(col(f"\nServer {slug}: {n} traced commit(s) across all branches.",
                          "g" if n == 0 else "y"))

        # 2) refresh the contributors graph: FLUSH first (rename the default
        # branch to reset GitHub's cache), THEN push a fresh commit (which makes
        # the cache recompute against the clean history). Neither step alone is
        # enough — the order flush → commit is what actually drops @claude.
        if no_refresh:
            info("skipped contributors-graph refresh (--no-refresh).")
        else:
            flush_cache(slug)
            refresh_contributors(repo)

        print(col("\nDone. Recheck the Contributors graph in Incognito.", "g"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── path (put declaude's Scripts dir on PATH) ──────────────────────────────────
def _scripts_dirs() -> list[str]:
    """Candidate directories where pip installs the `declaude` executable,
    most-likely first. Uses the same sysconfig lookup install.ps1 relies on, so
    a plain `pip install --user` and a system install are both covered."""
    import sysconfig
    schemes = set(sysconfig.get_scheme_names())
    order = ("nt_user", "nt") if os.name == "nt" else ("posix_user", "posix_prefix")
    out: list[str] = []
    for scheme in order:
        if scheme not in schemes:
            continue
        try:
            p = sysconfig.get_path("scripts", scheme)
        except Exception:
            p = None
        if p and p not in out:
            out.append(p)
    return out


def _exe_name() -> str:
    return "declaude.exe" if os.name == "nt" else "declaude"


def _find_scripts_dir() -> str | None:
    """The Scripts dir actually holding declaude's launcher, falling back to the
    most-likely candidate if the launcher isn't found (e.g. layout differs)."""
    dirs = _scripts_dirs()
    exe = _exe_name()
    for d in dirs:
        if d and os.path.exists(os.path.join(d, exe)):
            return d
    return dirs[0] if dirs else None


def _on_path(scripts: str) -> bool:
    """True if `scripts` is already on the *current* process PATH."""
    target = os.path.normcase(os.path.normpath(scripts))
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if p and os.path.normcase(os.path.normpath(p)) == target:
            return True
    return False


def _add_path_windows(scripts: str) -> bool:
    """Add `scripts` to the persistent *user* PATH (HKCU\\Environment) if missing.
    Returns True if it was added, False if already present. Broadcasts the change
    so newly opened terminals pick it up without a logout."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                        winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            cur, typ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            cur, typ = "", winreg.REG_EXPAND_SZ
        parts = [p for p in cur.split(";") if p]
        want = os.path.normcase(scripts.rstrip("\\"))
        if any(os.path.normcase(p.rstrip("\\")) == want for p in parts):
            return False
        parts.append(scripts)
        winreg.SetValueEx(key, "Path", 0, typ or winreg.REG_EXPAND_SZ, ";".join(parts))
    try:  # tell running programs the environment changed (best-effort)
        import ctypes
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x1A, 0, "Environment", 0x0002, 5000,
            ctypes.byref(ctypes.c_ulong()))
    except Exception:
        pass
    return True


def _rc_file() -> Path:
    """The shell startup file to extend on macOS/Linux, based on $SHELL."""
    shell = os.environ.get("SHELL", "")
    home = Path(os.path.expanduser("~"))
    if "zsh" in shell:
        return home / ".zshrc"
    if "bash" in shell:
        bashrc = home / ".bashrc"
        return bashrc if bashrc.exists() else (home / ".bash_profile")
    return home / ".profile"


def _add_path_posix(scripts: str) -> tuple[bool, Path]:
    """Append a PATH export for `scripts` to the shell rc file if not present.
    Returns (added, rc_file)."""
    rc = _rc_file()
    existing = rc.read_text() if rc.exists() else ""
    if scripts in existing:
        return False, rc
    block = f'\n# added by declaude path\nexport PATH="{scripts}:$PATH"\n'
    with open(rc, "a", encoding="utf-8") as f:
        f.write(block)
    return True, rc


def cmd_path():
    """Put declaude's install (Scripts) directory on PATH so the bare `declaude`
    command works — the one thing `pip install` can't do on its own."""
    scripts = _find_scripts_dir()
    if not scripts:
        die("could not locate the directory where declaude is installed.")
    if not os.path.exists(os.path.join(scripts, _exe_name())):
        info(col(f"note: no {_exe_name()} found in {scripts} yet — adding it anyway.", "y"))

    if os.name == "nt":
        if _add_path_windows(scripts):
            info(col(f"Added to your user PATH: {scripts}", "g"))
            info("Open a NEW terminal, then run:  declaude --help")
        else:
            info(col(f"Already on your user PATH: {scripts}", "g"))
            if not _on_path(scripts):
                info("Open a NEW terminal for it to take effect.")
    else:
        added, rc = _add_path_posix(scripts)
        if added:
            info(col(f"Added to PATH via {rc}: {scripts}", "g"))
            info(f"Reload your shell or run:  source {rc}")
        else:
            info(col(f"Already configured in {rc}: {scripts}", "g"))


# ── prevent ───────────────────────────────────────────────────────────────────
def cmd_prevent():
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
    argv = sys.argv[1:]
    if argv and argv[0] == "prevent":
        return cmd_prevent()
    if argv and argv[0] == "path":
        return cmd_path()

    p = argparse.ArgumentParser(
        prog="declaude",
        description="Remove Claude/AI attribution from a GitHub repo "
                    "(clean history + force-push + refresh Contributors graph).",
        epilog="Other: `declaude path` puts the install dir on your PATH so the "
               "`declaude` command works; `declaude prevent` turns off Claude Code "
               "attribution going forward.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("target", help="GitHub URL or OWNER/REPO slug")
    p.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    p.add_argument("--dry-run", action="store_true", help="show the plan only")
    p.add_argument("--no-refresh", action="store_true",
                   help="don't push the empty commit that refreshes the contributors graph")
    p.add_argument("--no-backup", action="store_true",
                   help="skip the restorable backup bundle before rewriting (not recommended)")
    args = p.parse_args(argv)
    declaude(args.target, yes=args.yes, dry_run=args.dry_run,
             no_refresh=args.no_refresh, no_backup=args.no_backup)


def _entry():
    try:
        main()
    except KeyboardInterrupt:
        die("aborted.", 130)


if __name__ == "__main__":
    _entry()
