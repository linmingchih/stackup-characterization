@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM Add current directory to PATH
set "PATH=%~dp0;%PATH%"

REM Check if .venv exists, create if not
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment with Python 3.10...
    REM Try py launcher first (matches .python-version = 3.10)
    py -3.10 -m venv .venv 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo Python 3.10 not found via py launcher. Trying python3.10...
        python3.10 -m venv .venv 2>nul
        if %ERRORLEVEL% NEQ 0 (
            echo ERROR: Python 3.10 is required but not found.
            echo Please install Python 3.10 from https://www.python.org/downloads/
            echo The project requires Python 3.10 for pyaedt compatibility.
            pause
            exit /b 1
        )
    )
)

REM Upgrade pip
echo Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if %ERRORLEVEL% NEQ 0 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

REM Install requirements
echo Installing requirements...
".venv\Scripts\pip.exe" install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo pip install failed.
    pause
    exit /b 1
)

REM Run application
echo Starting application...
start "" ".venv\Scripts\pythonw.exe" src\gui_app.py
