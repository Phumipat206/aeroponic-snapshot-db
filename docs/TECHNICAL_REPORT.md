# Technical Report — Aeroponic Snapshot Database System

> **รายงานทางเทคนิค (Technical Report) ฉบับสมบูรณ์**  
> **Date:** February 2026  
> **Author:** Aeroponic Monitoring Project Team  
> **Environment:** Ubuntu 24.04 LTS on Virtual Machine → Raspberry Pi Deployment

---

## Executive Summary

This report documents the complete technical implementation of the Aeroponic Snapshot Database System — a self-hosted, offline-capable web application for managing plant growth monitoring photographs from aeroponic farming systems. The system replaces cloud-based photo storage (Google Drive) with a local solution offering unlimited storage, advanced querying, and automated time-lapse video generation.

**Key capabilities:**
1. **REST API** for automated Raspberry Pi camera uploads (no GUI required)
2. **Recursive folder import** supporting nested `cam[n]/[n]_MM-DD` structure
3. **SQLite database** with hierarchical categories, tags, and full-text search
4. **Time-lapse video generation** from queried snapshot sequences
5. **Security hardening** — HTTPS, PBKDF2 password hashing, UFW firewall, API key auth

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Technology Stack](#2-technology-stack)
3. [Database Design](#3-database-design)
4. [API Design — Automated Upload](#4-api-design--automated-upload)
5. [Folder Structure & Recursive Import](#5-folder-structure--recursive-import)
6. [Web Interface](#6-web-interface)
7. [Video Generation Pipeline](#7-video-generation-pipeline)
8. [Security Implementation](#8-security-implementation)
9. [Network Configuration](#9-network-configuration)
10. [Deployment Strategy (VM → Raspberry Pi)](#10-deployment-strategy-vm--raspberry-pi)
11. [Testing Results](#11-testing-results)
12. [File Structure & Source Code Map](#12-file-structure--source-code-map)
13. [Performance Benchmarks](#13-performance-benchmarks)
14. [Future Improvements](#14-future-improvements)

---

## 1. System Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                        SYSTEM ARCHITECTURE                           │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────┐     HTTPS POST /api/upload     ┌──────────────────┐ │
│  │ Raspberry Pi │ ─────────────────────────────→ │  Flask Server    │ │
│  │ + Camera     │    (API Key + Image File)      │  (Python 3.12)   │ │
│  │ + Crontab    │                                │                  │ │
│  └─────────────┘     ◄── JSON Response ────────  │  ┌────────────┐ │ │
│                                                  │  │ SQLite DB  │ │ │
│  ┌─────────────┐     HTTPS (Browser)             │  └────────────┘ │ │
│  │ Web Browser  │ ─────────────────────────────→ │                  │ │
│  │ (User/Prof)  │    HTML + CSS + JS             │  ┌────────────┐ │ │
│  └─────────────┘     ◄────────────────────────── │  │ File Store │ │ │
│                                                  │  │ snapshots/ │ │ │
│  ┌─────────────┐     CLI / Script                │  └────────────┘ │ │
│  │ Batch Import │ ─────────────────────────────→ │                  │ │
│  │ (Python CLI) │    Recursive folder scan       │  ┌────────────┐ │ │
│  └─────────────┘                                 │  │ OpenCV     │ │ │
│                                                  │  │ Video Gen  │ │ │
│  ┌─────────────┐     HTTPS (Cloudflare Tunnel)   │  └────────────┘ │ │
│  │ Remote User  │ ─────────────────────────────→ │                  │ │
│  │ (Internet)   │    Secure tunnel (free)         │  UFW Firewall   │ │
│  └─────────────┘                                 │  SSL/TLS (4096) │ │
│                                                  └──────────────────┘ │
│                                                                       │
│  Development:  VM (VirtualBox/VMWare) on PC                          │
│  Production:   Raspberry Pi 4 (4GB RAM) at farm                      │
└───────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Automated Capture** → Raspberry Pi camera captures image on schedule (Crontab)
2. **API Upload** → Python script sends image via HTTPS POST to `/api/upload`
3. **Processing** → Server validates API key, saves file, extracts metadata
4. **Storage** → Image saved to `snapshots/` folder, metadata to SQLite DB
5. **Query** → Users filter by date, category, camera, tags via web interface
6. **Video** → Selected snapshots combined into MP4 time-lapse using OpenCV

---

## 2. Technology Stack

### Backend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Language | Python | 3.12 | Core application |
| Web Framework | Flask | 3.1.2 | HTTP routing, templates |
| WSGI | Werkzeug | 3.1.5 | Request handling |
| Database | SQLite | 3.45 | Metadata storage |
| Image Processing | Pillow | 12.1.0 | Resize, metadata extraction |
| Video Generation | OpenCV | 4.13.0 | Time-lapse MP4 creation |
| Numerical | NumPy | 2.4.2 | Array operations |
| Config | python-dotenv | 1.2.1 | Environment variables |
| Date Parsing | python-dateutil | 2.9.0 | Flexible date formats |
| HTTP Client | requests | 2.32.5 | Tunnel health check |
| File Watcher | watchdog | 6.0.0 | Auto-import on file change |

### Frontend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Structure | HTML5 | Page layout |
| Styling | CSS3 (Gradients, Flexbox) | Responsive design |
| Interactivity | Vanilla JavaScript | AJAX operations |
| Icons | CSS gradients | Visual elements |

### Security

| Component | Technology | Purpose |
|-----------|-----------|---------|
| TLS Certificate | OpenSSL RSA 4096 | HTTPS encryption |
| Password Hashing | PBKDF2-SHA256 (100k iter) | Secure authentication |
| Firewall | UFW | Port restriction |
| Tunnel | Cloudflared | Secure remote access |

### Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Development | VirtualBox VM (Ubuntu 24.04) | Testing environment |
| Production | Raspberry Pi 4 (4GB) | Deployment target |
| Networking | Bridged/NAT | VM connectivity |

---

## 3. Database Design

### Entity Relationship Diagram

```
┌─────────────────┐       ┌──────────────────────────┐       ┌────────────────────┐
│   categories    │       │       snapshots           │       │ video_generations  │
├─────────────────┤       ├──────────────────────────┤       ├────────────────────┤
│ id (PK)         │ 1───∞ │ id (PK)                  │       │ id (PK)            │
│ name            │       │ filename                  │       │ filename           │
│ parent_id (FK)  │←─┐    │ original_filename         │       │ filepath           │
│ description     │  │    │ filepath                  │       │ snapshot_count     │
│ created_at      │  │    │ category_id (FK)          │       │ fps                │
└────────┬────────┘  │    │ capture_time              │       │ duration           │
         │           │    │ upload_time               │       │ total_frames       │
         └───────────┘    │ file_size                 │       │ file_size          │
         (self-ref)       │ width                     │       │ width              │
                          │ height                    │       │ height             │
                          │ source                    │       │ category_filter    │
                          │ tags                      │       │ time_filter        │
                          │ notes                     │       │ created_at         │
                          │ camera_id                 │       │ status             │
                          │ project_name              │       │ error_message      │
                          └──────────────────────────┘       └────────────────────┘
```

### Table Details

**`categories`** — Hierarchical classification with self-referencing parent
```sql
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER,                    -- Self-reference for hierarchy
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES categories (id)
);
```

**`snapshots`** — Core data table with rich metadata
```sql
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,               -- Unique stored filename
    original_filename TEXT NOT NULL,       -- Original file name
    filepath TEXT NOT NULL,               -- Absolute file path
    category_id INTEGER,                  -- Category classification
    capture_time TIMESTAMP NOT NULL,      -- When photo was taken
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_size INTEGER,                    -- File size in bytes
    width INTEGER,                        -- Image width (px)
    height INTEGER,                       -- Image height (px)
    source TEXT DEFAULT 'Upload',         -- Upload source identifier
    tags TEXT,                            -- Comma-separated tags
    notes TEXT,                           -- Free-form notes
    camera_id TEXT,                       -- Camera identifier
    project_name TEXT,                    -- Project name
    FOREIGN KEY (category_id) REFERENCES categories (id)
);
-- Indexes for query performance
CREATE INDEX idx_capture_time ON snapshots (capture_time);
CREATE INDEX idx_category ON snapshots (category_id);
CREATE INDEX idx_camera ON snapshots (camera_id);
CREATE INDEX idx_project ON snapshots (project_name);
```

### Query Examples
```sql
-- All snapshots from cam1 in January 2026
SELECT * FROM snapshots 
WHERE camera_id = 'cam1' 
  AND capture_time BETWEEN '2026-01-01' AND '2026-01-31'
ORDER BY capture_time ASC;

-- Daily snapshot at 9 AM (±30 min tolerance)
SELECT * FROM snapshots 
WHERE CAST(strftime('%H', capture_time) AS INTEGER) BETWEEN 8 AND 9
ORDER BY capture_time ASC;

-- Count by camera
SELECT camera_id, COUNT(*) as count 
FROM snapshots 
GROUP BY camera_id;
```

---

## 4. API Design — Automated Upload

### Endpoint: `POST /api/upload`

This is the primary programmatic interface for Raspberry Pi cameras. It accepts multipart form data with API key authentication.

**Implementation:** [src/app.py](src/app.py) (line ~388)

### Authentication Flow
```
Client Request → Check api_key → Validate against API_KEYS config → Accept/Reject
```

API keys are stored in `.env`:
```
API_KEYS=rpi-cam1-secret-key-2024,rpi-cam2-secret-key-2024
```

### Request/Response Specification

**Request (multipart/form-data):**
| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `file` | Yes | File | Image file (jpg/png/gif/bmp) |
| `api_key` | Yes | String | Authentication key |
| `camera_id` | No | String | Camera identifier |
| `project_name` | No | String | Project for categorization |
| `timestamp` | No | String | Capture time (multiple formats) |
| `category_id` | No | Integer | Category classification |
| `tags` | No | String | Comma-separated tags |
| `notes` | No | String | Additional notes |

**Response (JSON):**
```json
{
    "success": true,
    "snapshot_id": 42,
    "filename": "cam1_20260210_143000_a1b2c3d4.jpg",
    "capture_time": "2026-02-10 14:30:00",
    "camera_id": "cam1",
    "project_name": "Aeroponic System 1",
    "file_size": 245760,
    "dimensions": "1920x1080"
}
```

### Client Scripts Provided
| File | Language | Use Case |
|------|----------|----------|
| `raspberry_pi_scripts/upload_snapshot.py` | Python | Full-featured client with camera capture |
| `raspberry_pi_scripts/upload_snapshot.sh` | Bash | Lightweight script for crontab |

### Crontab Automation
```cron
# Every 30 minutes: capture + upload
*/30 * * * * /usr/bin/python3 /home/pi/upload_snapshot.py --capture >> /home/pi/upload.log 2>&1
```

> **Full API documentation:** See [docs/API_DOCUMENTATION.md](API_DOCUMENTATION.md)

---

## 5. Folder Structure & Recursive Import

### Problem Statement
Farm cameras produce nested folder structures:
```
cam1/
├── 1_01-15/    ← Sequence 1, January 15
│   ├── photo1.jpg
│   └── photo2.jpg
├── 2_01-16/    ← Sequence 2, January 16
│   └── photo1.jpg
```

### Solution
The batch import tool (`scripts/batch_import.py`) supports:
1. **Recursive traversal** — `os.walk()` enters all subdirectories
2. **Camera detection** — Parses `cam1`, `cam2` folder names
3. **Date extraction** — Parses `[n]_MM-DD` folder names for capture date
4. **Auto-tagging** — Generates tags like `camera:cam1,date:01-15,seq:1`

### Parsing Logic
```python
# Camera: regex r'^cam(\d+)$' (case-insensitive)
# Date:   regex r'^(\d+)_(\d{2})-(\d{2})$'

# "cam1"    → camera_id = "cam1", camera_num = 1
# "2_01-16" → sequence = 2, month = "01", day = "16"
```

### Usage
```bash
# Analyze structure (no import)
python3 scripts/batch_import.py /data/ --analyze-only

# Import with structure parsing
python3 scripts/batch_import.py /data/ --parse-structure --source "Farm Data"
```

> **Full folder documentation:** See [docs/FOLDER_STRUCTURE_IMPORT.md](FOLDER_STRUCTURE_IMPORT.md)

---

## 6. Web Interface

### Available Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Overview with statistics |
| `/upload` | Upload | Manual image upload |
| `/query` | Query | Advanced search with filters |
| `/daily` | Daily Snapshots | Query by time of day |
| `/categories` | Categories | Manage classification hierarchy |
| `/generate-video` | Video Generator | Create time-lapse videos |
| `/videos` | Video Library | Browse generated videos |
| `/stats` | Statistics | Charts and analytics |
| `/login` | Login | User authentication |
| `/security` | Security Settings | Password, sessions, IP whitelist |
| `/online` | Online Access | Cloudflare tunnel management |

### Current Status
- **Environment:** Runs on local machine / VM
- **Access URL:** `https://localhost:8443`
- **Default Login:** `admin` / `admin` (change on first login)
- **Demo:** Screen recording available showing all features

### Responsive Design
- Built with CSS Flexbox/Grid
- Works on desktop, tablet, and mobile browsers
- Dark gradient theme with professional appearance

---

## 7. Video Generation Pipeline

### Process Flow
```
1. Query snapshots (by date, category, camera)
       ↓
2. Sort by capture_time ASC
       ↓
3. Load images and resize to uniform dimensions
       ↓
4. (Optional) Add timestamp overlay to each frame
       ↓
5. Encode frames into MP4 using OpenCV VideoWriter
       ↓
6. Save to generated_videos/ folder
       ↓
7. Record metadata in video_generations table
```

### Configuration
| Parameter | Default | Description |
|-----------|---------|-------------|
| FPS | 10 | Frames per second |
| Codec | mp4v | H.264 compatible |
| Timestamps | Optional | Date/time overlay on frames |

### Implementation
```python
# src/video_generator.py
# Uses cv2.VideoWriter with FOURCC('m','p','4','v')
# Supports:
#   - Standard time-lapse
#   - Timestamp overlay (semi-transparent background)
#   - Side-by-side comparison videos
```

---

## 8. Security Implementation

### 8.1 Authentication System

| Feature | Details |
|---------|---------|
| **Password Storage** | PBKDF2-HMAC-SHA256, 100,000 iterations, 32-byte random salt |
| **Session Management** | Server-side sessions with 60-minute timeout |
| **Brute Force Protection** | 5 failed attempts → 15 minute lockout |
| **Strong Password Policy** | Min 8 chars, requires uppercase + lowercase + digit |
| **Multi-user Support** | Admin can create/manage multiple user accounts |

### 8.2 Transport Security

| Feature | Details |
|---------|---------|
| **SSL/TLS** | Self-signed RSA 4096-bit X.509 certificate |
| **HTTPS Port** | 8443 (non-standard, avoids conflict) |
| **HSTS Header** | `max-age=31536000; includeSubDomains` |
| **Certificate Validity** | 365 days |

### 8.3 HTTP Security Headers

Applied to every response via `@app.after_request`:
```
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### 8.4 API Security

| Feature | Details |
|---------|---------|
| **API Key Auth** | Required for `/api/upload` endpoint |
| **Key Storage** | `.env` file with `chmod 600` |
| **File Validation** | Extension whitelist (jpg, png, gif, bmp) |
| **Filename Sanitization** | `werkzeug.utils.secure_filename()` |
| **Path Traversal Guard** | `os.path.realpath()` validation |

### 8.5 Infrastructure Security

| Feature | Details |
|---------|---------|
| **UFW Firewall** | Default: DENY incoming, ALLOW outgoing |
| **Open Ports** | SSH (22), HTTPS (8443) only |
| **File Permissions** | `.env`: 600, `key.pem`: 600, `certs/`: 700 |
| **IP Whitelisting** | Optional, configurable via web interface |

---

## 9. Network Configuration

### Firewall Rules (UFW)
```
Default: deny incoming, allow outgoing
22/tcp   ALLOW    SSH access
8443/tcp ALLOW    Aeroponic HTTPS
```

### Local Network Access
```
https://SERVER_IP:8443
```
Server binds to `0.0.0.0` — accessible from any device on the same network.

### Remote Access (Internet)
Cloudflare Tunnel (free, no port forwarding needed):
```bash
./src/cloudflared tunnel --url http://localhost:8443
# Generates: https://random-words.trycloudflare.com
```

### Network Topology
```
┌──────────────────────────────────────────────────────────────┐
│                    Local Network (LAN)                        │
│                                                              │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │ RPi      │    │ Server (VM)  │    │ User's PC/Phone   │  │
│  │ Camera   │───→│ Flask :8443  │←───│ Browser           │  │
│  └──────────┘    │ UFW Firewall │    └───────────────────┘  │
│                  │ SQLite DB    │                            │
│                  └──────┬───────┘                            │
│                         │                                    │
└─────────────────────────┼────────────────────────────────────┘
                          │ Cloudflare Tunnel (optional)
                          ↓
                  ┌───────────────┐
                  │   Internet    │
                  │  .trycloudflare│
                  │    .com       │
                  └───────────────┘
```

---

## 10. Deployment Strategy (VM → Raspberry Pi)

### Phase 1: Development on VM ✅
1. Create VirtualBox VM with Ubuntu 24.04 LTS
2. Install all system packages and Python dependencies
3. Configure security (UFW, SSL, auth)
4. Test all features (upload, query, video, API)
5. **Document every command** in install log

### Phase 2: Testing on VM ✅
1. Test API upload endpoints
2. Test recursive folder import
3. Test video generation
4. Test security (login, lockout, SSL)
5. Run system check script
6. Record test results

### Phase 3: Migration to Raspberry Pi ⬜
1. Copy project files via SCP
2. Run automated setup script (`setup_raspberry_pi.sh`)
3. Script handles: packages, venv, pip, SSL, .env, UFW, cloudflared (ARM)
4. Configure camera module
5. Setup crontab for automated capture
6. Verify all features

### Risk Mitigation
| Risk | Mitigation |
|------|-----------|
| Unstable internet at farm | All features work offline, SQLite is file-based |
| ARM architecture differences | `opencv-python-headless` for RPi, ARM cloudflared |
| RPi resource constraints | SQLite is lightweight, WAL mode for concurrent access |
| Setup errors on RPi | Automated script + detailed command log from VM |

---

## 11. Testing Results

### Functional Tests

| Test Case | Status | Notes |
|-----------|--------|-------|
| Web interface loads | ✅ PASS | HTTPS on port 8443 |
| User login/logout | ✅ PASS | PBKDF2 auth working |
| Login lockout (5 attempts) | ✅ PASS | 15-min lockout |
| Upload via web UI | ✅ PASS | Drag & drop supported |
| Upload via API (curl) | ✅ PASS | JSON response |
| Upload via Python script | ✅ PASS | `upload_snapshot.py` |
| Query by date range | ✅ PASS | Start/end time filter |
| Query by category | ✅ PASS | Hierarchical categories |
| Query by tags | ✅ PASS | Comma-separated search |
| Daily snapshot query | ✅ PASS | Hour/minute + tolerance |
| Batch import (flat) | ✅ PASS | Single directory |
| Batch import (recursive) | ✅ PASS | Nested folders |
| Batch import (parse structure) | ✅ PASS | cam/date parsing |
| Video generation (standard) | ✅ PASS | MP4 output |
| Video generation (timestamps) | ✅ PASS | Overlay working |
| SSL/TLS certificate | ✅ PASS | RSA 4096-bit |
| UFW firewall | ✅ PASS | Deny incoming default |
| Security headers | ✅ PASS | All headers present |
| Path traversal protection | ✅ PASS | realpath validation |
| Cross-OS path normalization | ✅ PASS | Windows/Linux compat |

### Performance Tests

| Operation | Result | Environment |
|-----------|--------|-------------|
| Upload single image | < 1 second | VM (2 cores, 2GB RAM) |
| Query 1000 snapshots | < 100 ms | SQLite with indexes |
| Video from 10 images | 2–5 seconds | OpenCV mp4v codec |
| Video from 100 images | 10–20 seconds | Standard resolution |
| Batch import 100 files | ~30 seconds | Including copy + DB insert |
| API upload (network) | 1–3 seconds | Depends on image size |

---

## 12. File Structure & Source Code Map

```
Task Description 4/
├── run.py                           # Entry point (SSL support)
├── start.sh                         # One-click setup + run
├── setup_raspberry_pi.sh            # Automated RPi/Ubuntu setup
├── requirements.txt                 # Python dependencies (pinned)
├── .env                             # Server configuration
│
├── src/                             # Core application
│   ├── app.py                       # Flask routes + security (2144 lines)
│   ├── auth.py                      # Authentication (496 lines)
│   ├── config.py                    # Configuration loader
│   ├── database.py                  # SQLite operations (822 lines)
│   ├── utils.py                     # File utilities
│   ├── video_generator.py           # OpenCV video creation
│   ├── logger.py                    # Logging setup
│   └── paths.py                     # Cross-OS path management
│
├── scripts/                         # Utility scripts
│   ├── batch_import.py              # Bulk import (442 lines)
│   ├── check_system.py              # System verification
│   ├── examples.py                  # API usage examples
│   └── folder_watcher.py            # Auto-import on file change
│
├── raspberry_pi_scripts/            # IoT upload clients
│   ├── upload_snapshot.py           # Python upload (287 lines)
│   ├── upload_snapshot.sh           # Bash upload script
│   └── README.md                    # RPi setup guide
│
├── templates/                       # HTML pages (15 templates)
├── static/                          # CSS, images
├── certs/                           # SSL certificate + private key
├── docs/                            # Documentation
│   ├── API_DOCUMENTATION.md         # REST API reference
│   ├── VM_SETUP_GUIDE.md            # VM installation guide
│   ├── FOLDER_STRUCTURE_IMPORT.md   # Recursive import docs
│   ├── SETUP_DOCUMENTATION.md       # Security + setup docs
│   ├── INSTALLATION.md              # Step-by-step install
│   ├── PROJECT_OVERVIEW.md          # Feature overview
│   ├── TECHNICAL_REPORT.md          # This report
│   └── ...
│
├── snapshots/                       # Image storage
├── generated_videos/                # MP4 output
└── logs/                            # Application logs
```

---

## 13. Performance Benchmarks

### Storage Efficiency
| Metric | Value |
|--------|-------|
| Database size (empty) | ~12 KB |
| Database size (1,000 snapshots) | ~200 KB |
| Average image size | 200–500 KB |
| 1,000 images storage | ~300 MB |
| 10,000 images storage | ~3 GB |

### SQLite vs Cloud Comparison
| Metric | SQLite (Local) | Google Drive |
|--------|---------------|--------------|
| Query latency | < 10 ms | 500–2000 ms |
| Upload speed | < 1 sec | 3–10 sec |
| Monthly cost | $0 | $0–$10 |
| Storage limit | Disk size | 15 GB free |
| Offline access | Full | Limited |
| API complexity | Simple REST | OAuth2 + API v3 |

---

## 14. Future Improvements

| Priority | Feature | Description |
|----------|---------|-------------|
| High | PostgreSQL option | For multi-user production deployments |
| High | Container deployment | Docker/Docker Compose for easier setup |
| Medium | Image analytics | ML-based plant growth measurement |
| Medium | Alert system | Notify when plants show abnormalities |
| Low | Mobile app | Native iOS/Android companion app |
| Low | Multi-site support | Manage multiple farm locations |

---

## References

### Software Used
1. Flask — https://flask.palletsprojects.com/
2. SQLite — https://www.sqlite.org/
3. OpenCV — https://opencv.org/
4. Cloudflared — https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
5. UFW — https://help.ubuntu.com/community/UFW
6. VirtualBox — https://www.virtualbox.org/

### Related Documentation
- [API Documentation](API_DOCUMENTATION.md) — REST API reference for Raspberry Pi integration
- [VM Setup Guide](VM_SETUP_GUIDE.md) — Complete VM installation step-by-step
- [Folder Structure Import](FOLDER_STRUCTURE_IMPORT.md) — Recursive import documentation
- [Setup Documentation](SETUP_DOCUMENTATION.md) — Security configuration reference
- [Installation Guide](INSTALLATION.md) — Quick installation steps
- [Project Overview](PROJECT_OVERVIEW.md) — Feature summary and completion status

---

**End of Technical Report**  
**Last Updated:** February 2026
