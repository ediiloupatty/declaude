# declaude installer for Windows (PowerShell).
#
# Mirrors install.sh, but also fixes the one thing pip can't do on Windows:
# it adds Python's user "Scripts" directory to your PATH automatically, so the
# `declaude` command works in a new terminal without the manual PATH warning.
#
# Run from a clone of this repo:
#
#     powershell -ExecutionPolicy Bypass -File .\install.ps1
#
# Or install the published package instead of this folder:
#
#     powershell -ExecutionPolicy Bypass -File .\install.ps1 -FromPyPI

param(
    [switch]$FromPyPI
)

$ErrorActionPreference = "Stop"

# Pick a Python launcher: prefer the `py` launcher, fall back to `python`.
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" }
      elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" }
      else { $null }

if (-not $py) {
    Write-Host "X Python not found. Install Python 3.8+ from https://python.org" -ForegroundColor Red
    exit 1
}

$source = if ($FromPyPI) { "declaude" } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
Write-Host "Installing declaude with: $py -m pip install --user `"$source`""
& $py -m pip install --user --upgrade $source
if ($LASTEXITCODE -ne 0) {
    Write-Host "X pip install failed." -ForegroundColor Red
    exit 1
}

# Find where pip put declaude.exe. With --user installs that's the nt_user
# scripts dir; fall back to the default scheme just in case.
$candidates = & $py -c @"
import sysconfig
seen = []
for scheme in ('nt_user', 'nt'):
    try:
        p = sysconfig.get_path('scripts', scheme)
    except Exception:
        p = None
    if p and p not in seen:
        seen.append(p)
print('\n'.join(seen))
"@

$scripts = $null
foreach ($c in ($candidates -split "`n")) {
    $c = $c.Trim()
    if ($c -and (Test-Path (Join-Path $c "declaude.exe"))) { $scripts = $c; break }
}
if (-not $scripts) {
    # No declaude.exe found yet (e.g. layout differs); use the first candidate.
    $scripts = ($candidates -split "`n" | Where-Object { $_.Trim() } | Select-Object -First 1).Trim()
}

# Add it to the *user* PATH if missing (persists across terminals).
if ($scripts) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($userPath) { $parts = $userPath -split ';' | Where-Object { $_ } }
    if ($parts -notcontains $scripts) {
        $newPath = (@($userPath, $scripts) | Where-Object { $_ }) -join ';'
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        $env:Path += ";$scripts"
        Write-Host "+ Added to your PATH: $scripts" -ForegroundColor Green
    } else {
        Write-Host "  Already on PATH: $scripts"
    }
}

Write-Host "OK declaude installed." -ForegroundColor Green

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "! Required: install GitHub CLI 'gh' (https://cli.github.com) and run 'gh auth login'." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Open a NEW terminal, then run:  declaude --help"
Write-Host "Or use it right now without opening a new terminal:  $py -m declaude --help"
