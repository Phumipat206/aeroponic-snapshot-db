import os
from pathlib import Path
from dotenv import load_dotenv
from src.paths import ProjectPaths

# Load .env file if it exists
env_file = ProjectPaths.ENV_FILE
if env_file.exists():
    load_dotenv(env_file)

# Base directory
BASE_DIR = ProjectPaths.ROOT

# Database configuration
DATABASE_PATH = str(ProjectPaths.DATABASE)

# Storage configuration
UPLOAD_FOLDER = str(ProjectPaths.SNAPSHOTS)
VIDEOS_FOLDER = str(ProjectPaths.VIDEOS)
LOGS_FOLDER = str(ProjectPaths.LOGS)

# Templates folder
TEMPLATES_FOLDER = str(ProjectPaths.TEMPLATES)

# File Upload
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))

# Allowed extensions
ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'png,jpg,jpeg,gif,bmp').split(','))

# Video generation settings
VIDEO_FPS = int(os.getenv('VIDEO_FPS', 10))
VIDEO_QUALITY = int(os.getenv('VIDEO_QUALITY', 95))

# Server configuration
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')

# API Keys for Raspberry Pi upload
api_keys_str = os.getenv('API_KEYS', 'rpi-cam1-secret-key-2024,rpi-cam2-secret-key-2024,rpi-cam3-secret-key-2024')
API_KEYS = {key: f"Key {i+1}" for i, key in enumerate(api_keys_str.split(','))}

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_MAX_SIZE = int(os.getenv('LOG_MAX_SIZE', 10 * 1024 * 1024))
LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))

# Initialize required directories
try:
    ProjectPaths.create_required_dirs()
    ProjectPaths.verify_structure()
except RuntimeError as e:
    import logging
    logging.getLogger('config').warning(f"Path setup warning: {e}")

# Create necessary directories (backward compatibility)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

