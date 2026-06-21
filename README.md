# declaude

**Deteksi & hapus atribusi Claude/AI dari repository git** — buang jejak seperti
`Co-Authored-By: Claude <noreply@anthropic.com>` atau baris _"Generated with
Claude Code"_ dari **seluruh riwayat commit**, **tanpa menyentuh kode** maupun
**author** commit-mu.

Dibuat dari pengalaman membersihkan repo sungguhan, jadi sudah memperhitungkan
jebakan yang biasa bikin repot:

- 🔒 **Menjaga perubahan belum-commit (WIP)** — di-backup lalu dikembalikan.
- 🌿 **Repo multi-branch** — push **semua** branch terdampak, bukan cuma `main`.
- 💾 **Backup bundle off-repo** sebelum rewrite (bisa dipulihkan penuh).
- 🙈 **Token di URL remote tak pernah dicetak.**
- ✅ **Verifikasi server-side** via `gh` setelah push.

## Kenapa muncul `@claude` di Contributors GitHub?

Tool AI sering menambahkan trailer `Co-Authored-By: Claude …` ke pesan commit.
GitHub membangun grafik **Contributors dari pesan commit di default branch**, jadi
selama trailer itu ada di history, `@claude` ikut terdaftar. Menghapusnya butuh
**rewrite history + force-push** — itulah yang dilakukan `declaude clean`.

## Pasang

```bash
# prasyarat
pipx install git-filter-repo      # atau: pip install --user git-filter-repo
# gh (GitHub CLI) opsional — untuk scan akun & verifikasi server

# pasang declaude
git clone <repo-ini> ~/declaude && ~/declaude/install.sh
# atau langsung:
./install.sh
```

`install.sh` menaruh symlink `declaude` di `~/.local/bin`.

## Pakai

```bash
# 1) Lihat repo mana saja yang punya jejak Claude (READ-ONLY, aman)
declaude scan ~/project            # scan semua repo di bawah folder
declaude scan ~/project --branches # rincikan per-branch

# 2) Lihat rencana untuk satu repo tanpa mengubah apa pun
declaude clean ~/project/app --dry-run

# 3) Bersihkan history lokal saja (belum push)
declaude clean ~/project/app

# 4) Bersihkan + force-push semua branch terdampak ke GitHub
declaude clean ~/project/app --push

# 5) Cegah kambuh: matikan atribusi Claude Code ke depan
declaude prevent
```

Setiap `clean` membuat **backup bundle** di `~/.declaude-backups/` lebih dulu.
Pulihkan kapan saja:

```bash
git -C <repo> fetch ~/.declaude-backups/<nama>.bundle '*:*'
```

## Catatan jujur

- **Author Claude (langka).** Bila ada commit yang _author_-nya Claude (bukan
  sekadar co-author), `declaude` memberi peringatan tapi tidak mengubahnya —
  gunakan `git filter-repo --mailmap` untuk menulis ulang author.
- **PR yang sudah ditutup.** GitHub menyimpan commit lama di `refs/pull/N/head`
  yang **tak bisa dihapus user**. Grafik Contributors dihitung dari default
  branch (sudah bersih setelah `clean --push`), jadi `@claude` semestinya tetap
  hilang; bila membandel, hanya GitHub Support yang bisa purge cache PR ref.
- **Cache UI GitHub.** Setelah `clean --push`, `@claude` bisa bertahan beberapa
  saat di tampilan karena cache. Force-push sudah memicu regen; cek di Incognito.

## Perintah

| Perintah | Fungsi |
|---|---|
| `declaude scan [PATH] [--branches] [--depth N]` | Cari repo & laporkan jejak (read-only). |
| `declaude clean REPO [--push] [--yes] [--dry-run] [--backup-dir DIR]` | Rewrite history + (opsional) push. |
| `declaude prevent` | Set `includeCoAuthoredBy:false` di `~/.claude/settings.json`. |

## Prasyarat

- `git`
- `git-filter-repo` (untuk `clean`)
- `gh` (opsional — scan akun GitHub & verifikasi server)
- Python 3.8+
