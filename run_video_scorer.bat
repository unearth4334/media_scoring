@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"
if not exist ".venv" (
    where py >nul 2>nul
    if %errorlevel%==0 ( py -m venv .venv ) else ( python -m venv .venv )
)
set "VENV_PY=.venv\Scripts\python.exe"
"%VENV_PY%" -m pip install --upgrade pip >nul
"%VENV_PY%" -m pip install -r requirements.txt >nul
for /f "usebackq delims=" %%L in (`"%VENV_PY%" read_config.py --file config.yml --format bat`) do ( %%L )
if not "%~1"=="" set "DIR=%~1"
if not "%~2"=="" set "PORT=%~2"
if not "%~3"=="" set "HOST=%~3"
if not "%~4"=="" set "STYLE=%~4"
echo Starting Video Scorer: dir=%DIR%  port=%PORT%  host=%HOST%  style=%STYLE%
"%VENV_PY%" app.py --dir "%DIR%" --port %PORT% --host %HOST% --style "%STYLE%"
popd
endlocal
