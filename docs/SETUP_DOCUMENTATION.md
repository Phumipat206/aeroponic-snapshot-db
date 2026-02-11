# Aeroponic Snapshot Database — Setup & Security Documentation

> **Date**: February 10, 2026  
> **Environment**: Ubuntu 24.04 LTS (tested on PC, deployable to Raspberry Pi)  
> **Goal**: Complete system installation with security hardening, ready for Raspberry Pi deployment

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Installed Packages](#2-installed-packages)
3. [Installation Commands](#3-installation-commands)
4. [Firewall Configuration (UFW)](#4-firewall-configuration-ufw)
5. [SSL/TLS Configuration](#5-ssltls-configuration)
6. [Security Settings](#6-security-settings)
7. [Configuration Files Modified](#7-configuration-files-modified)
8. [Usage](#8-usage)
9. [Raspberry Pi Deployment](#9-raspberry-pi-deployment)

---

## 1. System Overview

```
┌──────────────────────────────────────────────────┐
│              Ubuntu 24.04 LTS                    │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │  UFW Firewall                              │  │
│  │  • Default: DENY incoming, ALLOW outgoing  │  │
│  │  • Allow: SSH (22), HTTPS (8443)           │  │
│  ├────────────────────────────────────────────┤  │
│  │  Flask Application (Python 3.12)           │  │
│  │  • SSL/TLS (self-signed cert, RSA 4096)    │  │
│  │  • PBKDF2-SHA256 password hashing          │  │
│  │  • Login lockout (5 attempts → 15 min)     │  │
│  │  • Session timeout (60 min)                │  │
│  │  • Security headers (HSTS, X-Frame, etc.)  │  │
│  ├────────────────────────────────────────────┤  │
│  │  SQLite Database                           │  │
│  │  • aeroponic_snapshots.db                  │  │
│  │  • auth.json (users, sessions, lockout)    │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

---

## 2. Installed Packages

### System Packages (apt)

| Package | Purpose |
|---------|---------|
| `python3` | Python interpreter (3.12) |
| `python3-pip` | Python package manager |
| `python3-venv` | Virtual environment support |
| `python3-dev` | Python development headers |
| `build-essential` | C/C++ compiler (for compiling numpy, opencv) |
| `libopencv-dev` | OpenCV system library |
| `ufw` | Uncomplicated Firewall |
| `wget`, `curl` | File download utilities |
| `openssl` | SSL certificate generation |
| `sqlite3` | Database client |
| `libjpeg-dev`, `libpng-dev` | Image processing libraries |

### Python Packages (pip)

| Package | Version | Purpose |
|---------|---------|---------|
| `Flask` | 3.1.2 | Web framework |
| `Werkzeug` | 3.1.5 | WSGI toolkit |
| `python-dotenv` | 1.2.1 | Load .env configuration |
| `Pillow` | 12.1.0 | Image processing |
| `opencv-python` | 4.13.0.92 | Video/timelapse generation |
| `numpy` | 2.4.2 | Numerical operations |
| `watchdog` | 6.0.0 | File system monitoring |
| `python-dateutil` | 2.9.0.post0 | Date/time parsing |
| `requests` | 2.32.5 | HTTP requests |

---

## 3. Installation Commands

### 3.1 Update System
```bash
sudo apt update -y
sudo apt upgrade -y
```

### 3.2 Install System Packages
```bash
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    build-essential libopencv-dev ufw wget curl git openssl \
    sqlite3 libsqlite3-dev libjpeg-dev libpng-dev libffi-dev
```

### 3.3 Create Virtual Environment & Install Python Packages
```bash
cd /path/to/project
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 3.4 Configure Firewall
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8443/tcp comment 'Aeroponic HTTPS'
echo "y" | sudo ufw enable
sudo ufw status verbose
```

### 3.5 Generate SSL Certificate
```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 \
    -keyout certs/key.pem \
    -out certs/cert.pem \
    -days 365 -nodes \
    -subj "/C=TH/ST=Bangkok/L=Bangkok/O=AeroponicFarm/OU=IT/CN=aeroponic.local"
chmod 600 certs/key.pem
```

### 3.6 Create .env Configuration
```bash
# Generate secure keys
python3 -c "import secrets; print(secrets.token_hex(32))"  # → SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(16))"  # → ADMIN_TOKEN

# Create .env file (see section 7 for template)
chmod 600 .env
```

### 3.7 Download cloudflared (for online access)
```bash
# x86_64
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" -O src/cloudflared

# Raspberry Pi (ARM64)
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64" -O src/cloudflared

# Raspberry Pi (ARM32)
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm" -O src/cloudflared

chmod +x src/cloudflared
```

### 3.8 Run the Application
```bash
source .venv/bin/activate
python run.py
```

---

## 4. Firewall Configuration (UFW)

### Current Status
```
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere        # SSH
8443/tcp                   ALLOW IN    Anywhere        # Aeroponic HTTPS
```

### Rules Explained
- **Default incoming: DENY** — blocks all ports not explicitly opened
- **Default outgoing: ALLOW** — allows outbound connections
- **SSH (22):** Open for remote access
- **HTTPS (8443):** Open for the web application (changed from default Flask port 5000)
- Port 5000 (default Flask) is **blocked** in production mode

### Common Commands
```bash
sudo ufw status verbose     # View status
sudo ufw allow 8443/tcp     # Open port
sudo ufw delete allow 5000  # Close port
sudo ufw reload             # Reload rules
```

---

## 5. SSL/TLS Configuration

### Certificate Information
- **Type:** Self-signed X.509
- **Algorithm:** RSA 4096-bit
- **Hash:** SHA-256
- **Validity:** 365 days
- **Location:** `certs/cert.pem` (certificate), `certs/key.pem` (private key)

### Enable SSL
Set in `.env`:
```
USE_SSL=true
PORT=8443
```

### Verify Certificate
```bash
openssl x509 -in certs/cert.pem -text -noout | head -20
```

---

## 6. Security Settings

### 6.1 Password Hashing
- **Algorithm:** PBKDF2-HMAC-SHA256
- **Iterations:** 100,000
- **Salt:** 32 bytes random (unique per user)
- **Implementation:** `src/auth.py`

### 6.2 Login Protection

| Setting | Value | Description |
|---------|-------|-------------|
| `MAX_LOGIN_ATTEMPTS` | 5 | Maximum failed login attempts |
| `LOCKOUT_DURATION` | 15 min | Account lock duration after max attempts |
| `SESSION_TIMEOUT` | 60 min | Session auto-expiration |
| `enforce_strong_password` | true | Requires upper + lower + digit |
| `password_min_length` | 8 chars | Minimum password length |

### 6.3 Security Headers
Response headers added to every request:
```
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Strict-Transport-Security: max-age=31536000; includeSubDomains  (HTTPS only)
```

### 6.4 Path Traversal Protection
- All file-serving routes validate paths using `os.path.realpath()` to ensure files are within the upload folder
- Supports cross-OS path normalization (Windows ↔ Linux)

### 6.5 File Permissions
```bash
chmod 600 .env           # Owner read/write only
chmod 600 auth.json      # Owner read/write only
chmod 600 certs/key.pem  # Private key — owner only
chmod 700 certs/         # Directory — owner access only
```

---

## 7. Configuration Files Modified

### 7.1 `.env` (auto-generated by start.sh)
```env
HOST=0.0.0.0
PORT=8443
FLASK_DEBUG=False
SECRET_KEY=<random-64-hex-chars>
ADMIN_TOKEN=<random-32-hex-chars>
USE_SSL=true
API_KEYS=rpi-cam1-xxx,rpi-cam2-xxx,rpi-cam3-xxx
SESSION_TIMEOUT=60
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION=15
```

### 7.2 `run.py` (modified)
- Added SSL context support (`ssl_context` parameter)
- Reads `USE_SSL` from environment
- Loads cert/key from `certs/` directory

### 7.3 `src/app.py` (modified)
- Added `set_security_headers()` — applies security headers on every response
- Added `_normalize_filepath()` — cross-OS path support
- Fixed `serve_snapshot()` — uses path normalization
- Fixed `download_video()` — uses path normalization
- Fixed cloudflared detection — supports Linux binary
- Fixed `subprocess.Popen` — does not use `CREATE_NO_WINDOW` on Linux

### 7.4 `src/database.py` (modified)
- Added `_normalize_db_path()` — converts Windows paths in database
- Fixed `delete_snapshot()`, `delete_video()`, `cleanup_missing_files()` — uses path normalization

### 7.5 `requirements.txt` (modified)
- All package versions pinned exactly (no `>=` ranges)

---

## 8. Usage

### Start the Application
```bash
bash start.sh
```
Or manually:
```bash
source .venv/bin/activate
python run.py
```

### Access the Web Interface
- **URL:** https://localhost:8443 (or https://<IP>:8443)
- **Login:** admin / admin
- **Important:** Change the default password immediately after first login!

### Enable Online Access (Cloudflare Tunnel)
Click "Start Tunnel" on the Online Access page, or run:
```bash
./src/cloudflared tunnel --url http://localhost:8443
```

---

## 9. Raspberry Pi Deployment

### Method 1: Use the Setup Script (Recommended)
```bash
# 1. Copy the project to Raspberry Pi
scp -r "project-folder" pi@<RPI_IP>:~/Desktop/

# 2. SSH into Raspberry Pi
ssh pi@<RPI_IP>

# 3. Run setup script
cd ~/Desktop/project-folder
sudo bash setup_raspberry_pi.sh
```

The script automates everything:
- System updates
- Package installation
- Firewall configuration
- SSL certificate generation
- .env with secure random keys
- cloudflared download (ARM architecture)

### Method 2: Manual (follow commands in Section 3)

### Notes for Raspberry Pi
- Use `cloudflared-linux-arm64` instead of `cloudflared-linux-amd64`
- OpenCV may take longer to install on ARM — use `opencv-python-headless` if needed
- Recommended: Raspberry Pi 4 (4 GB RAM) or newer

---

## Security Checklist

- [x] UFW firewall enabled (deny incoming by default)
- [x] Port changed from default 5000 to 8443
- [x] SSL/TLS certificate (RSA 4096-bit)
- [x] Secure SECRET_KEY (random 64 hex chars)
- [x] Password hashing (PBKDF2-SHA256, 100k iterations)
- [x] Login lockout (5 attempts → 15 min lock)
- [x] Session timeout (60 min)
- [x] Strong password enforcement
- [x] Security HTTP headers (HSTS, X-Frame, XSS, etc.)
- [x] File permissions secured (.env, auth.json, private key)
- [x] Path traversal protection
- [x] Rate limiting on login
- [ ] **Change default admin password!**
