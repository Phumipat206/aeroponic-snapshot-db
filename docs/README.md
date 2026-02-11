# Aeroponic Snapshot Database System

A comprehensive, **free, and unlimited** snapshot management system for aeroponic monitoring with advanced querying and time-lapse video generation.

## Features

### Phase 1: Storage System
- **Unlimited Free Storage** — Local file-based storage with no limits
- **Hierarchical Organization** — Category-based classification system
- **Multi-source Import** — Import from multiple folders and sources
- **Automatic Organization** — Smart filename parsing and metadata extraction

### Phase 2: Query Interface
- **Time-based Filtering** — Query by date/time ranges
- **Category Filtering** — Search within specific categories
- **Daily Snapshot Tracking** — Find snapshots at the same time each day
- **Tag-based Search** — Organize and search by tags
- **Web Interface** — User-friendly browser-based interface
- **REST API** — Programmatic access to snapshot data

### Phase 3: Video Generation
- **Time-lapse Creation** — Automatic video generation from snapshots
- **Customizable FPS** — Control playback speed
- **Timestamp Overlay** — Optional date/time stamps on frames
- **Multiple Formats** — MP4 output for universal compatibility

### Security Features
- **HTTPS / TLS** — RSA 4096-bit self-signed certificate
- **Password Hashing** — PBKDF2-SHA256 (100,000 iterations)
- **Login Lockout** — 15-minute lock after 5 failed attempts
- **Session Timeout** — Auto-expiration after 60 minutes
- **Security Headers** — HSTS, X-Frame-Options, X-XSS-Protection, etc.
- **Firewall Ready** — UFW configuration included

### Bonus Features
- **Statistics Dashboard** — Comprehensive analytics
- **Batch Import** — Command-line bulk import tool
- **Auto-detection** — Capture time extraction from filenames
- **API Upload** — RESTful API for Raspberry Pi camera integration
- **Cloudflare Tunnel** — Online access without port forwarding
- **Responsive Design** — Works on desktop, tablet, and mobile

## Documentation Index

| Document | Description |
|----------|-------------|
| [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) | **รายงานทางเทคนิคฉบับสมบูรณ์** — Architecture, design, security, testing |
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | **REST API Reference** — Raspberry Pi automated upload |
| [VM_SETUP_GUIDE.md](VM_SETUP_GUIDE.md) | **VM Installation Guide** — VirtualBox → Ubuntu → Full setup |
| [FOLDER_STRUCTURE_IMPORT.md](FOLDER_STRUCTURE_IMPORT.md) | **Recursive Import** — cam[n]/[n]_MM-DD folder parsing |
| [SETUP_DOCUMENTATION.md](SETUP_DOCUMENTATION.md) | **Security & Setup** — UFW, SSL, password config |
| [INSTALLATION.md](INSTALLATION.md) | **Step-by-Step Install** — Manual installation guide |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | **Project Overview** — Feature summary |
| [ONLINE_SETUP.md](ONLINE_SETUP.md) | **Online Access** — Cloudflare Tunnel setup |

## Requirements

- Ubuntu 22.04+ / Debian 12+ / Raspberry Pi OS
- Python 3.10+

## Installation

```bash
bash start.sh
```

This single command handles everything: virtual environment, dependencies, SSL certificate, database initialization, and starts the server. See [INSTALLATION.md](INSTALLATION.md) for manual steps.

## Usage Guide

### 1. Upload Snapshots

**Web Interface:**
1. Navigate to "Upload" page
2. Select image file
3. Choose category (optional)
4. Add capture time (auto-detected from filename if not provided)
5. Click "Upload Snapshot"

**Batch Import:**
```bash
source .venv/bin/activate
python scripts/batch_import.py "/path/to/images" --source "Camera 1"
```

**API Upload (from Raspberry Pi):**
```bash
curl -sk -X POST https://server:8443/api/upload \
    -F "file=@snapshot.jpg" \
    -F "api_key=rpi-cam1-secret-key-2024" \
    -F "camera_id=cam1" \
    -F "project_name=Aeroponic System 1"
```

### 2. Query Snapshots

**Time-based Query:**
1. Go to "Query" page
2. Select category (optional)
3. Set start and end time
4. Add tag filter (optional)
5. Click "Search Snapshots"

**Daily Snapshots:**
1. Go to "Daily Snapshots" page
2. Enter hour (0–23) and minute
3. Set tolerance (± minutes)
4. Click "Find Daily Snapshots"
5. View snapshots taken at similar times each day

### 3. Generate Time-lapse Videos

1. Navigate to "Generate Video" page
2. Enter video name
3. Select category and time range
4. Choose FPS (10–15 recommended)
5. Enable/disable timestamp overlay
6. Click "Generate Video"
7. Download the generated MP4 file

