@echo off
REM =============================================================================
REM Aeroponic Snapshot Database — Windows Setup & Run
REM =============================================================================
REM Double-click this file or run: start.bat
REM =============================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ================================================================
echo   AEROPONIC SNAPSHOT DATABASE
echo   Windows Setup ^& Run
echo ================================================================
echo.

REM ── 1. Python ────────────────────────────────────────────────────────
echo [1/7] Checking Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [X] Python not found!
    echo   Please install Python 3 from https://www.python.org/downloads/
    echo   Make sure to check "Add to PATH" during installation
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   [OK] %PYVER%

REM ── 2. Virtual environment ───────────────────────────────────────────
echo [2/7] Setting up virtual environment...
if not exist ".venv" (
    python -m venv .venv
    echo   [OK] Created .venv
) else (
    echo   [OK] .venv exists
)
call .venv\Scripts\activate.bat

pip install -q --upgrade pip setuptools wheel 2>nul
pip install -q -r requirements.txt 2>nul
echo   [OK] Dependencies installed

REM ── 3. Directories ───────────────────────────────────────────────────
echo [3/7] Creating directories...
if not exist "snapshots" mkdir snapshots
if not exist "generated_videos" mkdir generated_videos
if not exist "logs" mkdir logs
if not exist "certs" mkdir certs
echo   [OK] All directories ready

REM ── 4. .env (auto-generate if missing) ───────────────────────────────
echo [4/7] Checking configuration...
if not exist ".env" (
    python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" > .env.tmp
    python -c "import secrets; print('ADMIN_TOKEN=' + secrets.token_hex(16))" >> .env.tmp
    python -c "import secrets; print('API_KEYS=rpi-cam1-' + secrets.token_hex(12) + ',rpi-cam2-' + secrets.token_hex(12))" >> .env.tmp
    
    echo # Auto-generated configuration > .env
    echo HOST=0.0.0.0 >> .env
    echo PORT=8443 >> .env
    echo FLASK_DEBUG=False >> .env
    type .env.tmp >> .env
    echo USE_SSL=true >> .env
    echo SESSION_TIMEOUT=60 >> .env
    echo MAX_LOGIN_ATTEMPTS=5 >> .env
    echo LOCKOUT_DURATION=15 >> .env
    echo MAX_CONTENT_LENGTH=52428800 >> .env
    echo ALLOWED_EXTENSIONS=png,jpg,jpeg,gif,bmp >> .env
    echo VIDEO_FPS=10 >> .env
    echo VIDEO_QUALITY=95 >> .env
    echo LOG_LEVEL=INFO >> .env
    del .env.tmp 2>nul
    echo   [OK] .env created with secure random keys
) else (
    echo   [OK] .env exists
)

REM ── 5. SSL certificate ───────────────────────────────────────────────
echo [5/7] Checking SSL certificate...
if not exist "certs\cert.pem" (
    where openssl >nul 2>&1
    if %errorlevel% equ 0 (
        openssl req -x509 -newkey rsa:4096 -keyout certs\key.pem -out certs\cert.pem -days 365 -nodes -subj "/C=TH/ST=Bangkok/L=Bangkok/O=AeroponicFarm/CN=localhost" 2>nul
        echo   [OK] SSL certificate generated
    ) else (
        echo   [!] OpenSSL not found - SSL will be disabled
        echo   Install OpenSSL or use: winget install OpenSSL
    )
) else (
    echo   [OK] SSL certificate exists
)

REM ── 6. cloudflared ───────────────────────────────────────────────────
echo [6/7] Checking cloudflared tunnel...
if not exist "src\cloudflared.exe" (
    where cloudflared >nul 2>&1
    if %errorlevel% equ 0 (
        echo   [OK] cloudflared found in PATH
    ) else (
        echo   [!] cloudflared not found
        echo   To enable online access, install via:
        echo   winget install Cloudflare.cloudflared
        echo   Or download from: https://github.com/cloudflare/cloudflared/releases
        echo   App will work locally, but Online Access won't work
    )
) else (
    echo   [OK] cloudflared.exe exists
)

REM ── 7. Database init ─────────────────────────────────────────────────
echo [7/7] Initializing database...
python -c "import sys; sys.path.insert(0, '.'); from src.database import init_database; init_database()" 2>nul
echo   [OK] Database ready

REM ── Start ─────────────────────────────────────────────────────────────
echo.
echo ================================================================
echo   ALL READY!
echo ================================================================
echo.
echo   Local:    https://localhost:8443
echo.
echo   Login: admin / admin
echo   Change password after first login!
echo.
echo   Press Ctrl+C to stop
echo ================================================================
echo.

python run.py

pause
