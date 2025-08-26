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
if not "%~4"=="" set "PATTERN=%~4"
if not "%~5"=="" set "STYLE=%~5"
echo Starting Video Scorer: dir=%DIR%  port=%PORT%  host=%HOST%  pattern=%PATTERN%  style=%STYLE%  toggle_ext=%TOGGLE_EXTENSIONS%
set "THUMBNAIL_ARGS="
if /I "%GENERATE_THUMBNAILS%"=="true" set "THUMBNAIL_ARGS=--generate-thumbnails --thumbnail-height %THUMBNAIL_HEIGHT%"
"%VENV_PY%" app.py --dir "%DIR%" --port %PORT% --host %HOST% --pattern "%PATTERN%" --style "%STYLE%" %THUMBNAIL_ARGS% --toggle-extensions %TOGGLE_EXTENSIONS%
popd
endlocal
