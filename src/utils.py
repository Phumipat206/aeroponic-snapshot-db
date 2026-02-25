import os
import re
import uuid
import hashlib
from datetime import datetime
from PIL import Image
from src.config import ALLOWED_EXTENSIONS
from src.logger import get_logger

logger = get_logger('utils')

# Strict allowed extensions for upload validation
STRICT_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# Maximum file size in bytes (20 MB)
MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024


def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_file_strict(filename):
    """Check if file has a strictly allowed image extension (jpg, jpeg, png only)"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in STRICT_IMAGE_EXTENSIONS


def compute_file_hash(filepath):
    """Compute SHA-256 hash of a file for duplicate detection.
    Reads file in chunks to handle large files efficiently."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        logger.warning(f"Error computing file hash: {e}")
        return None


def compute_data_hash(data_bytes):
    """Compute SHA-256 hash from raw bytes (e.g., from an uploaded file stream)."""
    return hashlib.sha256(data_bytes).hexdigest()

def generate_unique_filename(original_filename):
    """Generate a unique filename to avoid conflicts"""
    ext = original_filename.rsplit('.', 1)[1].lower()
    unique_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{timestamp}_{unique_id}.{ext}"

def get_image_dimensions(filepath):
    """Get image width and height"""
    try:
        with Image.open(filepath) as img:
            return img.size  # Returns (width, height)
    except Exception as e:
        logger.warning(f"Error getting image dimensions: {e}")
        return (0, 0)

def format_file_size(size_bytes):
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def parse_datetime(datetime_str):
    """Parse datetime string in various formats"""
    if not datetime_str:
        return None

    # Normalise the ISO 'T' separator so the standard formats work
    datetime_str = datetime_str.strip().replace('T', ' ')

    formats = [
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d',
        '%d-%m-%Y %H:%M:%S',
        '%d-%m-%Y %H:%M',
        '%d-%m-%Y',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    # If no format works, return None
    return None

def extract_datetime_from_filename(filename):
    """Attempt to extract datetime from filename"""
    # Common patterns: 20240123_143000, 2024-01-23_14-30-00, etc.
    
    patterns = [
        r'(\d{8})_(\d{6})',  # 20240123_143000
        r'(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})',  # 2024-01-23_14-30-00
        r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',  # 20240123143000
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            groups = match.groups()
            try:
                if len(groups) == 2:  # Format: 20240123_143000
                    date_str = groups[0]
                    time_str = groups[1]
                    dt_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
                    return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                elif len(groups) == 6:
                    dt_str = f"{groups[0]}-{groups[1]}-{groups[2]} {groups[3]}:{groups[4]}:{groups[5]}"
                    return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
    
    return None

def create_thumbnail(image_path, thumbnail_path, size=(300, 300)):
    """Create a thumbnail for an image"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumbnail_path, quality=85, optimize=True)
        return True
    except Exception as e:
        logger.warning(f"Error creating thumbnail: {e}")
        return False
