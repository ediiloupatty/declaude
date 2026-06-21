#!/usr/bin/env bash
# declaude installer — symlink into ~/.local/bin (no system changes).
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)/declaude.py"
BIN="${HOME}/.local/bin"
DEST="${BIN}/declaude"

mkdir -p "$BIN"
chmod +x "$SRC"
ln -sf "$SRC" "$DEST"
echo "✓ declaude installed: $DEST -> $SRC"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "! Add to PATH:  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

command -v git-filter-repo >/dev/null 2>&1 \
  || echo "! For 'declaude clean', install: pipx install git-filter-repo"
command -v gh >/dev/null 2>&1 \
  || echo "! (optional) install GitHub CLI 'gh' for server-side verification."

echo "Try: declaude scan ~/edi/project"
