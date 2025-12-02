@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM Check for uv
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo uv not found. Installing...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%LOCALAPPDATA%\bin;%USERPROFILE%\.cargo\bin;%PATH%"
)

REM Ensure correct Python version
echo Ensuring Python version from .python-version...
uv python install
if %ERRORLEVEL% NEQ 0 (
    echo Failed to install Python.
    pause
    exit /b 1
)

REM Sync environment
echo Syncing environment...
uv sync
if %ERRORLEVEL% NEQ 0 (
    echo uv sync failed.
    pause
    exit /b 1
)

REM Run application
echo Starting application...
start "" ".venv\Scripts\pythonw.exe" src\gui_app.py
