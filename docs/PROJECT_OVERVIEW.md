# Project Overview — Aeroponic Snapshot Database

## Project Completion Status

All three phases have been successfully implemented with additional bonus features.

---

## Phase 1: Snapshot Database (COMPLETED)

### Requirements Met
- **Free Storage Solution** — Local file-based storage with unlimited capacity
- **Hierarchical Classification** — Category system with parent-child relationships
- **Multiple Source Integration** — Import tool supports merging multiple data sources
- **Organized Structure** — Database schema with categories, snapshots, and metadata

### Key Features
1. **SQLite Database** — Lightweight, serverless, zero-configuration
2. **Category System** — Hierarchical organization (Root System, Leaf System, etc.)
3. **Metadata Storage** — Capture time, file size, dimensions, tags, notes
4. **Auto-detection** — Extracts datetime from filenames automatically
5. **Batch Import** — Command-line tool for bulk importing
6. **API Upload** — RESTful endpoint for Raspberry Pi camera integration

### Technical Implementation
- `src/database.py` — Database schema and operations
- `src/config.py` — Storage paths and settings (reads `.env`)
- `src/utils.py` — File handling utilities
- SQLite database with indexed queries for performance

---

## Phase 2: Query Interface (COMPLETED)

### Requirements Met
- **Web-based Interface** — Full-featured HTML/CSS/JavaScript frontend
- **Time-based Filtering** — Query by date/time ranges
- **Daily Time Queries** — Find snapshots at consistent daily times
- **Conditional Filtering** — Category, tags, date range, source

### Key Features
1. **Advanced Query Page**
   - Filter by category
   - Date/time range selection
   - Tag search
   - Result limiting

2. **Daily Snapshots Page**
   - Query by specific hour/minute
   - Tolerance setting (± minutes)
   - Perfect for tracking daily growth patterns

3. **REST API Endpoints**
   - `/api/snapshots` — Programmatic access
   - `/api/categories` — Category management
   - `/api/upload` — API upload for Raspberry Pi
   - JSON responses for integration

4. **Visual Results**
   - Grid layout with thumbnails
   - Detailed snapshot information
   - Click to view full details

### Technical Implementation
- `src/app.py` — Flask web application with routes and security
- `templates/` — Responsive HTML templates
- RESTful API design
- SQL queries with multiple filters

---

## Phase 3: Video Generation (COMPLETED)

### Requirements Met
- **Automatic Time-lapse** — Combines selected snapshots into videos
- **Query Integration** — Generate videos from query results
- **Advanced Features** — Timestamps, FPS control, comparison videos

### Key Features
1. **Standard Time-lapse**
   - Combine snapshots into MP4 video
   - Adjustable frame rate (FPS)
   - Universal format compatibility

2. **Timestamp Overlay**
   - Optional date/time display on frames
   - Semi-transparent background
   - Customizable appearance

3. **Comparison Videos**
   - Side-by-side view of multiple sequences
   - Compare different plant parts
   - Synchronized playback

4. **Web Interface**
   - Easy-to-use video generation form
   - Preview settings before generation
   - Download completed videos

### Technical Implementation
- `src/video_generator.py` — Video creation logic
- OpenCV (cv2) for video processing
- MP4 encoding with H.264 codec
- Multiple video generation modes

---

## Bonus Features (Beyond Requirements)

### 1. Security & Authentication
- HTTPS with RSA 4096-bit self-signed certificate
- PBKDF2-SHA256 password hashing (100,000 iterations)
- Login lockout protection (5 failed attempts → 15-minute lock)
- Session timeout (60 minutes)
- Security headers (HSTS, X-Frame-Options, CSP, etc.)
- UFW firewall pre-configured

### 2. Statistics Dashboard
- Total snapshots count
- Storage usage tracking
- Timeline visualization
- Category breakdowns
- Monthly activity reports

### 3. Batch Operations
- `scripts/batch_import.py` — Command-line bulk import
- Recursive directory scanning
- Progress reporting
- Error handling and logging

### 4. API Upload (IoT Integration)
- REST API for Raspberry Pi cameras
- API key authentication
- Auto-categorization by project and camera
- Automated scheduling via cron

### 5. Online Access
- Cloudflare Tunnel integration (free, no port forwarding)
- Optional ngrok support
- Secure remote access to snapshot database

