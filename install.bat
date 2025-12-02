@echo off
setlocal EnableDelayedExpansion

REM Check for uv
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo uv not found. Installing...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    
    REM Add common install locations to PATH for this session
    set "PATH=%LOCALAPPDATA%\bin;%USERPROFILE%\.cargo\bin;%PATH%"
    
    REM Check again
    where uv >nul 2>nul
    if !ERRORLEVEL! NEQ 0 (
        echo Failed to install or find uv. Please install it manually.
        pause
        exit /b 1
    )
)

REM Check for Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python not found in PATH.
    set /p "PYTHON_PATH=Please enter the full path to python.exe (or press Enter to let uv try to find/install one): "
    
    if defined PYTHON_PATH (
        REM Remove quotes if present
        set "PYTHON_PATH=!PYTHON_PATH:"=!"
        
        if exist "!PYTHON_PATH!" (
            echo Using provided Python: !PYTHON_PATH!
            REM Get directory of python.exe
            for %%F in ("!PYTHON_PATH!") do set "PYTHON_DIR=%%~dpF"
            set "PATH=!PYTHON_DIR!;%PATH%"
        ) else (
            echo Provided path does not exist: !PYTHON_PATH!
            echo Proceeding with uv default behavior...
        )
    )
)

echo Syncing environment with uv...
uv sync

if %ERRORLEVEL% NEQ 0 (
    echo uv sync failed.
    pause
    exit /b 1
)

echo Environment synced successfully.
pause
