@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM Add current directory to PATH
set "PATH=%~dp0;%PATH%"

REM - Step 1: Determine Python 3.10 executable -
set "PYTHON_EXE="
set "RECREATE_VENV="

REM Check default python version
for /f "tokens=2 delims= " %%v in ('python --version 2^>nul') do set "PY_VER=%%v"
if defined PY_VER (
    echo Detected default python version: !PY_VER!
    echo !PY_VER! | findstr /b "3.10" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "PYTHON_EXE=python"
        echo Default python is 3.10. Using it.
    )
)

REM If default python is not 3.10, ask user to input the path
if not defined PYTHON_EXE (
    echo.
    echo ============================================================
    echo   Python 3.10 is required but the default python is not 3.10.
    echo   Please provide the full path to your Python 3.10 executable.
    echo   Example: C:\Python310\python.exe
    echo ============================================================
    echo.
    set /p "USER_PYTHON=Enter Python 3.10 path: "

    REM Strip surrounding quotes from user input
    set "USER_PYTHON=!USER_PYTHON:"=!"

    REM Check if the path exists
    if not exist "!USER_PYTHON!" (
        echo ERROR: File not found: !USER_PYTHON!
        pause
        exit /b 1
    )

    REM Check if it is Python 3.10
    for /f "tokens=2 delims= " %%v in ('"!USER_PYTHON!" --version 2^>nul') do set "USER_PY_VER=%%v"
    if not defined USER_PY_VER (
        echo ERROR: Could not determine Python version from: !USER_PYTHON!
        pause
        exit /b 1
    )

    echo Detected version: !USER_PY_VER!
    echo !USER_PY_VER! | findstr /b "3.10" >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo ERROR: The provided Python is version !USER_PY_VER!, not 3.10.
        pause
        exit /b 1
    )

    set "PYTHON_EXE=!USER_PYTHON!"
    echo Using Python 3.10 from: !PYTHON_EXE!
)

REM - Step 1.5: Validate existing .venv against the selected/base Python -
if exist ".venv\pyvenv.cfg" (
    for /f "tokens=1,* delims==" %%A in (.venv\pyvenv.cfg) do (
        if /i "%%~A"=="home " set "VENV_HOME=%%~B"
    )

    if defined VENV_HOME (
        for /f "tokens=* delims= " %%A in ("!VENV_HOME!") do set "VENV_HOME=%%~A"
        if not exist "!VENV_HOME!\python.exe" (
            echo Existing .venv references missing base Python: !VENV_HOME!\python.exe
            set "RECREATE_VENV=1"
        )
    )
)

if defined USER_PYTHON if exist ".venv\pyvenv.cfg" (
    for %%I in ("!USER_PYTHON!") do set "SELECTED_PYTHON_HOME=%%~dpI"
    if defined SELECTED_PYTHON_HOME (
        if "!SELECTED_PYTHON_HOME:~-1!"=="\" set "SELECTED_PYTHON_HOME=!SELECTED_PYTHON_HOME:~0,-1!"
        if defined VENV_HOME if /I not "!VENV_HOME!"=="!SELECTED_PYTHON_HOME!" (
            echo Existing .venv was created from a different Python: !VENV_HOME!
            echo Rebuilding it with: !SELECTED_PYTHON_HOME!
            set "RECREATE_VENV=1"
        )
    )
)

REM - Step 2: Create .venv if it doesn't exist -
if defined RECREATE_VENV if exist ".venv" (
    echo Removing stale virtual environment...
    rmdir /s /q ".venv"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment with Python 3.10...
    "!PYTHON_EXE!" -m venv .venv
    if !ERRORLEVEL! NEQ 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM - Step 3: Upgrade pip -
echo Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if !ERRORLEVEL! NEQ 0 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

REM - Step 4: Install requirements -
echo Installing requirements...
".venv\Scripts\pip.exe" install -r requirements.txt
if !ERRORLEVEL! NEQ 0 (
    echo pip install failed.
    pause
    exit /b 1
)

REM - Step 5: Run application -
echo Starting application...
start "" ".venv\Scripts\pythonw.exe" src\gui_app.py