### 6. Advanced Utilities
- `scripts/examples.py` — API usage examples
- `scripts/check_system.py` — System verification tool
- `scripts/folder_watcher.py` — Auto-import on file change
- `start.sh` — One-click setup and run
- Comprehensive documentation

### 7. Professional Web Interface
- Responsive design (mobile-friendly)
- Modern gradient UI
- Intuitive navigation
- Flash messages for user feedback

---

## Complete File Structure

```
project/
├── src/                          # Core application
│   ├── app.py                   # Flask web app (routes, security)
│   ├── auth.py                  # Authentication & session management
│   ├── config.py                # Configuration (reads .env)
│   ├── database.py              # Database operations & schema
│   ├── utils.py                 # Utility functions
│   ├── video_generator.py       # Video creation logic
│   ├── logger.py                # Logging configuration
│   └── paths.py                 # Path management
│
├── scripts/                      # Utility scripts
│   ├── batch_import.py          # Bulk import tool
│   ├── examples.py              # API usage examples
│   ├── check_system.py          # System verification
│   └── folder_watcher.py        # Auto-import watcher
│
├── raspberry_pi_scripts/         # IoT upload scripts
│   ├── upload_snapshot.py       # Python upload script
│   ├── upload_snapshot.sh       # Bash upload script
│   └── README.md                # RPi setup guide
│
├── docs/                         # Documentation
│   ├── README.md                # Comprehensive docs
│   ├── QUICKSTART.md            # Quick start guide
│   ├── INSTALLATION.md          # Detailed install guide
│   ├── PROJECT_OVERVIEW.md      # This file
│   ├── ONLINE_SETUP.md          # Cloudflare Tunnel setup
│   ├── ONLINE_ACCESS_FIX.md     # Online access troubleshooting
│   └── SETUP_DOCUMENTATION.md   # Full setup documentation
│
├── templates/                    # HTML templates
│   ├── base.html                # Base template with navigation
│   ├── index.html               # Dashboard
│   ├── upload.html              # Upload interface
│   ├── query.html               # Query interface
│   ├── daily_snapshots.html     # Daily snapshot queries
│   ├── generate_video.html      # Video generation
│   ├── categories.html          # Category management
│   ├── stats.html               # Statistics page
│   ├── login.html               # Login page
│   ├── security_settings.html   # Security settings
│   └── ...                      # Additional templates
│
├── static/                       # Static assets
├── run.py                        # Entry point (SSL support)
├── start.sh                      # One-click setup & run (Linux)
├── .env.example                  # Example configuration
├── .gitignore                    # Git exclusion rules
└── requirements.txt              # Python dependencies (pinned)
```

---

## Technology Stack

### Backend
- **Python 3.12** — Core language
- **Flask 3.1** — Web framework
- **SQLite** — Database engine
- **OpenCV 4.13** — Video processing
- **Werkzeug 3.1** — WSGI utilities & password hashing

### Frontend
- **HTML5** — Structure
- **CSS3** — Styling (gradients, flexbox, grid)
- **JavaScript** — Interactivity
- **AJAX** — Asynchronous operations

### Security
- **SSL/TLS** — Self-signed RSA 4096-bit certificate
- **PBKDF2-SHA256** — Password hashing
- **UFW** — Firewall management
- **Cloudflared** — Secure tunnel for online access

### Libraries
- **python-dotenv** — Environment variable management
- **python-dateutil** — Date parsing
- **NumPy** — Array operations for video
- **Pillow** — Image processing

---

## How to Use

### Installation & Start
```bash
bash start.sh
```

This single command handles: virtual environment, dependencies, SSL certificate, database initialization, and starts the HTTPS server.

### Access Web Interface
Open browser: **https://localhost:8443**

Default login: `admin` / `admin`

### Import Snapshots

**Web Interface:**
1. Click "Upload"
2. Select images and category
3. Upload

**Command Line (Batch):**
```bash
source .venv/bin/activate
python scripts/batch_import.py "/path/to/folder" --source "Source Name"
```

**API Upload (Raspberry Pi):**
```bash
curl -sk -X POST https://server:8443/api/upload \
    -F "file=@snapshot.jpg" \
    -F "api_key=YOUR_API_KEY" \
    -F "camera_id=cam1" \
    -F "project_name=Aeroponic System 1"
```

