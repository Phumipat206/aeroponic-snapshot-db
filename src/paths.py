"""
Dynamic Path Management System
==============================
ระบบจัดการ paths ที่ทำงานได้กับทุก OS (Windows, Linux, Mac)
ใช้ relative paths เพื่อให้ app portable
"""

import os
import sys
from pathlib import Path


def get_project_root():
    """
    ได้ root directory ของโปรเจค
    Works: C:/Projects/Task Description 4/
    """
    # ถ้า run จาก run.py → ขึ้นไป 2 level
    current_file = Path(__file__).resolve()
    
    # src/paths.py → ขึ้นไป 1 level → root
    project_root = current_file.parent.parent
    
    return project_root


class ProjectPaths:
    """จัดการ paths ทั้งหมดของโปรเจค"""
    
    # Root directories
    ROOT = get_project_root()
    SRC = ROOT / "src"
    SCRIPTS = ROOT / "scripts"
    DOCS = ROOT / "docs"
    TEMPLATES = ROOT / "templates"
    STATIC = ROOT / "static"
    
    # Data directories (auto-create if not exist)
    SNAPSHOTS = ROOT / "snapshots"
    VIDEOS = ROOT / "generated_videos"
    LOGS = ROOT / "logs"
    CACHE = ROOT / ".cache"
    
    # Database
    DATABASE = ROOT / "aeroponic_snapshots.db"
    
    # Config files
    ENV_FILE = ROOT / ".env"
    ENV_EXAMPLE = ROOT / ".env.example"
    
    @classmethod
    def create_required_dirs(cls):
        """สร้างโฟลเดอร์ที่จำเป็นทั้งหมด"""
        dirs_to_create = [
            cls.SNAPSHOTS,
            cls.VIDEOS,
            cls.LOGS,
            cls.CACHE,
        ]
        
        for directory in dirs_to_create:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def verify_structure(cls):
        """ตรวจสอบว่าโครงสร้างถูกต้อง"""
        required = [cls.SRC, cls.TEMPLATES, cls.SCRIPTS]
        missing = [d for d in required if not d.exists()]
        
        if missing:
            raise RuntimeError(f"Missing required directories: {missing}")
        
        return True


def get_snapshots_dir():
    """ได้ snapshots folder path"""
    return ProjectPaths.SNAPSHOTS


def get_videos_dir():
    """ได้ videos folder path"""
    return ProjectPaths.VIDEOS


def get_logs_dir():
    """ได้ logs folder path"""
    return ProjectPaths.LOGS


def get_database_path():
    """ได้ database file path"""
    return ProjectPaths.DATABASE


def get_config_path():
    """ได้ .env file path"""
    return ProjectPaths.ENV_FILE


def get_templates_folder():
    """ได้ templates folder path"""
    return ProjectPaths.TEMPLATES


def safe_join(base_path, *parts):
    """
    Safe path joining - ป้องกัน directory traversal
    
    Args:
        base_path: base directory
        *parts: path components
    
    Returns:
        Path object ที่ safe (ไม่เลยออกจาก base)
    """
    base = Path(base_path).resolve()
    result = base
    
    for part in parts:
        # ลบ .. เพื่อป้องกัน directory traversal
        part = str(part).replace("..", "").lstrip("/").lstrip("\\")
        result = result / part
    
    # ตรวจสอบว่าไม่ได้เลยออกจาก base
    try:
        result.resolve().relative_to(base)
    except ValueError:
        raise ValueError(f"Path traversal attempt detected: {parts}")
    
    return result


if __name__ == "__main__":
    # Test paths
    print("=== Project Paths ===")
    print(f"Root: {ProjectPaths.ROOT}")
    print(f"SRC: {ProjectPaths.SRC}")
    print(f"Snapshots: {ProjectPaths.SNAPSHOTS}")
    print(f"Videos: {ProjectPaths.VIDEOS}")
    print(f"Logs: {ProjectPaths.LOGS}")
    print(f"Database: {ProjectPaths.DATABASE}")
    print(f"Templates: {ProjectPaths.TEMPLATES}")
    print("\n✅ All paths configured successfully")
