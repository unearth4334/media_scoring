@echo off
REM Run Video Scorer (FastAPI) — Windows batch entrypoint
REM Usage:
REM   run_video_scorer.bat [DIR] [PORT] [HOST]
REM Defaults:
REM   DIR = current directory
REM   PORT = 7862
REM   HOST = 127.0.0.1

setlocal enabledelayedexpansion

set "DIR=%~1"
if "%DIR%"=="" set "DIR=%CD%"

set "PORT=%~2"
if "%PORT%"=="" set "PORT=7862"

set "HOST=%~3"
if "%HOST%"=="" set "HOST=127.0.0.1"

REM Resolve script directory and cd there
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

REM Create venv if missing
if not exist ".venv" (
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -m venv .venv
    ) else (
        python -m venv .venv
    )
)

set "VENV_PY=.venv\Scripts\python.exe"

REM Upgrade pip and install deps (quiet-ish)
"%VENV_PY%" -m pip install --upgrade pip >nul
"%VENV_PY%" -m pip install -r requirements.txt

REM Launch app
"%VENV_PY%" app_fastapi.py --dir "%DIR%" --port %PORT% --host %HOST%

popd
endlocal
