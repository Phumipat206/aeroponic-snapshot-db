# Folder Structure & Recursive Import Documentation

> **ตอบข้อสงสัยอาจารย์ (Fig.8):** ระบบรองรับการอ่านโฟลเดอร์ซ้อนโฟลเดอร์ (Recursive) และสามารถ Parse ชื่อโฟลเดอร์วันที่ `[n]_MM-DD` เพื่อดึงข้อมูลวันที่มากำกับภาพได้  
> **Date:** February 2026

---

## 1. Supported Folder Structures

### Structure Level 1: Flat (Single Folder)
```
/images/
├── snapshot_001.jpg
├── snapshot_002.jpg
└── snapshot_003.jpg
```
**Command:**
```bash
python3 scripts/batch_import.py /images/
```

### Structure Level 2: Camera Folders Only
```
/data/
├── cam1/
│   ├── snapshot_001.jpg
│   └── snapshot_002.jpg
├── cam2/
│   ├── snapshot_001.jpg
│   └── snapshot_002.jpg
└── cam3/
    └── snapshot_001.jpg
```
**Command:**
```bash
python3 scripts/batch_import.py /data/ --parse-structure
```

### Structure Level 3: Camera + Date Folders (Real Farm Layout)
```
/farm_data/
├── cam1/
│   ├── 1_01-15/              ← Sequence 1, January 15
│   │   ├── photo_0001.jpg
│   │   ├── photo_0002.jpg
│   │   └── photo_0003.jpg
│   ├── 2_01-16/              ← Sequence 2, January 16
│   │   ├── photo_0001.jpg
│   │   └── photo_0002.jpg
│   └── 3_01-17/              ← Sequence 3, January 17
│       └── photo_0001.jpg
├── cam2/
│   ├── 1_01-15/
│   │   └── photo_0001.jpg
│   └── 2_01-16/
│       └── photo_0001.jpg
└── cam3/
    └── 1_01-15/
        └── photo_0001.jpg
```
**Command:**
```bash
python3 scripts/batch_import.py /farm_data/ --parse-structure --source "Farm Camera Data"
```

---

## 2. Date Folder Naming Convention

### Format: `[n]_MM-DD`

| Part | Meaning | Example |
|------|---------|---------|
| `n` | Sequence number (1, 2, 3...) | `1`, `2`, `15` |
| `_` | Separator | `_` |
| `MM` | Month (01-12) | `01` = January |
| `DD` | Day (01-31) | `15` = 15th day |

### Examples
| Folder Name | Sequence | Date |
|-------------|----------|------|
| `1_01-15` | 1st batch | January 15 |
| `2_01-16` | 2nd batch | January 16 |
| `3_02-01` | 3rd batch | February 1 |
| `10_12-25` | 10th batch | December 25 |

### How the System Parses Dates
```python
# File: scripts/batch_import.py → parse_date_folder()
import re

def parse_date_folder(folder_name):
    pattern = r'^(\d+)_(\d{2})-(\d{2})$'
    match = re.match(pattern, folder_name)
    
    if match:
        return {
            'sequence': int(match.group(1)),  # Batch number
            'month': match.group(2),          # MM
            'day': match.group(3),            # DD
            'date_str': f"{match.group(2)}-{match.group(3)}"  # MM-DD
        }
    return None

# Example:
# parse_date_folder("1_01-15") → {'sequence': 1, 'month': '01', 'day': '15', 'date_str': '01-15'}
# parse_date_folder("2_01-16") → {'sequence': 2, 'month': '01', 'day': '16', 'date_str': '01-16'}
# parse_date_folder("random")  → None (not a date folder, skipped)
```

---

## 3. Camera Folder Detection

### Supported Camera Folder Names
```python
# File: scripts/batch_import.py → parse_camera_folder()
# Recognized patterns (case-insensitive):
#   cam1, cam2, cam10
#   camera_1, camera_2
#   camera1, camera2
#   CAM1, CAM2
```

| Input Folder | Recognized? | Camera ID |
|-------------|-------------|-----------|
| `cam1` | ✅ Yes | `cam1` |
| `cam2` | ✅ Yes | `cam2` |
| `camera_1` | ✅ Yes | `camera_1` |
| `CAM3` | ✅ Yes | `CAM3` |
| `photos` | ❌ No | — |
| `images` | ❌ No | — |