### Generate Time-lapse
1. Click "Generate Video"
2. Set parameters (category, date range, FPS)
3. Click generate
4. Download video

---

## Advantages Over Google Drive

| Feature | Google Drive | This System |
|---------|-------------|-------------|
| **Storage Limit** | 15 GB free | Unlimited |
| **Monthly Cost** | $2–10 for more | $0 Forever |
| **Query Capabilities** | Basic search | Advanced SQL |
| **Time-based Queries** | No | Yes |
| **Video Generation** | No | Yes |
| **Offline Access** | Limited | Full |
| **Speed** | Internet-dependent | Local |
| **Organization** | Folders only | Categories + Tags |
| **API Access** | Complex OAuth | Simple REST |
| **Data Ownership** | Cloud-based | 100% Local |
| **Security** | Third-party | Self-hosted |

---

## Usage Scenarios

### Scenario 1: Daily Growth Tracking
1. Take photos at 9 AM daily (manual or automated via RPi)
2. Upload to category "Root System"
3. Use "Daily Snapshots" to view the 9 AM series
4. Generate time-lapse video showing daily progression

### Scenario 2: Multi-Source Consolidation
1. Import from folder 1: `python scripts/batch_import.py "/data/source1" --source "Source 1"`
2. Import from folder 2: `python scripts/batch_import.py "/data/source2" --source "Source 2"`
3. All snapshots unified in a single database
4. Query across all sources simultaneously

### Scenario 3: Research Documentation
1. Organize by categories (Root, Leaf, Environment)
2. Tag experiments (treatment1, control, week1, etc.)
3. Query by tag + date range
4. Export results as video for presentations

### Scenario 4: Automated Monitoring
1. Set up Raspberry Pi with camera
2. Configure `upload_snapshot.py` with server URL and API key
3. Schedule via cron (e.g., every 30 minutes)
4. Snapshots automatically stored, organized, and queryable

---

## Data Security & Backup

### Security Features
- **HTTPS encryption** — All traffic encrypted with TLS
- **Authentication** — Login required with password hashing
- **Brute-force protection** — Account lockout after failed attempts
- **Firewall** — UFW configured to allow only necessary ports
- **No cloud dependency** — Works completely offline

### Backup Strategy
```bash
# Full backup
cp aeroponic_snapshots.db aeroponic_snapshots.db.bak
cp -r snapshots/ snapshots_backup/
cp -r generated_videos/ videos_backup/
```

### Restoration
1. Copy backed-up files to project folder
2. Run `bash start.sh`
3. All data restored instantly

---

## Meeting All Requirements

### Phase 1 Requirements
- [x] Free snapshot database
- [x] Based on existing hierarchical classification
- [x] Integrates multiple data sources
- [x] Unified snapshot database

### Phase 2 Requirements
- [x] Query and retrieve snapshots
- [x] Time-based filtering
- [x] Time range queries
- [x] Daily snapshot listing (same time each day)

### Phase 3 Requirements
- [x] Advanced application (time-lapse)
- [x] Automatic video combination
- [x] Similar to time-lapse recording

### Additional Deliverables
- [x] Complete implementation beyond basic requirements
- [x] Security features (HTTPS, authentication, firewall)
- [x] API for IoT integration (Raspberry Pi)
- [x] Online access via Cloudflare Tunnel
- [x] Comprehensive English documentation
- [x] One-click setup via `start.sh`

---

## Summary

This project delivers a **complete, production-ready snapshot management system** that:

1. **Solves the storage problem** — Unlimited free local storage
2. **Exceeds query requirements** — Advanced filtering with multiple criteria
3. **Automates video creation** — Professional time-lapse generation
4. **Provides ease of use** — Intuitive web interface with one-click setup
5. **Ensures security** — HTTPS, authentication, firewall, and security headers
6. **Supports IoT** — REST API for automated Raspberry Pi camera uploads
7. **Enables remote access** — Cloudflare Tunnel for online access

The system is **ready for immediate deployment** and long-term use in aeroponic research.

---

**Status: PROJECT COMPLETE**

All phases implemented, tested, and documented.

Last Updated: February 2026
