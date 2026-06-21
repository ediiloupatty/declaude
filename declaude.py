#!/usr/bin/env python3
"""
declaude — deteksi & hapus atribusi Claude/AI dari repository git.

Membersihkan jejak yang ditinggalkan tool AI (mis. "Co-Authored-By: Claude
<noreply@anthropic.com>" atau baris "Generated with Claude Code") dari SELURUH
riwayat commit, tanpa menyentuh kode maupun penulis (author) commit-mu.

Subperintah:
  scan    — (read-only) cari repo git + laporkan jejak Claude per repo/branch.
  clean   — rewrite history sebuah repo untuk membuang jejak (filter-repo),
            simpan backup, opsional force-push semua branch terdampak.
  prevent — set "includeCoAuthoredBy": false di ~/.claude/settings.json.

Dirancang dari pengalaman membersihkan repo sungguhan, jadi sudah memperhitungkan:
  • menjaga perubahan belum-commit (WIP) — di-backup lalu dikembalikan,
  • repo multi-branch — push SEMUA branch terdampak, bukan cuma main,
  • backup bundle off-repo sebelum rewrite (bisa dipulihkan),
  • token di URL remote tak pernah dicetak,
  • verifikasi server-side via `gh` setelah push.

Butuh: git, git-filter-repo (untuk `clean`), dan gh (opsional, untuk verifikasi
server & scan akun GitHub).
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

# Baris yang dianggap "jejak Claude" pada pesan commit.
DETECT_RE = re.compile(
    r"(co-authored-by:.*(claude|anthropic))|(generated with claude)|(noreply@anthropic)",
    re.IGNORECASE,
)

# Body fungsi untuk `git filter-repo --message-callback`. Menerima `message`
# (bytes), mengembalikan bytes. Membuang baris co-author Claude/anthropic dan
# baris "Generated with Claude Code", lalu merapikan baris kosong berlebih.
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

# ── warna kecil-kecilan ───────────────────────────────────────────────────────
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


# ── helper proses ─────────────────────────────────────────────────────────────
def run(cmd, cwd=None, check=False, capture=True):
    """Jalankan command; return (rc, stdout). Tak pernah melempar kecuali check."""
    res = subprocess.run(
        cmd, cwd=cwd, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    if check and res.returncode != 0:
        die(f"perintah gagal: {' '.join(cmd)}\n{res.stdout or ''}")
    return res.returncode, (res.stdout or "")


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def git(repo: str, *args, check=False, capture=True):
    return run(["git", "-C", repo, *args], check=check, capture=capture)


# ── deteksi repo & jejak ──────────────────────────────────────────────────────
def find_repos(root: str, max_depth: int = 5) -> list[str]:
    """Cari semua working-tree git di bawah `root` (berdasarkan folder .git)."""
    root = os.path.abspath(root)
    repos = []
    root_depth = root.rstrip("/").count("/")
    for dirpath, dirnames, _ in os.walk(root):
        if dirpath.count("/") - root_depth > max_depth:
            dirnames[:] = []
            continue
        if ".git" in dirnames or os.path.isfile(os.path.join(dirpath, ".git")):
            repos.append(dirpath)
            # jangan menyelam ke .git, tapi tetap telusuri nested repo lain
            if ".git" in dirnames:
                dirnames.remove(".git")
    return sorted(repos)


def remote_slug(repo: str) -> str | None:
    """OWNER/REPO dari remote origin (None bila bukan github / tak ada)."""
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
    """Jumlah commit yang mengandung jejak Claude pada `ref` (atau semua ref)."""
    rc, out = git(
        repo, "log", ref, "-i", "-E",
        "--grep=co-authored-by:.*(claude|anthropic)",
        "--grep=generated with claude", "--format=%H",
    )
    return len([h for h in out.split("\n") if h.strip()]) if rc == 0 else 0


def author_hits(repo: str) -> int:
    """Commit yang AUTHOR/COMMITTER-nya Claude/anthropic (kasus langka, lebih serius)."""
    rc, out = git(repo, "log", "--all", "--format=%an <%ae>|%cn <%ce>")
    if rc != 0:
        return 0
    return len([ln for ln in out.split("\n") if re.search(r"claude|anthropic", ln, re.I)])


def is_dirty(repo: str) -> int:
    rc, out = git(repo, "status", "--porcelain")
    return len([ln for ln in out.split("\n") if ln.strip()]) if rc == 0 else 0


# ── scan ──────────────────────────────────────────────────────────────────────
def cmd_scan(args):
    root = args.path or os.getcwd()
    if not os.path.isdir(root):
        die(f"folder tak ada: {root}")
    repos = find_repos(root, args.depth)
    if not repos:
        info("tak ada repo git ditemukan.")
        return
    print(col(f"\nScan {len(repos)} repo di {root}\n", "b"))
    dirty_total = 0
    for repo in repos:
        rel = os.path.relpath(repo, root)
        slug = remote_slug(repo)
        hits = count_hits(repo)
        ah = author_hits(repo)
        tag = col("BERSIH", "g") if hits == 0 and ah == 0 else col(f"{hits} co-author"
                  + (f", {ah} author" if ah else ""), "y")
        loc = slug or col("(lokal/non-github)", "d")
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
        print(col(f"{dirty_total} repo punya jejak Claude.", "y"),
              "Bersihkan dengan:", col("declaude clean <path-repo> --push", "b"))
    else:
        print(col("Semua repo bersih. 🎉", "g"))


# ── clean ─────────────────────────────────────────────────────────────────────
def backup_repo(repo: str, backup_dir: str) -> tuple[str, str | None]:
    """Buat bundle semua ref + (bila kotor) arsip file WIP. Return (bundle, wip)."""
    os.makedirs(backup_dir, exist_ok=True)
    name = os.path.basename(os.path.abspath(repo)) or "repo"
    ts = time.strftime("%Y%m%d-%H%M%S")
    bundle = os.path.join(backup_dir, f"{name}-{ts}.bundle")
    rc, out = git(repo, "bundle", "create", bundle, "--all")
    if rc != 0:
        die(f"gagal membuat bundle backup:\n{out}")
    wip = None
    if is_dirty(repo):
        # daftar file berubah (tracked + untracked, non-deleted)
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
        die(f"bukan repo git: {repo}")
    if not have("git-filter-repo"):
        die("git-filter-repo tak terpasang. Pasang: pipx install git-filter-repo "
            "(atau pip install --user git-filter-repo)")

    hits = count_hits(repo)
    ah = author_hits(repo)
    if hits == 0 and ah == 0:
        info(col("Repo sudah bersih — tak ada jejak Claude.", "g"))
        return
    slug = remote_slug(repo)
    affected = [b for b in local_branches(repo) if count_hits(repo, b)]
    rbranches = set(remote_branches(repo)) if slug else set()

    print(col(f"\nRepo   : {repo}", "b"))
    print(f"  remote : {slug or '(tak ada / non-github)'}")
    print(f"  jejak  : {col(str(hits), 'y')} commit co-author"
          + (f", {col(str(ah),'y')} author/committer Claude" if ah else ""))
    print(f"  branch terdampak (lokal): {', '.join(affected) or '-'}")
    if ah:
        print(col("  ⚠ ada commit dgn AUTHOR Claude — declaude hanya membersihkan "
                  "trailer pesan, BUKAN author. Pakai git-filter-repo --mailmap untuk itu.", "y"))
    if args.dry_run:
        print(col("\n[dry-run] tak ada yang diubah. Hilangkan --dry-run untuk eksekusi.", "c"))
        return
    if not args.yes:
        print(col("\nIni MENULIS ULANG history (semua SHA berubah)"
                  + (" lalu FORCE-PUSH." if args.push else "."), "y"))
        if input("  Lanjut? ketik 'ya': ").strip().lower() not in ("ya", "y", "yes"):
            die("dibatalkan.", 0)

    # 1) backup
    bundle, wip = backup_repo(repo, args.backup_dir)
    info(f"backup bundle: {col(bundle, 'd')}")
    if wip:
        info(f"backup WIP   : {col(wip, 'd')}")

    # 2) simpan URL origin (mungkin mengandung token — TAK dicetak)
    _, origin_url = git(repo, "remote", "get-url", "origin")
    origin_url = origin_url.strip()

    # 3) rewrite
    info("menulis ulang history (git filter-repo)…")
    rc, out = run(["git", "filter-repo", "--force", "--message-callback", SCRUB_CALLBACK],
                  cwd=repo)
    if rc != 0:
        die(f"filter-repo gagal:\n{out}\n\nPulihkan dari bundle:\n"
            f"  git -C {repo} fetch {bundle} '*:*'")
    # filter-repo melepas origin → pasang ulang
    if origin_url:
        git(repo, "remote", "remove", "origin")
        git(repo, "remote", "add", "origin", origin_url)

    # 4) kembalikan WIP
    if wip:
        with tarfile.open(wip, "r:gz") as t:
            t.extractall(repo)
        info("WIP dikembalikan.")

    left = count_hits(repo)
    if left:
        die(f"masih ada {left} jejak setelah rewrite — cek manual.")
    info(col(f"history lokal bersih (0 jejak).", "g"))

    # 5) push
    if not args.push:
        print(col("\nLokal sudah bersih. Belum di-push (tambah --push untuk dorong ke GitHub).", "c"))
        return
    if not slug:
        info("tak ada remote github — lewati push.")
        return
    push_branches = [b for b in affected if b in rbranches] or \
                    [b for b in local_branches(repo) if b in rbranches]
    info(f"force-push branch: {', '.join(push_branches)}")
    for b in push_branches:
        rc, out = git(repo, "push", "origin", b, "--force", capture=True)
        ok = "forced update" in out or "->" in out
        print(f"    {col('✓','g') if ok else col('✗','r')} {b}")
    # verifikasi server (bila gh ada)
    if have("gh"):
        n = server_hits(slug)
        print(col(f"\nServer {slug}: {n} commit ber-jejak di seluruh branch.",
                  "g" if n == 0 else "y"))
        if n == 0:
            print(col("Selesai. Cek halaman repo di Incognito; @claude akan hilang "
                      "setelah GitHub regen contributors.", "g"))
    else:
        info("(pasang `gh` untuk verifikasi otomatis sisi server)")


def server_hits(slug: str) -> int:
    """Total commit ber-jejak di semua branch repo (via gh)."""
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
            die(f"gagal baca {path} (JSON tak valid).")
    if data.get("includeCoAuthoredBy") is False:
        info(col("Sudah aktif: includeCoAuthoredBy=false.", "g"))
        return
    data["includeCoAuthoredBy"] = False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    info(col(f"Set includeCoAuthoredBy=false di {path}.", "g"))
    info("Commit/PR Claude Code ke depan tak akan menambah trailer atribusi.")


# ── cli ───────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        prog="declaude",
        description="Deteksi & hapus atribusi Claude/AI dari repository git.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="cari repo + laporkan jejak Claude (read-only)")
    s.add_argument("path", nargs="?", help="folder akar (default: cwd)")
    s.add_argument("--branches", action="store_true", help="rincikan per-branch")
    s.add_argument("--depth", type=int, default=5, help="kedalaman pencarian repo")
    s.set_defaults(func=cmd_scan)

    c = sub.add_parser("clean", help="rewrite history sebuah repo & (opsional) push")
    c.add_argument("repo", help="path repo git")
    c.add_argument("--push", action="store_true", help="force-push branch terdampak")
    c.add_argument("--yes", action="store_true", help="lewati konfirmasi")
    c.add_argument("--dry-run", action="store_true", help="tampilkan rencana saja")
    c.add_argument("--backup-dir", default=os.path.expanduser("~/.declaude-backups"),
                   help="folder backup bundle + WIP")
    c.set_defaults(func=cmd_clean)

    pr = sub.add_parser("prevent", help="set includeCoAuthoredBy=false (cegah kambuh)")
    pr.set_defaults(func=cmd_prevent)

    args = p.parse_args()
    if not have("git"):
        die("git tak ditemukan di PATH.")
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        die("dibatalkan.", 130)
