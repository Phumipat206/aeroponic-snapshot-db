# Quick Start Guide

## Get Started in 1 Step

```bash
bash start.sh
```

That's it! The script handles everything automatically. When it finishes, open your browser at **https://localhost:8443**.

> **Default login:** `admin` / `admin`

---

## What `start.sh` Does

1. Checks Python 3 is installed
2. Creates a virtual environment (`.venv`)
3. Installs all Python dependencies
4. Creates required directories
5. Generates `.env` with random secure keys
6. Generates a self-signed SSL certificate
7. Downloads cloudflared tunnel binary
8. Initializes the SQLite database
9. Starts the Flask server on HTTPS port 8443

---

## First Steps After Installation

### 1. Upload Your First Snapshot
- Click **Upload** in the navigation bar
- Select an image file
- Add capture time (or let it auto-detect from filename)
- Click **Upload Snapshot**

### 2. Import Existing Snapshots

**Method 1: Web Interface**
1. Click **Import** in navigation
2. Enter the folder path (e.g., `/home/user/photos/aeroponic`)
3. Click **Start Import**
4. Wait for completion

**Method 2: Command Line (faster for large collections)**
```bash
source .venv/bin/activate
python scripts/batch_import.py "/path/to/images" --source "Camera 1"
```

### 3. Query Your Snapshots
- Click **Query** in navigation
- Set date range (optional)
- Select category (optional)
- Click **Search Snapshots**

### 4. Create Your First Time-lapse Video
- Click **Generate Video**
- Select time range or category
- Set FPS (recommended: 10–15)
- Click **Generate Video**
- Download the result

---

## Common Use Cases

### Track Daily Growth at 9 AM
1. Go to **Daily Snapshots**
2. Enter: Hour=9, Minute=0, Tolerance=10
3. Click **Find Daily Snapshots**
4. View all snapshots taken around 9 AM each day

### Create Weekly Time-lapse
1. Go to **Generate Video**
2. Set start date: 7 days ago
3. Set end date: today
4. FPS: 10
5. Enable "Show timestamp"
6. Generate!

### Organize by Categories
1. Go to **Categories**
2. Add categories (e.g., Root Development, Leaf Growth, Environment)
3. Upload snapshots and assign categories
4. Query by category later

---

## File Structure After First Run

```
project/
├── aeroponic_snapshots.db    # SQLite database
├── auth.json                 # User accounts & sessions
├── .env                      # Configuration (auto-generated)
├── certs/                    # SSL certificate & key (auto-generated)
├── snapshots/                # Uploaded snapshot images
│   ├── category_1/
│   └── *.jpg/png
├── generated_videos/         # Time-lapse videos
│   └── *.mp4
└── logs/                     # Application logs
```

---

## Troubleshooting

### "Python not found"
```bash
sudo apt install -y python3 python3-pip python3-venv
```

### Cannot access web interface
- Check the terminal output for errors
- Try **https://127.0.0.1:8443** instead of localhost
- The browser will warn about a self-signed cert — click **Advanced → Proceed**

### Video generation fails
- Ensure opencv-python is installed: `pip install opencv-python`
- Check that snapshot files exist and are readable
- Try with fewer snapshots first (10–20)

---

## Filename Convention for Auto-Detection

Use dates in filenames for automatic timestamp extraction:
- `20260210_143000_root.jpg` — detected as 2026-02-10 14:30:00
- `2026-02-10_14-30-00.jpg` — detected as 2026-02-10 14:30:00
- `IMG_1234.jpg` — falls back to file modification time
