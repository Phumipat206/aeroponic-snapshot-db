# Aeroponic Snapshot Database

A snapshot management system for Aeroponic plant monitoring with time-lapse video generation.  
Supports **Ubuntu / Debian / Raspberry Pi OS / macOS / Windows**.

---

## Quick Start

### Linux / macOS / Raspberry Pi
```bash
git clone https://github.com/Phumipat206/aeroponic-snapshot-db.git
cd aeroponic-snapshot-db
bash start.sh
```

### Windows
```cmd
git clone https://github.com/Phumipat206/aeroponic-snapshot-db.git
cd aeroponic-snapshot-db
start.bat
```

Then open **https://localhost:8443** in your browser.

> **Default login:** `admin` / `admin` — change the password after first login!

> **Browser warning:** Click "Advanced" → "Proceed" to bypass the self-signed certificate warning.

---

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/USER_GUIDE.md) | Complete usage instructions |
| [Quick Start](docs/QUICKSTART.md) | Quick setup guide |
| [API Documentation](docs/API_DOCUMENTATION.md) | REST API reference |
| [Project Overview](docs/PROJECT_OVERVIEW.md) | Architecture overview |

---

## What `start.sh` Does

| Step | Description |
|------|-------------|
| 1. Python | Checks that Python 3 is installed |
| 2. Virtual Environment | Creates `.venv` and installs all dependencies |
| 3. Directories | Creates `snapshots/`, `generated_videos/`, `logs/`, `certs/` |
| 4. Configuration | Generates `.env` with **random secret keys** |
| 5. SSL Certificate | Generates a self-signed RSA 4096-bit certificate (365 days) |
| 6. Cloudflared | Downloads the tunnel binary (auto-detects CPU architecture) |
| 7. Database | Initializes SQLite database with default categories |

---

## Security Features

| Feature | Detail |
|---------|--------|
| **HTTPS / TLS** | RSA 4096-bit self-signed certificate |
| **Password Hashing** | PBKDF2-SHA256 (100,000 iterations) |
| **Login Lockout** | Locked for 15 minutes after 5 failed attempts |
| **Session Timeout** | Auto-expires after 60 minutes |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS, Referrer-Policy, Permissions-Policy |
| **Secret Key** | Auto-generated using `secrets.token_hex(32)` |
| **Firewall (recommended)** | `sudo ufw allow 22/tcp && sudo ufw allow 8443/tcp && sudo ufw enable` |

---

## Project Structure

```
├── src/                        # Core source code
│   ├── app.py                 # Flask web application (routes, security headers)
│   ├── auth.py                # Authentication & session management
│   ├── config.py              # Reads settings from .env
│   ├── database.py            # SQLite operations
│   ├── utils.py               # Utility functions
│   ├── video_generator.py     # Time-lapse video generation (OpenCV)
│   ├── logger.py              # Logging configuration
│   └── paths.py               # Path management
│
├── scripts/                    # Utility scripts
│   ├── batch_import.py        # Batch image import
│   ├── folder_watcher.py      # Automatic folder monitoring
│   ├── check_system.py        # System health check
│   └── examples.py            # API usage examples
│
├── templates/                  # Jinja2 HTML templates
├── static/                     # Static assets (images, CSS)
├── docs/                       # Documentation
│   ├── SETUP_DOCUMENTATION.md # Installation & security documentation
│   ├── INSTALLATION.md        # Detailed installation guide
│   ├── ONLINE_SETUP.md        # Cloudflared tunnel setup
│   ├── PROJECT_OVERVIEW.md    # Project overview
│   └── QUICKSTART.md          # Quick start guide
│
├── raspberry_pi_scripts/       # Raspberry Pi scripts
│   ├── upload_snapshot.py     # Upload images to server
│   └── upload_snapshot.sh     # Cron-ready bash script
│
├── snapshots/                  # Uploaded images (gitignored)
├── generated_videos/           # Generated videos (gitignored)
├── logs/                       # Log files (gitignored)
├── certs/                      # SSL cert & key (gitignored, auto-generated)
│
├── run.py                      # Entry point (supports SSL)
├── start.sh                    # One-click setup & run (Linux)
├── start.bat                   # Start script (Windows)
├── .env.example                # Example configuration
├── .gitignore                  # Excludes secrets, DB, certs from version control
└── requirements.txt            # Python dependencies (pinned versions)
```

---

## Prerequisites

- **OS:** Ubuntu 22.04+ / Debian 12+ / Raspberry Pi OS
- **Python:** 3.10+
- **Required packages (if not already installed):**
  ```bash
  sudo apt update
  sudo apt install -y python3 python3-pip python3-venv openssl
  ```

> `start.sh` will check for these and display a warning if anything is missing.

---

## API Upload (Raspberry Pi / Automation)

For automated uploads from Raspberry Pi or other devices, use the REST API:

```bash
curl -sk -X POST https://your-server:8443/api/upload \
  -F "file=@snapshot.jpg" \
  -F "api_key=rpi-cam1-secret-key-2024" \
  -F "camera_id=cam1" \
  -F "project_name=Aeroponic System 1"
```

See [raspberry_pi_scripts/README.md](raspberry_pi_scripts/README.md) for full API documentation and crontab examples.

---

## Documentation

- [Installation & Security Documentation](docs/SETUP_DOCUMENTATION.md)
- [Detailed Installation Guide](docs/INSTALLATION.md)
- [Quick Start Guide](docs/QUICKSTART.md)
- [Project Overview](docs/PROJECT_OVERVIEW.md)
- [Online Access (Cloudflare Tunnel)](docs/ONLINE_SETUP.md)
- [Raspberry Pi Setup](raspberry_pi_scripts/README.md)

---

## Utility Scripts

```bash
# Batch import images from a folder
python scripts/batch_import.py "/path/to/images" --source "Camera 1"

# Watch a folder and auto-import new images
python scripts/folder_watcher.py --watch "/path/to/watch" --category "Aeroponic System 1"

# Run system health check
python scripts/check_system.py
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Flask 3.1.2 (Python 3.12) |
| Database | SQLite |
| Video | OpenCV 4.13 |
| Security | HTTPS (TLS), PBKDF2-SHA256, Security Headers |
| Tunnel | Cloudflare Tunnel (cloudflared) |
| Deployment | Ubuntu 24.04 / Raspberry Pi OS |
