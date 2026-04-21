@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM Add current directory to PATH
set "PATH=%~dp0;%PATH%"

REM Check for Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python not found. Please install Python.
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if !ERRORLEVEL! NEQ 0 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Sync environment
echo Syncing environment...
".venv\Scripts\python.exe" -m pip install -e .
if !ERRORLEVEL! NEQ 0 (
    echo pip install failed.
    pause
    exit /b 1
)

REM Run application
echo Starting application...
start "" ".venv\Scripts\pythonw.exe" src\gui_app.py
