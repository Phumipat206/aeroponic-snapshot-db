# API Documentation — Raspberry Pi Automatic Upload

> **ตอบข้อสงสัยอาจารย์ (Fig.2):** ระบบมี REST API Endpoint ให้ Raspberry Pi ส่งภาพเข้ามาอัตโนมัติโดยไม่ต้องใช้คนกดผ่านหน้าเว็บ (GUI)  
> **Date:** February 2026

---

## 1. API Endpoint Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload snapshot image (main endpoint) |
| `GET` | `/api/upload/test` | Test server connectivity |
| `GET` | `/api/snapshots` | Query snapshots programmatically |
| `GET` | `/api/categories` | List all categories |

---

## 2. Upload API — `POST /api/upload`

### Authentication
Every request must include an **API Key** via:
- Form field: `api_key`
- OR HTTP header: `X-API-Key`

API keys are configured in the server's `.env` file:
```
API_KEYS=rpi-cam1-secret-key-2024,rpi-cam2-secret-key-2024,rpi-cam3-secret-key-2024
```

### Request Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | **Yes** | Image file (jpg, png, gif, bmp) |
| `api_key` | String | **Yes** | API key for authentication |
| `camera_id` | String | No | Camera identifier (e.g., `cam1`, `cam2`) |
| `project_name` | String | No | Project name for categorization |
| `timestamp` | String | No | Capture time (`YYYY-MM-DD_HH-MM-SS`) |
| `category_id` | Integer | No | Category ID for classification |
| `tags` | String | No | Comma-separated tags |
| `notes` | String | No | Additional notes |

### Timestamp Formats Accepted
- `YYYY-MM-DD_HH-MM-SS` (e.g., `2026-02-10_14-30-00`)
- `YYYYMMDD_HHMMSS` (e.g., `20260210_143000`)
- `YYYY-MM-DD HH:MM:SS` (e.g., `2026-02-10 14:30:00`)
- If omitted: auto-detected from filename, or defaults to current time

### Success Response (HTTP 200)
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

### Error Responses
| HTTP Code | Error | Cause |
|-----------|-------|-------|
| 401 | `API key required` | No API key provided |
| 401 | `Invalid API key` | API key not in server config |
| 400 | `No file provided` | Missing `file` field |
| 400 | `Invalid file type` | File extension not in allowed list |
| 500 | `Upload failed` | Server error during processing |

---

## 3. Usage Examples

### 3.1 cURL Command (simplest)
```bash
curl -sk -X POST https://SERVER_IP:8443/api/upload \
    -F "file=@/home/pi/snapshot.jpg" \
    -F "api_key=rpi-cam1-secret-key-2024" \
    -F "camera_id=cam1" \
    -F "project_name=Aeroponic System 1" \
    -F "timestamp=2026-02-10_14-30-00"
```

### 3.2 Python Script (Raspberry Pi)
```python
#!/usr/bin/env python3
"""Minimal example: Upload snapshot from Raspberry Pi to server"""
import requests
from datetime import datetime

SERVER_URL = "https://192.168.1.100:8443"  # ← Change to server IP
API_KEY = "rpi-cam1-secret-key-2024"       # ← Change to your API key

def upload(image_path, camera_id="cam1"):
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    
    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{SERVER_URL}/api/upload",
            files={'file': f},
            data={
                'api_key': API_KEY,
                'camera_id': camera_id,
                'project_name': 'Aeroponic System 1',
                'timestamp': timestamp,
            },
            verify=False,  # Self-signed cert
            timeout=60,
        )
    
    result = response.json()
    if result['success']:
        print(f"✅ Uploaded: ID={result['snapshot_id']}")
    else:
        print(f"❌ Failed: {result['error']}")
    return result

if __name__ == '__main__':
    upload('/home/pi/snapshot.jpg')
```

### 3.3 Capture + Upload (Raspberry Pi Camera)
```python
#!/usr/bin/env python3
"""Capture from Raspberry Pi camera module and upload automatically"""
import os
import requests
from datetime import datetime

SERVER_URL = "https://192.168.1.100:8443"
API_KEY = "rpi-cam1-secret-key-2024"

def capture_and_upload():
    timestamp = datetime.now()
    filename = f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
    filepath = f"/tmp/{filename}"
    
    # Capture image using libcamera (Raspberry Pi 4/5)
    os.system(f"libcamera-still -o {filepath} --width 1920 --height 1080 -t 1000 --nopreview")
    
    if not os.path.exists(filepath):
        print("❌ Capture failed")
        return
    
    # Upload
    with open(filepath, 'rb') as f:
        response = requests.post(
            f"{SERVER_URL}/api/upload",
            files={'file': (filename, f, 'image/jpeg')},
            data={
                'api_key': API_KEY,
                'camera_id': 'cam1',
                'project_name': 'Aeroponic System 1',
                'timestamp': timestamp.strftime('%Y-%m-%d_%H-%M-%S'),
            },
            verify=False,
            timeout=60,
        )
    
    result = response.json()
    print(f"[{timestamp}] {'✅' if result['success'] else '❌'} {result}")
    
    # Cleanup
    os.remove(filepath)

if __name__ == '__main__':
    capture_and_upload()
```

