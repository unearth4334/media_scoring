param([string] $Dir,[int] $Port,[string] $Host,[string] $Pattern,[string] $Style)
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir
if (-not (Test-Path ".venv")) { try { py -m venv .venv } catch { python -m venv .venv } }
$VenvPython = Join-Path ".venv" "Scripts/python.exe"
& $VenvPython -m pip install --upgrade pip *> $null
& $VenvPython -m pip install -r requirements.txt *> $null
$cfg = & $VenvPython "read_config.py" --file "config.yml" --format "json" | ConvertFrom-Json
if (-not $Dir)   { $Dir   = $cfg.dir }
if (-not $Port)  { $Port  = [int]$cfg.port }
if (-not $Host)  { $Host  = $cfg.host }
if (-not $Pattern) { $Pattern = $cfg.pattern }
if (-not $Style) { $Style = $cfg.style }
Write-Host "Starting Video Scorer: dir=$Dir  port=$Port  host=$Host  pattern=$Pattern  style=$Style"
& $VenvPython "app.py" --dir $Dir --port $Port --host $Host --pattern $Pattern --style $Style
