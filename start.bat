@echo off
REM Aeroponic Snapshot Database - Portable Setup Script
REM Automatic setup and run for Windows

setlocal enabledelayedexpansion
chcp 65001 > nul 2>&1
title Aeroponic Snapshot Database
color 0A

REM Set project directory
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo.
echo ================================================================
echo.
echo          AEROPONIC SNAPSHOT DATABASE
echo          Portable Setup Script
echo.
echo ================================================================
echo.

REM [1] Check Python
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ❌ ERROR: Python not found!
    echo.
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to add Python to PATH during installation
    echo.
    pause
    endlocal
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do (
    echo ✅ Found Python %%v
)
echo.

REM [2] Create/Check virtual environment
echo [2/5] Setting up virtual environment...
if not exist ".venv" (
    echo Creating .venv folder...
    python -m venv .venv
    if errorlevel 1 (
        echo ❌ Failed to create virtual environment
        pause
        endlocal
        exit /b 1
    )
)
echo ✅ Virtual environment ready
echo.

REM [3] Activate virtual environment
echo [3/5] Activating virtual environment...
call .venv\Scripts\activate.bat
echo ✅ Virtual environment activated
echo.

REM [4] Upgrade pip and install dependencies
echo [4/5] Installing dependencies...
echo (This may take a few minutes on first run)
echo.

python -m pip install --quiet --upgrade pip setuptools wheel 2>nul

REM Install requirements
python -m pip install --quiet -r requirements.txt 2>nul
if errorlevel 1 (
    echo ⚠️  Some packages failed to install. Retrying...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install dependencies
        echo.
        echo Possible solutions:
        echo 1. Check your internet connection
        echo 2. Try deleting .venv folder and running this script again
        echo 3. Manually run: pip install -r requirements.txt
        echo.
        pause
        endlocal
        exit /b 1
    )
)
echo ✅ Dependencies installed
echo.

REM [5] Create required folders
echo [5/5] Creating folders...
if not exist "snapshots" mkdir snapshots
if not exist "generated_videos" mkdir generated_videos
if not exist "logs" mkdir logs
echo ✅ Folders created
echo.

REM Start the server
echo ================================================================
echo ✅ SETUP COMPLETE!
echo ================================================================
echo.
echo ================================================================
echo    STARTUP OPTIONS
echo ================================================================
echo.
echo    [1] Start Server Only - Local Access
echo    [2] Start Server + Online Access - Share Worldwide
echo.
echo ================================================================
echo.

REM Check if running with argument
if "%~1"=="1" goto :START_LOCAL
if "%~1"=="2" goto :START_ONLINE
if "%~1"=="online" goto :START_ONLINE

REM Interactive mode - ask user
set "CHOICE=1"
set /p "CHOICE=Select option [1 or 2, default=1]: "

if "%CHOICE%"=="2" goto :START_ONLINE
if /i "%CHOICE%"=="online" goto :START_ONLINE
goto :START_LOCAL

:START_ONLINE
echo.
echo Starting with Online Access...
echo.
echo URL Local: http://localhost:5000
echo Online URL will be generated automatically...
echo.
echo Press Ctrl+C to stop
echo ================================================================
echo.

REM Set environment variable to auto-start tunnel
set "AUTO_START_TUNNEL=1"

python run.py
goto :END_SERVER

:START_LOCAL
echo.
echo Starting Server Only - Local Access
echo.
echo URL: http://localhost:5000
echo.
echo Press Ctrl+C to stop
echo ================================================================
echo.

python run.py
goto :END_SERVER

:END_SERVER

REM If error
if errorlevel 1 (
    echo.
    echo ❌ Server failed to start
    echo.
    pause
    endlocal
    exit /b 1
)

endlocal
exit /b 0
