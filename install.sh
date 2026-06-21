#!/usr/bin/env bash
# Pemasang declaude — symlink ke ~/.local/bin (tanpa menyentuh sistem).
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)/declaude.py"
BIN="${HOME}/.local/bin"
DEST="${BIN}/declaude"

mkdir -p "$BIN"
chmod +x "$SRC"
ln -sf "$SRC" "$DEST"
echo "✓ declaude terpasang: $DEST -> $SRC"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "! Tambahkan ke PATH:  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

command -v git-filter-repo >/dev/null 2>&1 \
  || echo "! Untuk 'declaude clean', pasang: pipx install git-filter-repo"
command -v gh >/dev/null 2>&1 \
  || echo "! (opsional) pasang GitHub CLI 'gh' untuk verifikasi sisi server."

echo "Coba: declaude scan ~/edi/project"
