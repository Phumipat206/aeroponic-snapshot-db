# Aeroponic Snapshot Database — User Guide

Complete guide to install, run, and use the Aeroponic Snapshot Database system.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Running the Application](#running-the-application)
4. [First Login](#first-login)
5. [Features Overview](#features-overview)
6. [Online Access (Tunnel)](#online-access-tunnel)
7. [Raspberry Pi Integration](#raspberry-pi-integration)
8. [User Management & Permissions](#user-management--permissions)
9. [Troubleshooting](#troubleshooting)
10. [Configuration Reference](#configuration-reference)

---

## System Requirements

### Minimum Requirements
- **OS:** Ubuntu 20.04+, Debian 11+, Raspberry Pi OS, macOS 12+, or Windows 10+
- **Python:** 3.10 or higher
- **RAM:** 1 GB minimum (2 GB recommended)
- **Storage:** 500 MB for app + space for snapshots
- **Browser:** Chrome, Firefox, Safari, or Edge (modern versions)

### Required Software
| Software | Purpose | Install Command |
|----------|---------|-----------------|
| Python 3 | Runtime | `sudo apt install python3 python3-pip python3-venv` |
| OpenSSL | SSL certificates | `sudo apt install openssl` |
| Git | Clone repository | `sudo apt install git` |

### Optional Software
| Software | Purpose | Install Command |
|----------|---------|-----------------|
| cloudflared | Online access tunnel | Auto-downloaded by `start.sh` |

---

## Installation

### Linux / macOS / Raspberry Pi

```bash
# 1. Clone the repository
git clone https://github.com/Phumipat206/aeroponic-snapshot-db.git
cd aeroponic-snapshot-db

# 2. Run the setup script (does everything automatically)
bash start.sh
```

The `start.sh` script automatically:
- Creates Python virtual environment
- Installs all dependencies
- Generates secure `.env` configuration
- Creates SSL certificates
- Downloads cloudflared binary
- Initializes the database
- Starts the server

### Windows

```cmd
# 1. Clone the repository
git clone https://github.com/Phumipat206/aeroponic-snapshot-db.git
cd aeroponic-snapshot-db

# 2. Run the setup script
start.bat
```

### Manual Installation (All Platforms)

If the automatic scripts don't work:

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate     # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create directories
mkdir -p snapshots generated_videos logs certs

# 4. Copy and edit configuration
cp .env.example .env
# Edit .env and set SECRET_KEY to a random string

# 5. Generate SSL certificate (optional but recommended)
openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes -subj "/CN=localhost"

# 6. Run the application
python run.py
```

---

## Running the Application

### Start the Server

**Linux/macOS:**
```bash
cd aeroponic-snapshot-db
bash start.sh
```

**Windows:**
```cmd
cd aeroponic-snapshot-db
start.bat
```

**Manual (if already set up):**
```bash
source .venv/bin/activate
python run.py
```

### Access the Application

After starting, the server runs on:

| Access Type | URL |
|-------------|-----|
| Local | https://localhost:8443 |
| Network | https://YOUR_IP:8443 |
| Online (if tunnel active) | https://xxx.trycloudflare.com |

> **Note:** Your browser will show a security warning for the self-signed certificate. Click "Advanced" → "Proceed" to continue.

### Stop the Server

Press `Ctrl+C` in the terminal where the server is running.

---

## First Login

### Default Credentials

| Username | Password | Role |
|----------|----------|------|
| admin | admin | Administrator |

### ⚠️ Important: Change Password Immediately

1. Login with `admin` / `admin`
2. Go to **Security** (in the sidebar)
3. Click **Change Password** tab
4. Enter current password and new password
5. Click **Change Password**

---

## Features Overview

### Dashboard
The home page showing system statistics:
- Total snapshots
- Total categories
- Total videos
- Storage used
- Quick action buttons

### Upload Snapshots
Upload individual plant images:
1. Click **Upload** in the sidebar
2. Select an image file (JPG, PNG, GIF, BMP)
3. Optionally set:
   - Category
   - Capture time
   - Tags
   - Notes
4. Click **Upload Snapshot**

### Search / Query
Find snapshots with filters:
1. Click **Search** in the sidebar
2. Set filters:
   - Date range
   - Category
   - Project name
   - Camera ID
   - Keywords
3. Click **Search Snapshots**
4. View results with pagination

### Daily View
Find snapshots taken at the same time each day:
1. Click **Daily View** in the sidebar
2. Set time: Hour and Minute
3. Set tolerance (±minutes)
4. Click **Find Daily Snapshots**

### Generate Video
Create time-lapse videos from snapshots:
1. Click **Create Video** in the sidebar
2. Select snapshots by:
   - Category
   - Date range
   - Project & Camera
3. Configure video:
   - FPS (frames per second)
   - Show timestamps overlay
4. Click **Generate Video**
5. Wait for processing
6. Download the MP4 file

### Categories
Organize snapshots into categories:
1. Click **Categories** in the sidebar
2. View existing categories
3. Add new categories with name and description
4. Delete categories (snapshots moved to uncategorized)

### Import
Bulk import from local folders:
1. Click **Import** in the sidebar
2. Enter folder path
3. Enable **Smart Detect** to auto-detect project/camera from path
4. Click **Start Import**

### Statistics
View system analytics:
- Snapshots per category
- Monthly upload trends
- Storage breakdown

### Security Settings
(Admin only) Manage users and security:
- **General:** Login requirements, session timeout, lockout settings
- **Users:** Add/delete users, change roles
- **Permissions:** Set per-user access to specific features
- **Sessions:** View and revoke active sessions
- **Login History:** Monitor login attempts

---

## Online Access (Tunnel)

Make your system accessible from anywhere in the world using Cloudflare Tunnel.

### Enable Online Access

1. Click **Online Access** in the sidebar
2. Click **Start Online Access**
3. Wait 10-20 seconds
4. Copy the generated URL (e.g., `https://random-name.trycloudflare.com`)
5. Share this URL with anyone who needs access

### Requirements for Online Access

- Internet connection
- `cloudflared` binary (auto-downloaded by `start.sh`)
- Port 8443 accessible locally

### Troubleshooting Online Access

**"cloudflared not found" error:**

*Linux:*
```bash
# Re-run start.sh to download cloudflared
bash start.sh

# Or install manually:
sudo wget -O /usr/local/bin/cloudflared \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
sudo chmod +x /usr/local/bin/cloudflared
```

*Windows:*
```cmd
winget install Cloudflare.cloudflared
```

**Tunnel starts but no URL appears:**
- Check your internet connection
- The URL appears in the terminal logs
- Wait up to 30 seconds

**Tunnel URL changes every restart:**
This is normal for the free "Quick Tunnel" feature. For a permanent URL, set up a Cloudflare account and named tunnel.

---

## Raspberry Pi Integration

Upload snapshots automatically from Raspberry Pi cameras.

### Setup on Raspberry Pi

```bash
# Copy the script
scp raspberry_pi_scripts/upload_snapshot.* pi@raspberrypi:~/

# On the Raspberry Pi, edit the config
nano ~/upload_snapshot.sh
# Set: SERVER_URL and API_KEY
```

### Configuration

Edit `upload_snapshot.sh`:
```bash
SERVER_URL="https://YOUR_SERVER_IP:8443"
API_KEY="your-api-key-from-env-file"
CAMERA_ID="cam1"
PROJECT_NAME="tomato"
```

### Automatic Capture with Cron

Add to crontab (`crontab -e`):
```cron
# Capture and upload every hour
0 * * * * /home/pi/upload_snapshot.sh >> /home/pi/upload.log 2>&1

# Capture every 15 minutes
*/15 * * * * /home/pi/upload_snapshot.sh >> /home/pi/upload.log 2>&1
```

### API Keys

API keys are defined in `.env`:
```env
API_KEYS=rpi-cam1-secretkey,rpi-cam2-secretkey,rpi-cam3-secretkey
```

Each camera should use a unique API key.

---

## User Management & Permissions

### Roles

| Role | Description |
|------|-------------|
| **Admin** | Full access to all features including security settings |
| **Editor** | Can upload, edit, delete snapshots and videos |
| **Viewer** | Read-only access to view snapshots and videos |

### Adding a New User

1. Go to **Security** → **Users** tab
2. Click **Add User**
3. Fill in:
   - Username (required)
   - Display Name
   - Password (required)
   - Role
4. Click **Create User**

### Changing User Permissions

1. Go to **Security** → **Permissions** tab
2. Select a user from the dropdown
3. Check/uncheck permissions
4. Click **Save Permissions**

### Permission Types

| Permission | Description |
|------------|-------------|
| Dashboard | View the home dashboard |
| Upload | Upload new snapshots |
| Search | Search and query snapshots |
| View Snapshots | View snapshot details and images |
| Edit Snapshots | Edit snapshot metadata |
| Delete Snapshots | Delete snapshots |
| Categories | View categories |
| Manage Categories | Add/delete categories |
| Generate Video | Create time-lapse videos |
| Videos | View videos list |
| Delete Videos | Delete videos |
| Import | Import from folders |
| Statistics | View system statistics |
| Online Access | Manage tunnel settings |
| Security | Access security settings (admin only) |

---

## Troubleshooting

### Application Won't Start

**Error: `python3: command not found`**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3 python3-pip python3-venv

# macOS
brew install python3
```

**Error: `ModuleNotFoundError: No module named 'xxx'`**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

**Error: `Address already in use`**
```bash
# Find and kill the process using port 8443
sudo lsof -i :8443
sudo kill -9 <PID>
```

### SSL Certificate Errors

**Browser shows "Your connection is not private":**
This is normal for self-signed certificates. Click "Advanced" → "Proceed to localhost".

**Error: `SSL certificate problem`**
```bash
# Regenerate the certificate
rm -rf certs/*.pem
bash start.sh
```

### Database Issues

**Error: `database is locked`**
```bash
# The app uses SQLite WAL mode. If truly locked:
cp aeroponic_snapshots.db aeroponic_snapshots.db.backup
# Restart the application
```

**Reset database:**
```bash
rm aeroponic_snapshots.db
python run.py  # Creates new empty database
```

### Video Generation Fails

**Error: `opencv not found`**
```bash
pip install opencv-python
```

**Error: `No snapshots found`**
- Check your date range includes snapshots
- Verify snapshots exist in the database

### Login Issues

**Forgot admin password:**
```bash
# Delete auth.json to reset (creates new admin/admin)
rm auth.json
python run.py
```

**Account locked out:**
Wait for the lockout duration (default: 15 minutes) or delete `auth.json`.

---

## Configuration Reference

All configuration is in `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| HOST | 0.0.0.0 | Listen address |
| PORT | 8443 | Server port |
| FLASK_DEBUG | False | Debug mode |
| SECRET_KEY | (random) | Session encryption key |
| ADMIN_TOKEN | (random) | API admin token |
| USE_SSL | true | Enable HTTPS |
| API_KEYS | (random) | Comma-separated API keys for Raspberry Pi |
| SESSION_TIMEOUT | 60 | Login session timeout (minutes) |
| MAX_LOGIN_ATTEMPTS | 5 | Failed logins before lockout |
| LOCKOUT_DURATION | 15 | Lockout time (minutes) |
| MAX_CONTENT_LENGTH | 52428800 | Max upload size (bytes, default 50MB) |
| ALLOWED_EXTENSIONS | png,jpg,jpeg,gif,bmp | Allowed image types |
| VIDEO_FPS | 10 | Default video framerate |
| VIDEO_QUALITY | 95 | JPEG quality for video frames |
| LOG_LEVEL | INFO | Logging verbosity |

---

## Support

For issues or questions:
1. Check this guide's [Troubleshooting](#troubleshooting) section
2. Review logs in the `logs/` folder
3. Open an issue on GitHub

---

*Last updated: February 2026*