### 3.4 Bash Script with cURL (for Crontab)
```bash
#!/bin/bash
# /home/pi/auto_upload.sh
SERVER="https://192.168.1.100:8443"
API_KEY="rpi-cam1-secret-key-2024"
CAMERA="cam1"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
IMAGE="/tmp/snapshot_${TIMESTAMP}.jpg"

# Capture
libcamera-still -o "$IMAGE" --width 1920 --height 1080 -t 1000 --nopreview

# Upload
curl -sk -X POST "${SERVER}/api/upload" \
    -F "file=@${IMAGE}" \
    -F "api_key=${API_KEY}" \
    -F "camera_id=${CAMERA}" \
    -F "project_name=Aeroponic System 1" \
    -F "timestamp=${TIMESTAMP}"

# Cleanup
rm -f "$IMAGE"
```

---

## 4. Crontab Configuration (Automated Scheduling)

### Setup on Raspberry Pi
```bash
crontab -e
```

### Schedule Examples
```cron
# Every 30 minutes (recommended for growth monitoring)
*/30 * * * * /usr/bin/python3 /home/pi/upload_snapshot.py --capture >> /home/pi/upload.log 2>&1

# Every hour
0 * * * * /home/pi/auto_upload.sh >> /home/pi/upload.log 2>&1

# Three times a day (6 AM, 12 PM, 6 PM)
0 6,12,18 * * * /home/pi/auto_upload.sh >> /home/pi/upload.log 2>&1

# Every 15 minutes during daytime only (6 AM to 8 PM)
*/15 6-20 * * * /home/pi/auto_upload.sh >> /home/pi/upload.log 2>&1
```

### Verify Crontab
```bash
crontab -l                    # List scheduled jobs
tail -f /home/pi/upload.log   # Monitor upload log
```

---

## 5. Test Server Connectivity

### From Raspberry Pi
```bash
# Test if server is reachable
curl -sk https://SERVER_IP:8443/api/upload/test

# Expected response:
# {
#     "success": true,
#     "message": "API Upload endpoint is ready",
#     "usage": { ... }
# }
```

### Using the Python Script
```bash
python3 upload_snapshot.py --test --server https://SERVER_IP:8443
```

---

## 6. Data Flow Diagram

```
┌─────────────────────┐       HTTPS POST /api/upload        ┌──────────────────────┐
│   Raspberry Pi      │ ───────────────────────────────────→ │   Flask Server       │
│                     │                                      │   (VM / Linux PC)    │
│  ┌───────────────┐  │   Form Data:                         │                      │
│  │ Camera Module │  │   • file: image.jpg                  │  ┌────────────────┐  │
│  │ (libcamera)   │  │   • api_key: rpi-cam1-xxx            │  │  Validate      │  │
│  └───────┬───────┘  │   • camera_id: cam1                  │  │  API Key       │  │
│          │ capture   │   • project_name: Aeroponic Sys 1    │  └───────┬────────┘  │
│  ┌───────▼───────┐  │   • timestamp: 2026-02-10_14-30-00   │          │           │
│  │ /tmp/snap.jpg │  │                                      │  ┌───────▼────────┐  │
│  └───────┬───────┘  │                                      │  │  Save to       │  │
│          │ upload    │                                      │  │  snapshots/    │  │
│  ┌───────▼───────┐  │                                      │  └───────┬────────┘  │
│  │ cURL/Python   │  │                                      │          │           │
│  │ requests.post │  │                                      │  ┌───────▼────────┐  │
│  └───────────────┘  │   ◄──────── JSON Response ────────── │  │  Insert into   │  │
│                     │   {success:true, snapshot_id:42}      │  │  SQLite DB     │  │
│  ┌───────────────┐  │                                      │  └────────────────┘  │
│  │ Crontab       │  │                                      │                      │
│  │ (scheduler)   │  │                                      │  Web GUI accessible  │
│  └───────────────┘  │                                      │  at /query, /stats   │
└─────────────────────┘                                      └──────────────────────┘
```

---

## 7. Security Notes

- **API Keys** are stored in `.env` file (never hardcoded in source)
- **HTTPS** is enforced with self-signed SSL certificate
- **File validation** checks extension and file type
- **Secure filenames** via `werkzeug.utils.secure_filename()`
- **Rate limiting** can be enabled for API endpoints
- **IP whitelisting** available in security settings

---

## 8. Source Code Location

| File | Description |
|------|-------------|
| `src/app.py` (line ~388) | API upload route handler |
| `raspberry_pi_scripts/upload_snapshot.py` | Python upload client |
| `raspberry_pi_scripts/upload_snapshot.sh` | Bash upload client |
| `src/config.py` | API_KEYS configuration |
| `src/auth.py` | Authentication system |
