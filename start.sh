#!/bin/bash

# =============================================================================
# Aeroponic Snapshot Database — One-Click Setup & Run
# =============================================================================
# Clone → bash start.sh → ใช้งานได้เลย
# รองรับ: Ubuntu / Debian / Raspberry Pi OS / macOS
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✅${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠️${NC}  $1"; }
fail() { echo -e "  ${RED}❌${NC} $1"; }

echo ""
echo "================================================================"
echo "  🌱  AEROPONIC SNAPSHOT DATABASE"
echo "      Automatic Setup & Run"
echo "================================================================"
echo ""

# ── 1. Python ────────────────────────────────────────────────────────
echo "[1/7] Checking Python..."
if ! command -v python3 &>/dev/null; then
    fail "Python 3 is not installed!"
    echo "  Install:  sudo apt install -y python3 python3-pip python3-venv"
    exit 1
fi
ok "$(python3 --version)"

# ── 2. Virtual environment ───────────────────────────────────────────
echo "[2/7] Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    ok "Created .venv"
else
    ok ".venv exists"
fi
source .venv/bin/activate
pip install -q --upgrade pip setuptools wheel 2>/dev/null
pip install -q -r requirements.txt
ok "Dependencies installed"

# ── 3. Directories ───────────────────────────────────────────────────
echo "[3/7] Creating directories..."
mkdir -p snapshots generated_videos logs certs .cache
ok "All directories ready"

# ── 4. .env (auto-generate if missing) ───────────────────────────────
echo "[4/7] Checking configuration..."
if [ ! -f ".env" ]; then
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    ADMIN_TK=$(python3 -c "import secrets; print(secrets.token_hex(16))")
    API1=$(python3 -c "import secrets; print('rpi-cam1-' + secrets.token_hex(12))")
    API2=$(python3 -c "import secrets; print('rpi-cam2-' + secrets.token_hex(12))")
    API3=$(python3 -c "import secrets; print('rpi-cam3-' + secrets.token_hex(12))")

    cat > .env << EOF
# Auto-generated on $(date '+%Y-%m-%d %H:%M:%S')
HOST=0.0.0.0
PORT=8443
FLASK_DEBUG=False
SECRET_KEY=${SECRET}
ADMIN_TOKEN=${ADMIN_TK}
USE_SSL=true
API_KEYS=${API1},${API2},${API3}
SESSION_TIMEOUT=60
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION=15
MAX_CONTENT_LENGTH=52428800
ALLOWED_EXTENSIONS=png,jpg,jpeg,gif,bmp
VIDEO_FPS=10
VIDEO_QUALITY=95
LOG_LEVEL=INFO
EOF
    chmod 600 .env
    ok ".env created with secure random keys"
else
    ok ".env exists"
fi

# Read PORT from .env
APP_PORT=$(grep -E "^PORT=" .env 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo "8443")
USE_SSL=$(grep -E "^USE_SSL=" .env 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo "true")

# ── 5. SSL certificate (auto-generate if missing) ────────────────────
echo "[5/7] Checking SSL certificate..."
if [ "$USE_SSL" = "true" ]; then
    if [ ! -f "certs/cert.pem" ] || [ ! -f "certs/key.pem" ]; then
        HOSTNAME_VAL=$(hostname 2>/dev/null || echo "aeroponic")
        openssl req -x509 -newkey rsa:4096 \
            -keyout certs/key.pem -out certs/cert.pem \
            -days 365 -nodes \
            -subj "/C=TH/ST=Bangkok/L=Bangkok/O=AeroponicFarm/CN=${HOSTNAME_VAL}" \
            2>/dev/null
        chmod 600 certs/key.pem
        ok "SSL certificate generated (RSA 4096-bit, 365 days)"
    else
        ok "SSL certificate exists"
    fi
    PROTO="https"
else
    PROTO="http"
    ok "SSL disabled — running HTTP"
fi

# ── 6. cloudflared (download if missing) ─────────────────────────────
echo "[6/7] Checking cloudflared tunnel binary..."
if [ ! -f "src/cloudflared" ] || [ ! -s "src/cloudflared" ]; then
    rm -f src/cloudflared 2>/dev/null  # Remove broken file if exists
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  CF_ARCH="amd64" ;;
        aarch64) CF_ARCH="arm64" ;;
        armv7l)  CF_ARCH="arm"   ;;
        armv6l)  CF_ARCH="arm"   ;;
        *)       CF_ARCH="amd64" ;;
    esac
    CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}"
    echo "  Downloading cloudflared for linux-${CF_ARCH}..."
    
    DOWNLOAD_OK=false
    if command -v wget &>/dev/null; then
        wget -q --timeout=30 "$CF_URL" -O src/cloudflared 2>/dev/null && DOWNLOAD_OK=true
    elif command -v curl &>/dev/null; then
        curl -sL --connect-timeout 30 "$CF_URL" -o src/cloudflared 2>/dev/null && DOWNLOAD_OK=true
    else
        warn "wget/curl not found — cannot download cloudflared"
    fi
    
    # Verify download succeeded (file exists, >1MB, and is valid binary)
    if [ "$DOWNLOAD_OK" = true ] && [ -s "src/cloudflared" ]; then
        FILE_SIZE=$(stat -c%s "src/cloudflared" 2>/dev/null || stat -f%z "src/cloudflared" 2>/dev/null || echo "0")
        if [ "$FILE_SIZE" -gt 1000000 ]; then
            chmod +x src/cloudflared
            ok "cloudflared downloaded (linux-${CF_ARCH}, $(($FILE_SIZE / 1024 / 1024))MB)"
        else
            rm -f src/cloudflared
            warn "Downloaded file too small (may be blocked by firewall)"
            warn "Online tunnel won't work, but app runs fine locally"
            warn "Manual install: sudo wget -O /usr/local/bin/cloudflared $CF_URL && chmod +x /usr/local/bin/cloudflared"
        fi
    else
        rm -f src/cloudflared 2>/dev/null
        warn "Could not download cloudflared (network issue or blocked)"
        warn "Online tunnel won't work, but app runs fine locally"
    fi
else
    # Verify existing file is valid
    FILE_SIZE=$(stat -c%s "src/cloudflared" 2>/dev/null || stat -f%z "src/cloudflared" 2>/dev/null || echo "0")
    if [ "$FILE_SIZE" -gt 1000000 ]; then
        ok "cloudflared exists ($(($FILE_SIZE / 1024 / 1024))MB)"
    else
        rm -f src/cloudflared
        warn "Existing cloudflared is corrupted, please re-run start.sh"
    fi
fi

# ── 7. Database init ─────────────────────────────────────────────────
echo "[7/7] Initializing database..."
python3 -c "
import sys; sys.path.insert(0, '.')
from src.database import init_database
init_database()
" 2>/dev/null
ok "Database ready"

# ── Start ─────────────────────────────────────────────────────────────
IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
echo ""
echo "================================================================"
echo "  ✅  ALL READY!"
echo "================================================================"
echo ""
echo "  🌐  ${PROTO}://localhost:${APP_PORT}"
echo "  🌐  ${PROTO}://${IP_ADDR}:${APP_PORT}"
echo ""
echo "  👤  Login: admin / admin"
echo "  ⚠️   Change password after first login!"
echo ""
echo "  📝  Press Ctrl+C to stop"
echo "================================================================"
echo ""

python run.py

if [ $? -ne 0 ]; then
    echo ""
    fail "Application failed to start! Check the error above."
    exit 1
fi
