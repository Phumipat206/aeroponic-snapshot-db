# Installation & Verification Guide

## Automated Installation (Recommended)

The easiest way to install and run the system:

```bash
bash start.sh
```

This script handles all steps below automatically. Continue reading only if you prefer manual installation.

---

## Manual Step-by-Step Installation

### Prerequisites
- Ubuntu 22.04+ / Debian 12+ / Raspberry Pi OS
- Python 3.10 or higher
- pip and venv (Python package tools)
- 100 MB free disk space (minimum)

### Step 1: Install System Packages

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv openssl curl
```

### Step 2: Verify Python Installation

```bash
python3 --version
```

Expected output: `Python 3.10.x` or higher.

### Step 3: Navigate to Project Folder

```bash
cd /path/to/project
```

### Step 4: Create Virtual Environment and Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

This will install:
- Flask (web framework)
- Werkzeug (WSGI utilities)
- Pillow (image processing)
- python-dateutil (date parsing)
- opencv-python (video generation)
- numpy (numerical operations)
- python-dotenv (environment configuration)
- watchdog (file system monitoring)
- requests (HTTP client)

**Installation time:** ~2–5 minutes depending on internet speed.

### Step 5: Create Configuration File

```bash
cp .env.example .env
# Edit .env and set a secure SECRET_KEY:
python3 -c "import secrets; print(secrets.token_hex(32))"
# Paste the output as the SECRET_KEY value in .env
chmod 600 .env
```

### Step 6: Generate SSL Certificate

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 \
    -keyout certs/key.pem -out certs/cert.pem \
    -days 365 -nodes \
    -subj "/C=TH/ST=Bangkok/L=Bangkok/O=AeroponicFarm/CN=$(hostname)"
chmod 600 certs/key.pem
```

### Step 7: Initialize Database

```bash
source .venv/bin/activate
python3 -c "import sys; sys.path.insert(0,'.'); from src.database import init_database; init_database()"
```

### Step 8: Start the Application

```bash
source .venv/bin/activate
python run.py
```

Expected output:
```
 * Serving Flask app 'src.app'
 * Running on https://0.0.0.0:8443
```

### Step 9: Access Web Interface

1. Open your browser
2. Go to: **https://localhost:8443**
3. Accept the self-signed certificate warning (Advanced → Proceed)
4. Log in with: `admin` / `admin`
5. **Change the password immediately** via Security Settings

---

## Common Installation Issues

### Issue 1: "python3: command not found"
```bash
sudo apt install -y python3 python3-pip python3-venv
```

### Issue 2: Permission denied
```bash
pip install --user -r requirements.txt
```

### Issue 3: OpenCV installation fails (especially on Raspberry Pi)
```bash
pip install opencv-python-headless
```

### Issue 4: Port 8443 already in use
Edit `.env` and change:
```
PORT=8444
```

### Issue 5: "externally-managed-environment" error
Use a virtual environment (which `start.sh` does automatically):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Verification Checklist

After installation, verify:

- [ ] Python version is 3.10+
- [ ] Virtual environment created (`.venv/` exists)
- [ ] All dependencies installed (`pip list` shows Flask, opencv-python, etc.)
- [ ] `.env` file created with secure keys
- [ ] SSL certificate exists (`certs/cert.pem`, `certs/key.pem`)
- [ ] Database created (`aeroponic_snapshots.db`)
- [ ] `snapshots/` folder created
- [ ] `generated_videos/` folder created
- [ ] Web server starts without errors
- [ ] Can access https://localhost:8443
- [ ] Login works with admin/admin
- [ ] Navigation menu works (all pages load)

---

## First Use Test

### Test 1: Upload a Snapshot
1. Go to the **Upload** page
2. Select any image file
3. Click **Upload Snapshot**
4. Should see a success message

### Test 2: View Statistics
1. Go to the **Statistics** page
2. Should show: Total Snapshots, Total Categories, Total Videos, Total Storage

### Test 3: Query Snapshots
1. Go to the **Query** page
2. Leave all filters empty
3. Click **Search Snapshots**
4. Should see your uploaded snapshot

### Test 4: Generate Video
1. Upload 5–10 test images
2. Go to **Generate Video**
3. Leave filters empty, set FPS to 10
4. Click **Generate Video**
5. Should produce an MP4 file

---

## Performance Expectations

| Operation | Time |
|-----------|------|
| Upload per image | < 1 second |
| Query thousands of snapshots | < 100 ms |
| Video from 10 snapshots | 2–5 seconds |
| Video from 100 snapshots | 10–20 seconds |
| Video from 1,000 snapshots | 1–3 minutes |

---

## Network Access

To access from other devices on the same network:

1. Find your IP address:
   ```bash
   hostname -I
   ```
2. The server already binds to `0.0.0.0`, so visit:
   ```
   https://YOUR_IP:8443
   ```

3. (Optional) Open the firewall:
   ```bash
   sudo ufw allow 8443/tcp
   ```

---

## Uninstallation

1. Stop the application (Ctrl+C)
2. Delete the project folder
3. (Optional) Remove the virtual environment: `rm -rf .venv`

All data is completely contained in the project folder. No system-wide changes are made (except optional UFW rules).
