# Raspberry Pi Upload Scripts

Scripts for uploading snapshots from Raspberry Pi to the Aeroponic Snapshot Database server.

## Prerequisites

- Raspberry Pi with camera module (optional, required only for `--capture`)
- Python 3 + `requests` library
- Network connectivity to the server

## Installation

### 1. Copy Files to Raspberry Pi

```bash
# Using scp
scp upload_snapshot.py pi@raspberrypi:/home/pi/
scp upload_snapshot.sh pi@raspberrypi:/home/pi/

# Or clone the entire repository
git clone <REPO_URL>
```

### 2. Install Dependencies (Python version)

```bash
pip3 install requests
```

### 3. Edit Configuration

Open `upload_snapshot.py` or `upload_snapshot.sh` and update:

```python
# Python version
SERVER_URL = "https://your-server:8443"        # Server IP or tunnel URL
API_KEY = "rpi-cam1-secret-key-2024"           # Must match .env on server
DEFAULT_CAMERA_ID = "cam1"                     # This camera's identifier
DEFAULT_PROJECT_NAME = "Aeroponic System 1"    # Project name
```

```bash
# Bash version
SERVER_URL="https://your-server:8443"
API_KEY="rpi-cam1-secret-key-2024"
CAMERA_ID="cam1"
PROJECT_NAME="Aeroponic System 1"
```

### 4. Configure API Keys on the Server

API keys are defined in the `.env` file on the server:

```env
API_KEYS=rpi-cam1-secret-key-2024,rpi-cam2-secret-key-2024,rpi-cam3-secret-key-2024
```

Each Raspberry Pi camera should use a unique key for identification.

## Usage

### Python Version

```bash
# Test server connectivity
python3 upload_snapshot.py --test

# Upload an existing image file
python3 upload_snapshot.py /path/to/image.jpg

# Upload with camera and project specified
python3 upload_snapshot.py /path/to/image.jpg --camera cam1 --project "Project A"

# Capture from camera and upload (requires picamera2)
python3 upload_snapshot.py --capture

# Specify a different server
python3 upload_snapshot.py /path/to/image.jpg --server https://other-server:8443
```

### Bash Version

```bash
# Grant execute permission
chmod +x upload_snapshot.sh

# Upload an existing file
./upload_snapshot.sh /path/to/image.jpg

# Capture from camera and upload
./upload_snapshot.sh
```

## Automated Scheduling with Crontab

```bash
# Open crontab editor
crontab -e
```

Add one of the following lines:

```bash
# Upload every 30 minutes
*/30 * * * * /usr/bin/python3 /home/pi/upload_snapshot.py --capture >> /home/pi/upload.log 2>&1

# Upload every hour
0 * * * * /home/pi/upload_snapshot.sh >> /home/pi/upload.log 2>&1

# Upload at 6 AM, 12 PM, and 6 PM only
0 6,12,18 * * * /usr/bin/python3 /home/pi/upload_snapshot.py --capture >> /home/pi/upload.log 2>&1

# Upload every 15 minutes between 6 AM and 6 PM
*/15 6-18 * * * /home/pi/upload_snapshot.sh >> /home/pi/upload.log 2>&1
```

## API Endpoint Reference

### POST /api/upload

Upload a snapshot image to the server.

**Headers:**
```
Content-Type: multipart/form-data
```

**Form Data:**

| Field | Required | Description |
|-------|----------|-------------|
| file | Yes | Image file (jpg, png, gif, bmp) |
| api_key | Yes | API key for authentication |
| camera_id | No | Camera identifier (e.g., cam1) |
| project_name | No | Project name for categorization |
| timestamp | No | Capture timestamp (YYYY-MM-DD_HH-MM-SS) |
| category_id | No | Category ID in database |
| tags | No | Comma-separated tags |
| notes | No | Additional notes |

**Successful Response (200):**
```json
{
    "success": true,
    "snapshot_id": 123,
    "filename": "cam1_20260210_083000_abc123.jpg",
    "capture_time": "2026-02-10 08:30:00",
    "camera_id": "cam1",
    "project_name": "Aeroponic System 1",
    "file_size": 1024000,
    "dimensions": "1920x1080"
}
```

**Error Response (401/400):**
```json
{
    "success": false,
    "error": "Invalid API key"
}
```

### GET /api/upload/test

Verify that the API endpoint is online and ready.

**Response:**
```json
{
    "success": true,
    "message": "API Upload endpoint is ready",
    "usage": { "..." },
    "example_curl": "curl -X POST ..."
}
```

## cURL Examples

```bash
# Basic upload
curl -sk -X POST https://server:8443/api/upload \
    -F "file=@snapshot.jpg" \
    -F "api_key=rpi-cam1-secret-key-2024"

# Upload with full metadata
curl -sk -X POST https://server:8443/api/upload \
    -F "file=@snapshot.jpg" \
    -F "api_key=rpi-cam1-secret-key-2024" \
    -F "camera_id=cam1" \
    -F "project_name=Aeroponic System 1" \
    -F "timestamp=2026-02-10_08-30-00" \
    -F "tags=morning,sunny"

# Use header instead of form field for API key
curl -sk -X POST https://server:8443/api/upload \
    -H "X-API-Key: rpi-cam1-secret-key-2024" \
    -F "file=@snapshot.jpg" \
    -F "camera_id=cam1"
```

> **Note:** The `-sk` flags are required: `-s` (silent mode) and `-k` (skip SSL certificate verification for self-signed certificates).

## Troubleshooting

### "Cannot connect to server"
- Verify `SERVER_URL` is correct (IP address + port)
- Ensure the server is running (`bash start.sh`)
- Check firewall: port 8443 must be open on the server
- Test with: `curl -sk https://server:8443/api/upload/test`

### "Invalid API key"
- Verify `API_KEY` matches one of the keys in the server's `.env` file (`API_KEYS=...`)

### "File not found"
- Check the image file path exists and is readable

### Camera capture failed
- Ensure the camera module is properly connected
- Test with: `libcamera-still -o test.jpg` (Pi 4/5) or `raspistill -o test.jpg` (older Pi)
- Install picamera2: `pip3 install picamera2`

## Log Files

```bash
# Watch logs in real-time
tail -f /home/pi/upload.log

# View last 50 lines
tail -50 /home/pi/upload.log
```
