#!/bin/bash
# =============================================================================
# Aeroponic Snapshot Database — Raspberry Pi / Ubuntu Full Setup Script
# =============================================================================
# This script automates the complete installation on a fresh Linux system.
#
# Tested on: Ubuntu 24.04 LTS / Raspberry Pi OS (Debian Bookworm)
# Run as:    sudo bash setup_raspberry_pi.sh
# =============================================================================

set -e  # Exit on any error

# ---------- Configuration ----------
APP_USER="${APP_USER:-admin1}"
APP_DIR="${APP_DIR:-/home/$APP_USER/Desktop/Task\ Description\ 4}"
APP_PORT="${APP_PORT:-8443}"
SSH_PORT="${SSH_PORT:-22}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_step() { echo -e "\n${BLUE}[STEP]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()  { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "================================================================"
echo "  AEROPONIC SNAPSHOT DATABASE — FULL SETUP"
echo "  Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  System: $(uname -s) $(uname -m)"
echo "  User: $(whoami)"
echo "================================================================"
echo ""

# =============================================================================
# STEP 1: System Update
# =============================================================================
log_step "1/8 — Updating system packages..."

apt update -y
apt upgrade -y
log_ok "System updated"

# =============================================================================
# STEP 2: Install Required System Packages
# =============================================================================
log_step "2/8 — Installing required packages..."

apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libopencv-dev \
    ufw \
    wget \
    curl \
    git \
    openssl \
    sqlite3 \
    libsqlite3-dev \
    libjpeg-dev \
    libpng-dev \
    libffi-dev

log_ok "All system packages installed"

# Record installed packages for documentation
dpkg -l | grep -E "python3|ufw|openssl|sqlite3|opencv|wget|curl" > /tmp/installed_packages.log
log_ok "Package list saved to /tmp/installed_packages.log"

# =============================================================================
# STEP 3: Configure Firewall (UFW)
# =============================================================================
log_step "3/8 — Configuring UFW firewall..."

ufw default deny incoming
ufw default allow outgoing
ufw allow ${SSH_PORT}/tcp comment 'SSH access'
ufw allow ${APP_PORT}/tcp comment 'Aeroponic HTTPS'

# Enable UFW (non-interactive)
echo "y" | ufw enable
ufw status verbose

log_ok "Firewall configured — SSH:${SSH_PORT}, HTTPS:${APP_PORT}"

# =============================================================================
# STEP 4: Setup Python Virtual Environment
# =============================================================================
log_step "4/8 — Setting up Python virtual environment..."

cd "$APP_DIR" 2>/dev/null || {
    log_err "Application directory not found: $APP_DIR"
    log_warn "Please copy the project files to $APP_DIR first"
    exit 1
}

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    log_ok "Virtual environment created"
else
    log_ok "Virtual environment already exists"
fi

source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

log_ok "Python dependencies installed"

# =============================================================================
# STEP 5: Generate SSL Certificates
# =============================================================================
log_step "5/8 — Generating SSL/TLS certificates..."

mkdir -p certs

if [ ! -f "certs/cert.pem" ] || [ ! -f "certs/key.pem" ]; then
    HOSTNAME=$(hostname)
    IP_ADDR=$(hostname -I | awk '{print $1}')

    openssl req -x509 -newkey rsa:4096 \
        -keyout certs/key.pem \
        -out certs/cert.pem \
        -days 365 \
        -nodes \
        -subj "/C=TH/ST=Bangkok/L=Bangkok/O=AeroponicFarm/OU=IT/CN=${HOSTNAME}"

    chmod 600 certs/key.pem
    chmod 644 certs/cert.pem
    log_ok "SSL certificate generated (valid 365 days)"
    log_ok "  CN=${HOSTNAME}, IP=${IP_ADDR}"
else
    log_ok "SSL certificates already exist"
fi

# =============================================================================
# STEP 6: Generate Secure .env Configuration
# =============================================================================
log_step "6/8 — Creating secure .env configuration..."

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ADMIN_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(16))")
API_KEY_1=$(python3 -c "import secrets; print('rpi-cam1-' + secrets.token_hex(12))")
API_KEY_2=$(python3 -c "import secrets; print('rpi-cam2-' + secrets.token_hex(12))")
API_KEY_3=$(python3 -c "import secrets; print('rpi-cam3-' + secrets.token_hex(12))")

