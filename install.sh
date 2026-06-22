#!/usr/bin/env bash
# declaude installer.
#
# declaude is now a normal Python package, so the recommended install is just:
#
#     pip install declaude          # once published to PyPI
#     pip install .                 # from this folder
#     pip install git+https://github.com/ediiloupatty/declaude
#
# This script is a convenience wrapper around `pip install .` for people who
# clone the repo and run ./install.sh out of habit.
set -euo pipefail

cd "$(dirname "$0")"

PIP="${PIP:-pip}"
command -v "$PIP" >/dev/null 2>&1 || PIP="pip3"
command -v "$PIP" >/dev/null 2>&1 || { echo "✗ pip not found. Install Python 3.8+ and pip."; exit 1; }

echo "Installing declaude with: $PIP install --user ."
"$PIP" install --user .

echo "✓ declaude installed. Try: declaude --help"

command -v gh >/dev/null 2>&1 \
  || echo "! Required: install GitHub CLI 'gh' (https://cli.github.com) and run 'gh auth login'."