### 4. Manage Categories

1. Go to "Categories" page
2. View existing category hierarchy
3. Add new categories with parent-child relationships

## Project Structure

```
project/
├── src/                        # Core source code
│   ├── app.py                 # Flask application (routes, security)
│   ├── auth.py                # Authentication & session management
│   ├── config.py              # Configuration (reads .env)
│   ├── database.py            # SQLite operations
│   ├── utils.py               # Utility functions
│   ├── video_generator.py     # Time-lapse video generation
│   ├── logger.py              # Logging configuration
│   └── paths.py               # Path management
│
├── scripts/                    # Utility scripts
│   ├── batch_import.py        # Bulk import tool
│   ├── folder_watcher.py      # Auto-import on file change
│   ├── check_system.py        # System health check
│   └── examples.py            # API usage examples
│
├── templates/                  # HTML templates
├── static/                     # Static assets
├── docs/                       # Documentation
├── raspberry_pi_scripts/       # Raspberry Pi upload scripts
│
├── run.py                      # Entry point (supports SSL)
├── start.sh                    # One-click setup & run
├── .env.example                # Example configuration
├── .gitignore                  # Git exclusion rules
└── requirements.txt            # Python dependencies (pinned)
```

## Configuration

Edit `.env` to customize (auto-generated by `start.sh`):

- **PORT**: Server port (default: 8443)
- **USE_SSL**: Enable HTTPS (default: true)
- **SECRET_KEY**: Session encryption key (random)
- **API_KEYS**: Comma-separated API keys for Raspberry Pi
- **SESSION_TIMEOUT**: Minutes before session expires
- **MAX_LOGIN_ATTEMPTS**: Failed attempts before lockout
- **LOCKOUT_DURATION**: Minutes of lockout after max attempts

## Database Schema

### Tables

**categories**
- id, name, parent_id, description, created_at
- Hierarchical structure for snapshot organization

**snapshots**
- id, filename, original_filename, filepath
- category_id, capture_time, upload_time
- file_size, width, height, source, tags, notes

**video_generations**
- id, video_filename, video_path
- snapshot_count, start_time, end_time
- fps, created_at, query_params

## API Endpoints

### Query Snapshots
```
GET /api/snapshots?category_id=1&start_time=2026-01-01&end_time=2026-01-31&limit=100
```

### Upload Snapshot (API)
```
POST /api/upload
Form Data: file, api_key, camera_id, project_name, timestamp, tags, notes
```

### Test API
```
GET /api/upload/test
```

### Manage Categories
```
GET /api/categories
POST /api/categories  (body: {name, parent_id, description})
```

## Tips and Best Practices

### Organizing Snapshots
1. **Use Categories**: Create logical hierarchies (Root System, Leaf System, Environment)
2. **Consistent Naming**: Include dates in filenames for auto-detection
3. **Add Tags**: Tag snapshots for easy searching

### Time-lapse Videos
- 5–8 FPS: Slow, detailed observation
- 10–15 FPS: Standard, balanced viewing
- 20–30 FPS: Fast, long-period overview
- Best results with consistent lighting and camera angles

### Filename Convention
Use dates in filenames for automatic timestamp extraction:
- `20260210_143000_root.jpg` — detected as 2026-02-10 14:30:00
- `2026-02-10_14-30-00.jpg` — detected as 2026-02-10 14:30:00
- `IMG_1234.jpg` — falls back to file modification time

## Comparison with Google Drive

| Feature | Google Drive | This System |
|---------|-------------|-------------|
| Storage Limit | 15 GB free | **Unlimited** |
| Cost | Paid beyond 15 GB | **100% Free** |
| Search | Basic | **Advanced (time, category, tags)** |
| Video Generation | No | **Yes (time-lapse)** |
| Offline Access | Limited | **Full offline** |
| API Upload | Complex OAuth | **Simple REST API** |
| Organization | Folders only | **Categories + tags** |

## Troubleshooting

### Database Issues
```bash
# Reinitialize database
source .venv/bin/activate
python3 -c "from src.database import init_database; init_database()"
```

### Video Generation Fails
- Ensure opencv-python is installed
- Check that snapshot files exist
- Verify sufficient disk space

### Cannot Access Web Interface
- Check terminal output for errors
- Try https://127.0.0.1:8443
- Accept the self-signed certificate warning (Advanced → Proceed)

## Data Backup

```bash
# Backup everything
cp aeroponic_snapshots.db aeroponic_snapshots.db.bak
cp -r snapshots/ snapshots_backup/
cp -r generated_videos/ videos_backup/
```

All data is fully contained in the project folder.

---

**Built for Aeroponic Research | Last Updated: February 2026**