if [ ! -f ".env" ]; then
    cat > .env << ENVEOF
# Auto-generated on $(date '+%Y-%m-%d %H:%M:%S')
HOST=0.0.0.0
PORT=${APP_PORT}
FLASK_DEBUG=False

SECRET_KEY=${SECRET_KEY}
ADMIN_TOKEN=${ADMIN_TOKEN}

USE_SSL=true

API_KEYS=${API_KEY_1},${API_KEY_2},${API_KEY_3}

SESSION_TIMEOUT=60
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION=15

MAX_CONTENT_LENGTH=52428800
ALLOWED_EXTENSIONS=png,jpg,jpeg,gif,bmp

VIDEO_FPS=10
VIDEO_QUALITY=95

LOG_LEVEL=INFO
LOG_MAX_SIZE=10485760
LOG_BACKUP_COUNT=5
ENVEOF

    chmod 600 .env
    log_ok ".env file created with secure random keys"
    echo ""
    echo "  📝 API Keys for Raspberry Pi cameras:"
    echo "     Camera 1: ${API_KEY_1}"
    echo "     Camera 2: ${API_KEY_2}"
    echo "     Camera 3: ${API_KEY_3}"
    echo ""
else
    log_warn ".env already exists — not overwriting"
fi

# =============================================================================
# STEP 7: Initialize Database
# =============================================================================
log_step "7/8 — Initializing database..."

python3 -c "
import sys
sys.path.insert(0, '.')
from src.database import init_database
init_database()
print('Database initialized successfully')
"

log_ok "SQLite database ready"

# =============================================================================
# STEP 8: Download cloudflared (for tunnel/online access)
# =============================================================================
log_step "8/8 — Setting up cloudflared tunnel binary..."

ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  CF_ARCH="amd64" ;;
    aarch64) CF_ARCH="arm64" ;;
    armv7l)  CF_ARCH="arm"   ;;
    *)       CF_ARCH="amd64" ;;
esac

if [ ! -f "src/cloudflared" ]; then
    wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" \
        -O src/cloudflared
    chmod +x src/cloudflared
    log_ok "cloudflared downloaded (linux-${CF_ARCH})"
else
    log_ok "cloudflared already exists"
fi

# =============================================================================
# STEP 9: Set File Permissions
# =============================================================================
log_step "BONUS — Setting secure file permissions..."

chown -R ${APP_USER}:${APP_USER} "$APP_DIR"
chmod 700 certs/
chmod 600 certs/key.pem
chmod 600 .env
chmod 600 auth.json 2>/dev/null || true
chmod 755 start.sh

log_ok "File permissions secured"

# =============================================================================
# DONE
# =============================================================================
echo ""
echo "================================================================"
echo "  ✅ SETUP COMPLETE!"
echo "================================================================"
echo ""
echo "  To start the application:"
echo "    cd \"$APP_DIR\""
echo "    source .venv/bin/activate"
echo "    python run.py"
echo ""
echo "  Or use the start script:"
echo "    bash start.sh"
echo ""
IP_ADDR=$(hostname -I | awk '{print $1}')
echo "  Access URL: https://${IP_ADDR}:${APP_PORT}"
echo "  Login:      admin / admin (change immediately!)"
echo ""
echo "  Firewall Status:"
ufw status | grep -E "ALLOW|DENY" | head -5
echo ""
echo "  Security Checklist:"
echo "  [x] UFW firewall enabled"
echo "  [x] SSL/TLS certificate generated"
echo "  [x] Secure SECRET_KEY generated"
echo "  [x] Random API keys for RPi cameras"
echo "  [x] Security headers enabled"
echo "  [x] Password hashing (PBKDF2-SHA256, 100k iterations)"
echo "  [x] Login attempt lockout"
echo "  [x] Session timeout"
echo "  [ ] Change default admin password!"
echo ""
echo "================================================================"
