# VM Setup Guide — Complete Installation on Virtual Machine

> **ตอบข้อกำหนดอาจารย์:** ให้จำลอง Linux Server บน VM → ติดตั้งให้เสร็จสมบูรณ์ → จดทุก Command → ค่อยย้ายไป Raspberry Pi  
> **Date:** February 2026  
> **Goal:** Develop and test on VM first, then replicate on Raspberry Pi

---

## Table of Contents

1. [VM Creation (VirtualBox)](#1-vm-creation-virtualbox)
2. [Ubuntu Installation](#2-ubuntu-installation)
3. [System Configuration](#3-system-configuration)
4. [Project Installation (Step-by-Step)](#4-project-installation-step-by-step)
5. [Database Setup & Verification](#5-database-setup--verification)
6. [Security Hardening](#6-security-hardening)
7. [Testing & Validation](#7-testing--validation)
8. [Migration to Raspberry Pi](#8-migration-to-raspberry-pi)
9. [Complete Command Log](#9-complete-command-log)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. VM Creation (VirtualBox)

### 1.1 Download Required Software
```
VirtualBox: https://www.virtualbox.org/wiki/Downloads
Ubuntu ISO: https://ubuntu.com/download/server (Ubuntu 24.04 LTS)
```

### 1.2 Create New Virtual Machine

| Setting | Value |
|---------|-------|
| Name | `AeroponicServer` |
| Type | Linux |
| Version | Ubuntu (64-bit) |
| RAM | 2048 MB (2 GB) minimum |
| Hard Disk | VDI, Dynamically allocated, 20 GB |
| Network | Bridged Adapter (to access from host) |
| CPU | 2 cores |

### 1.3 VirtualBox Network Configuration

**For Host-to-VM access:**
1. Select VM → Settings → Network
2. Adapter 1:
   - Attached to: **Bridged Adapter**
   - Name: Select your physical network adapter
3. This gives the VM its own IP on the local network

**Alternative: Port Forwarding (NAT)**
1. Adapter 1 → Attached to: NAT
2. Advanced → Port Forwarding:
   - Rule 1: Host `8443` → Guest `8443` (HTTPS)
   - Rule 2: Host `2222` → Guest `22` (SSH)

### 1.4 Boot from Ubuntu ISO
1. Storage → Controller: IDE → Add ISO
2. Start VM
3. Proceed to Ubuntu installation

---

## 2. Ubuntu Installation

### 2.1 Installation Steps
1. Select "Install Ubuntu Server"
2. Language: English
3. Keyboard: Your preference
4. Network: Automatic (DHCP)
5. Storage: Use entire disk
6. Profile:
   - Name: `admin1`
   - Server name: `aeroponic-server`
   - Username: `admin1`
   - Password: (set strong password)
7. SSH: Install OpenSSH server ✓
8. Complete installation and reboot

### 2.2 First Login & Find IP
```bash
# Login with your credentials
# Find the VM's IP address:
ip addr show | grep "inet " | grep -v "127.0.0.1"
# Note this IP — you'll need it to access from host machine
```

### 2.3 SSH from Host (Optional but recommended)
```bash
# From your host machine terminal:
ssh admin1@VM_IP_ADDRESS

# If using NAT port forwarding:
ssh -p 2222 admin1@localhost
```

---

## 3. System Configuration

### 3.1 Update System
```bash
sudo apt update -y
sudo apt upgrade -y
```

### 3.2 Set Timezone
```bash
sudo timedatectl set-timezone Asia/Bangkok
timedatectl status
```

### 3.3 Install Required System Packages
```bash
sudo apt install -y \
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
    libffi-dev \
    net-tools \
    htop
```

### 3.4 Verify Installations
```bash
python3 --version          # Expected: Python 3.12.x
pip3 --version             # Expected: pip 24.x
sqlite3 --version          # Expected: 3.45.x
openssl version            # Expected: OpenSSL 3.x
ufw --version              # Expected: ufw 0.36.x
```

**Record output:**
```bash
echo "=== System Info ===" > ~/install_log.txt
date >> ~/install_log.txt
uname -a >> ~/install_log.txt
python3 --version >> ~/install_log.txt 2>&1
pip3 --version >> ~/install_log.txt 2>&1
sqlite3 --version >> ~/install_log.txt 2>&1
openssl version >> ~/install_log.txt 2>&1
echo "=== Installed Packages ===" >> ~/install_log.txt
dpkg -l | grep -E "python3|ufw|openssl|sqlite3|opencv|curl|wget" >> ~/install_log.txt
```

---

## 4. Project Installation (Step-by-Step)

### 4.1 Transfer Project to VM

**Option A: Using SCP (from host)**
```bash
scp -r "/path/to/Task Description 4" admin1@VM_IP:~/Desktop/
```

**Option B: Using Git (if project is in a repository)**
```bash
cd ~/Desktop
git clone YOUR_REPO_URL "Task Description 4"
```

**Option C: Using Shared Folder (VirtualBox)**
1. VirtualBox → Settings → Shared Folders → Add
2. Mount path: `/mnt/shared`
3. Inside VM:
```bash
sudo mount -t vboxsf SharedFolderName /mnt/shared
cp -r /mnt/shared/"Task Description 4" ~/Desktop/
```

### 4.2 Navigate to Project
```bash
cd ~/Desktop/"Task Description 4"
ls -la
```

### 4.3 Create Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate

# Verify virtual environment is active
which python3
# Expected: /home/admin1/Desktop/Task Description 4/.venv/bin/python3
```

### 4.4 Upgrade pip and Install Dependencies
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

**Record installed packages:**
```bash
pip list > ~/pip_packages.txt
echo "=== Python Packages ===" >> ~/install_log.txt
pip list >> ~/install_log.txt
```

### 4.5 Create `.env` Configuration File
```bash
# Generate secure keys
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ADMIN_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(16))")
API_KEY_1=$(python3 -c "import secrets; print('rpi-cam1-' + secrets.token_hex(16))")
API_KEY_2=$(python3 -c "import secrets; print('rpi-cam2-' + secrets.token_hex(16))")

# Create .env file
cat > .env << EOF
# Server Configuration
HOST=0.0.0.0
PORT=8443
FLASK_DEBUG=False

# Security Keys (auto-generated)
SECRET_KEY=${SECRET_KEY}
ADMIN_TOKEN=${ADMIN_TOKEN}

# SSL/TLS
USE_SSL=true

# API Keys for Raspberry Pi (auto-generated)
API_KEYS=${API_KEY_1},${API_KEY_2}

# Session Settings
SESSION_TIMEOUT=60
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION=15

# Logging
LOG_LEVEL=INFO
EOF

# Secure file permissions
chmod 600 .env

echo "Generated .env file:"
cat .env
```

### 4.6 Generate SSL Certificate
```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 \
    -keyout certs/key.pem \
    -out certs/cert.pem \
    -days 365 -nodes \
    -subj "/C=TH/ST=Bangkok/L=Bangkok/O=AeroponicFarm/OU=IT/CN=aeroponic.local"

chmod 600 certs/key.pem
chmod 700 certs/

# Verify certificate
openssl x509 -in certs/cert.pem -text -noout | head -15
```

### 4.7 Initialize Database
```bash
source .venv/bin/activate
python3 -c "
import sys; sys.path.insert(0, '.')
from src.database import init_database
init_database()
print('✅ Database initialized successfully')
"

# Verify database
sqlite3 aeroponic_snapshots.db ".tables"
# Expected output: categories  snapshots  video_generations
sqlite3 aeroponic_snapshots.db ".schema snapshots" | head -20
```

### 4.8 Create Required Directories
```bash
mkdir -p snapshots generated_videos logs
ls -la
```

---

## 5. Database Setup & Verification

### 5.1 Database Schema
```bash
sqlite3 aeroponic_snapshots.db << 'EOF'
.headers on
.mode column
SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;
EOF
```

Expected tables:
| Table | Purpose |
|-------|---------|
| `categories` | Hierarchical category classification |
| `snapshots` | Snapshot metadata (filepath, capture time, tags) |
| `video_generations` | Generated video records |

### 5.2 Verify Database Operations
```bash
source .venv/bin/activate
python3 -c "
import sys; sys.path.insert(0, '.')
from src.database import init_database, get_database_stats, add_category

init_database()

# Add test category
cat_id = add_category('Root System', description='Root growth monitoring')
print(f'Created category ID: {cat_id}')

# Check stats
stats = get_database_stats()
print(f'Categories: {stats[\"total_categories\"]}')
print(f'Snapshots: {stats[\"total_snapshots\"]}')
print(f'Videos: {stats[\"total_videos\"]}')
print('✅ Database operations verified')
"
```

### 5.3 Test Batch Import (Recursive Folder Traversal)
```bash
# Create test folder structure matching farm camera layout
mkdir -p /tmp/test_import/cam1/1_01-15
mkdir -p /tmp/test_import/cam1/2_01-16
mkdir -p /tmp/test_import/cam2/1_01-15

# Create dummy test images
python3 -c "
from PIL import Image
import os
dirs = [
    '/tmp/test_import/cam1/1_01-15',
    '/tmp/test_import/cam1/2_01-16',
    '/tmp/test_import/cam2/1_01-15',
]
for d in dirs:
    for i in range(3):
        img = Image.new('RGB', (100, 100), color=(i*50, 100, 150))
        img.save(os.path.join(d, f'test_{i}.jpg'))
        print(f'  Created: {d}/test_{i}.jpg')
print('✅ Test images created')
"

# Run batch import with structure parsing
source .venv/bin/activate
python3 scripts/batch_import.py /tmp/test_import \
    --parse-structure \
    --source "VM Test Import" \
    --tags "test,vm"

# Verify import
sqlite3 aeroponic_snapshots.db "SELECT COUNT(*) as total FROM snapshots;"
```

---

## 6. Security Hardening

### 6.1 Configure UFW Firewall
```bash
# Set default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (essential for remote access)
sudo ufw allow 22/tcp comment 'SSH access'

# Allow HTTPS for web application
sudo ufw allow 8443/tcp comment 'Aeroponic HTTPS'

# Enable firewall
echo "y" | sudo ufw enable

# Verify status
sudo ufw status verbose
```

**Expected output:**
```
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere        # SSH access
8443/tcp                   ALLOW IN    Anywhere        # Aeroponic HTTPS
```

### 6.2 Secure File Permissions
```bash
cd ~/Desktop/"Task Description 4"

# Sensitive files: owner read/write only
chmod 600 .env
chmod 600 auth.json 2>/dev/null || true
chmod 600 certs/key.pem

# Directories
chmod 700 certs/

# Verify permissions
ls -la .env certs/ auth.json 2>/dev/null
```

### 6.3 Application Security Features

The application includes built-in security:

| Feature | Implementation | Config |
|---------|---------------|--------|
| **Password Hashing** | PBKDF2-HMAC-SHA256, 100k iterations | `src/auth.py` |
| **Login Lockout** | 5 failed attempts → 15 min lock | `.env: MAX_LOGIN_ATTEMPTS` |
| **Session Timeout** | Auto-expire after 60 min | `.env: SESSION_TIMEOUT` |
| **Strong Password** | Min 8 chars, upper+lower+digit | `auth.json: security_settings` |
| **Security Headers** | HSTS, X-Frame, X-XSS, CSP | `src/app.py` |
| **API Key Auth** | Required for /api/upload | `.env: API_KEYS` |
| **Path Traversal** | `os.path.realpath()` validation | `src/app.py` |
| **SSL/TLS** | RSA 4096-bit self-signed cert | `certs/` |

### 6.4 IP Whitelisting (Optional)
Through the web interface: Security Settings → Allowed IPs
```
# Only allow specific IPs to connect
# Leave empty to allow all IPs
# Example: 192.168.1.0/24 (allow entire local network)
```

### 6.5 Change Default Admin Password
```bash
# IMPORTANT: Change default password on first login!
# 1. Open https://VM_IP:8443
# 2. Login: admin / admin
# 3. Go to Security Settings
# 4. Change password to a strong password
```

---

## 7. Testing & Validation

### 7.1 Start the Application
```bash
cd ~/Desktop/"Task Description 4"
source .venv/bin/activate
python3 run.py
```

**Expected output:**
```
🔒 SSL/TLS ENABLED — using certs from certs/
============================================================
🌱 Aeroponic Snapshot Database
============================================================
📁 Project Root: /home/admin1/Desktop/Task Description 4
📁 Snapshots: /home/admin1/Desktop/Task Description 4/snapshots
📁 Videos: /home/admin1/Desktop/Task Description 4/generated_videos
📁 Logs: /home/admin1/Desktop/Task Description 4/logs
🗄️  Database: /home/admin1/Desktop/Task Description 4/aeroponic_snapshots.db
============================================================
🌐 Starting server at https://0.0.0.0:8443
============================================================
```

### 7.2 Test Web Interface
```bash
# From VM:
curl -sk https://localhost:8443 | head -5

# From host machine browser:
# https://VM_IP:8443
# Accept self-signed certificate warning → Proceed
```

### 7.3 Test API Upload
```bash
# Test connectivity
curl -sk https://localhost:8443/api/upload/test | python3 -m json.tool

# Upload test image
curl -sk -X POST https://localhost:8443/api/upload \
    -F "file=@snapshots/test_image.jpg" \
    -F "api_key=$(grep API_KEYS .env | cut -d= -f2 | cut -d, -f1)" \
    -F "camera_id=cam1" \
    -F "project_name=VM Test"
```

### 7.4 Test Recursive Import
```bash
source .venv/bin/activate
python3 scripts/batch_import.py /tmp/test_import --analyze-only
python3 scripts/batch_import.py /tmp/test_import --parse-structure --source "Test"
```

### 7.5 Test Video Generation
```bash
# Import at least 5 test images, then generate video via web interface
# Or via API:
curl -sk "https://localhost:8443/api/snapshots" | python3 -m json.tool | head -20
```

### 7.6 Full System Verification
```bash
source .venv/bin/activate
python3 scripts/check_system.py
```

### 7.7 Record Test Results
```bash
echo "=== Test Results $(date) ===" >> ~/install_log.txt
echo "Web Interface: OK" >> ~/install_log.txt
echo "API Upload: OK" >> ~/install_log.txt
echo "Database: OK" >> ~/install_log.txt
echo "SSL/TLS: OK" >> ~/install_log.txt
echo "Firewall: $(sudo ufw status | head -1)" >> ~/install_log.txt
```

---

## 8. Migration to Raspberry Pi

### 8.1 Prerequisites
- Raspberry Pi 4 (4 GB RAM recommended) or newer
- Raspberry Pi OS (64-bit, based on Debian Bookworm)
- MicroSD card 32 GB+
- Network connection (Ethernet recommended)
- Camera Module v2 or HQ Camera

### 8.2 Migration Steps

**Step 1: Copy project to Raspberry Pi**
```bash
# From your VM or host machine:
scp -r ~/Desktop/"Task Description 4" pi@RPI_IP:~/Desktop/
```

**Step 2: SSH into Raspberry Pi**
```bash
ssh pi@RPI_IP
```

**Step 3: Run automated setup script**
```bash
cd ~/Desktop/"Task Description 4"
sudo bash setup_raspberry_pi.sh
```

This script automatically performs ALL steps from sections 3–6:
- System update
- Package installation
- UFW firewall configuration
- Python virtual environment
- pip dependencies
- SSL certificate generation
- .env configuration with random keys
- cloudflared download (ARM architecture)

**Step 4: Verify on Raspberry Pi**
```bash
source .venv/bin/activate
python3 run.py
```

**Step 5: Configure camera upload (crontab)**
```bash
crontab -e
# Add:
*/30 * * * * /usr/bin/python3 /home/pi/Desktop/Task\ Description\ 4/raspberry_pi_scripts/upload_snapshot.py --capture >> /home/pi/upload.log 2>&1
```

### 8.3 Architecture Note (Raspberry Pi ARM)

Some packages differ on ARM:
```bash
# If opencv-python fails on ARM, use headless version:
pip install opencv-python-headless

# Download ARM version of cloudflared:
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64" -O src/cloudflared
chmod +x src/cloudflared
```

---

## 9. Complete Command Log

Below is every command executed during VM setup, in order:

```bash
# ============================================================
# COMPLETE INSTALLATION LOG — Copy and run on fresh Ubuntu VM
# ============================================================

# --- System Update ---
sudo apt update -y
sudo apt upgrade -y

# --- Install System Packages ---
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    build-essential libopencv-dev ufw wget curl git openssl \
    sqlite3 libsqlite3-dev libjpeg-dev libpng-dev libffi-dev \
    net-tools htop

# --- Set Timezone ---
sudo timedatectl set-timezone Asia/Bangkok

# --- Navigate to Project ---
cd ~/Desktop/"Task Description 4"

# --- Python Virtual Environment ---
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# --- Generate Secure Keys ---
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ADMIN_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(16))")
API_KEY_1=$(python3 -c "import secrets; print('rpi-cam1-' + secrets.token_hex(16))")
API_KEY_2=$(python3 -c "import secrets; print('rpi-cam2-' + secrets.token_hex(16))")

# --- Create .env ---
cat > .env << EOF
HOST=0.0.0.0
PORT=8443
FLASK_DEBUG=False
SECRET_KEY=${SECRET_KEY}
ADMIN_TOKEN=${ADMIN_TOKEN}
USE_SSL=true
API_KEYS=${API_KEY_1},${API_KEY_2}
SESSION_TIMEOUT=60
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION=15
LOG_LEVEL=INFO
EOF
chmod 600 .env

# --- Generate SSL Certificate ---
mkdir -p certs
openssl req -x509 -newkey rsa:4096 \
    -keyout certs/key.pem -out certs/cert.pem \
    -days 365 -nodes \
    -subj "/C=TH/ST=Bangkok/L=Bangkok/O=AeroponicFarm/OU=IT/CN=aeroponic.local"
chmod 600 certs/key.pem
chmod 700 certs/

# --- Initialize Database ---
python3 -c "import sys; sys.path.insert(0,'.'); from src.database import init_database; init_database()"

# --- Create Directories ---
mkdir -p snapshots generated_videos logs

# --- Firewall ---
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH access'
sudo ufw allow 8443/tcp comment 'Aeroponic HTTPS'
echo "y" | sudo ufw enable
sudo ufw status verbose

# --- Secure Permissions ---
chmod 600 .env
chmod 600 auth.json 2>/dev/null || true
chmod 600 certs/key.pem
chmod 700 certs/

# --- Start Application ---
source .venv/bin/activate
python3 run.py
```

---

## 10. Troubleshooting

### Issue: "externally-managed-environment" error
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Issue: OpenCV installation fails
```bash
pip install opencv-python-headless
```

### Issue: Port 8443 already in use
```bash
sudo lsof -i :8443
# Kill the process or change PORT in .env
```

### Issue: Cannot access from host browser
```bash
# Check VM IP
ip addr show
# Check firewall allows port
sudo ufw status
# Ensure bridged network or port forwarding is configured
```

### Issue: SSL certificate errors
```bash
# Regenerate certificate
rm certs/cert.pem certs/key.pem
openssl req -x509 -newkey rsa:4096 \
    -keyout certs/key.pem -out certs/cert.pem \
    -days 365 -nodes -subj "/CN=aeroponic.local"
chmod 600 certs/key.pem
```

### Issue: Database locked
```bash
# Check for orphan connections
fuser aeroponic_snapshots.db
# Restart the application
```

### Issue: Low disk space
```bash
df -h
du -sh snapshots/ generated_videos/
# Clean up old videos if needed
```