---

## 4. Recursive File Traversal (How It Works)

### Code Logic
```python
# File: scripts/batch_import.py → import_folder()

# Default: recursive=True — walks ALL subdirectories
if recursive:
    walk_iterator = os.walk(folder_path)
else:
    walk_iterator = [(folder_path, [], os.listdir(folder_path))]

for root, dirs, files in walk_iterator:
    for filename in files:
        if not allowed_file(filename):  # Check extension
            continue
        
        # Parse folder structure for metadata
        relative_path = os.path.relpath(root, folder_path)
        path_parts = relative_path.split(os.sep)
        
        # Level 1: Check for camera folder
        if len(path_parts) >= 1:
            cam_info = parse_camera_folder(path_parts[0])
            # → Sets camera_id = "cam1"
        
        # Level 2: Check for date folder
        if len(path_parts) >= 2:
            date_info = parse_date_folder(path_parts[1])
            # → Sets month, day, sequence
```

### What Gets Extracted

For a file at path: `/farm_data/cam1/2_01-16/photo_0001.jpg`

| Field | Value | Source |
|-------|-------|--------|
| `camera_id` | `cam1` | Parsed from folder `cam1` |
| `sequence` | `2` | Parsed from folder `2_01-16` |
| `month` | `01` | Parsed from folder `2_01-16` |
| `day` | `16` | Parsed from folder `2_01-16` |
| `capture_time` | `2026-01-16 12:00:00` | Constructed from month+day |
| `tags` | `camera:cam1,date:01-16,seq:2` | Auto-generated |
| `notes` | `Camera: cam1 | Date folder: 01-16 (seq 2)` | Auto-generated |

---

## 5. Analyze-Only Mode

Before importing, you can analyze a folder structure first:

```bash
python3 scripts/batch_import.py /farm_data/ --analyze-only
```

**Output:**
```
===========================================================
FOLDER STRUCTURE ANALYSIS
===========================================================

📁 Folder: /farm_data/
   Structure type: camera_with_dates
   Cameras found: 3
   Has date folders: True

📷 Camera Details:

   cam1:
      └── 1_01-15 (sequence: 1, date: 01-15)
      └── 2_01-16 (sequence: 2, date: 01-16)
      └── 3_01-17 (sequence: 3, date: 01-17)

   cam2:
      └── 1_01-15 (sequence: 1, date: 01-15)
      └── 2_01-16 (sequence: 2, date: 01-16)

   cam3:
      └── 1_01-15 (sequence: 1, date: 01-15)

💡 To import with structure parsing, run:
   python batch_import.py "/farm_data/" --parse-structure
```

---

## 6. Import Examples

### Basic Import
```bash
python3 scripts/batch_import.py /path/to/images/ --source "Manual Import"
```

### Import with Full Structure Parsing
```bash
python3 scripts/batch_import.py /path/to/farm_data/ \
    --parse-structure \
    --source "Farm Camera Data" \
    --tags "batch,farm1"
```

### Import to Specific Category
```bash
python3 scripts/batch_import.py /path/to/images/ \
    --category 1 \
    --source "Root System Photos"
```

### Import Without Subdirectories
```bash
python3 scripts/batch_import.py /path/to/images/ --no-recursive
```

---

## 7. Web-Based Import (Alternative)

The web interface also supports import via the Upload page:
1. Navigate to **Upload** → select image(s)
2. Choose category, add tags
3. Click Upload

For Google Drive imports:
1. Navigate to **Import from Drive**
2. Paste Google Drive folder link
3. System downloads and imports automatically

---

## 8. Source Code References

| File | Function | Purpose |
|------|----------|---------|
| `scripts/batch_import.py` | `parse_date_folder()` | Parse `[n]_MM-DD` folder names |
| `scripts/batch_import.py` | `parse_camera_folder()` | Detect `cam1`, `camera_2` patterns |
| `scripts/batch_import.py` | `analyze_folder_structure()` | Analyze folder tree |
| `scripts/batch_import.py` | `import_folder()` | Recursive import with metadata |
| `src/utils.py` | `allowed_file()` | Check file extension |
| `src/utils.py` | `extract_datetime_from_filename()` | Extract date from filename |
| `src/database.py` | `add_snapshot()` | Insert snapshot record into DB |
