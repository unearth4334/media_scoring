# Run Video Scorer (FastAPI) — PowerShell entrypoint
# Usage:
#   .\run_video_scorer.ps1 [-Dir <path>] [-Port <int>] [-Host <ip/name>]
param(
    [string] $Dir = (Get-Location).Path,
    [int]    $Port = 7862,
    [string] $Host = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

# Resolve script root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# Create venv if missing
if (-not (Test-Path ".venv")) {
    try {
        py -m venv .venv
    } catch {
        python -m venv .venv
    }
}

$VenvPython = Join-Path ".venv" "Scripts/python.exe"

# Upgrade pip and install deps
& $VenvPython -m pip install --upgrade pip *> $null
& $VenvPython -m pip install -r requirements.txt

# Launch app
& $VenvPython "app_fastapi.py" --dir $Dir --port $Port --host $Host
