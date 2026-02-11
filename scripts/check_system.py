"""
System Check Script
Verifies that all dependencies are installed and the system is ready to run.

Usage:
    python scripts/check_system.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.paths import ProjectPaths
from src.logger import get_logger

# Setup logger
logger = get_logger('system_check')

def check_python_version():
    """Check Python version"""
    print("Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"  ✅ Python {version.major}.{version.minor}.{version.micro} (OK)")
        return True
    else:
        print(f"  ❌ Python {version.major}.{version.minor}.{version.micro} (Need 3.8+)")
        return False

def check_dependencies():
    """Check if all required packages are installed"""
    print("\nChecking dependencies...")
    
    required_packages = [
        ('Flask', 'flask'),
        ('Werkzeug', 'werkzeug'),
        ('Pillow', 'PIL'),
        ('python-dateutil', 'dateutil'),
        ('OpenCV', 'cv2'),
        ('NumPy', 'numpy'),
        ('python-dotenv', 'dotenv'),
    ]
    
    all_ok = True
    
    for display_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"  ✅ {display_name} installed")
        except ImportError:
            print(f"  ❌ {display_name} NOT installed")
            all_ok = False
    
    return all_ok

def check_directories():
    """Check if required directories exist"""
    print("\nChecking directories...")
    
    from src.config import UPLOAD_FOLDER, VIDEOS_FOLDER, TEMPLATES_FOLDER
    
    dirs = [
        ('Snapshots folder', UPLOAD_FOLDER),
        ('Videos folder', VIDEOS_FOLDER),
        ('Templates folder', TEMPLATES_FOLDER),
    ]
    
    all_ok = True
    
    for name, path in dirs:
        if os.path.exists(path):
            print(f"  ✅ {name} exists: {path}")
        else:
            print(f"  ⚠️  {name} missing: {path} (will be created)")
            try:
                os.makedirs(path, exist_ok=True)
                print(f"     Created: {path}")
            except Exception as e:
                print(f"     ❌ Could not create: {e}")
                all_ok = False
    
    return all_ok

def check_database():
    """Check database"""
    print("\nChecking database...")
    
    from src.config import DATABASE_PATH
    
    if os.path.exists(DATABASE_PATH):
        size = os.path.getsize(DATABASE_PATH)
        print(f"  ✅ Database exists: {DATABASE_PATH} ({size} bytes)")
        
        # Try to query it
        try:
            from src.database import get_database_stats
            stats = get_database_stats()
            print(f"     Total snapshots: {stats['total_snapshots']}")
            print(f"     Total categories: {stats['total_categories']}")
            print(f"     Total videos: {stats['total_videos']}")
        except Exception as e:
            print(f"  ⚠️  Database exists but has issues: {e}")
            return False
    else:
        print(f"  ⚠️  Database not found: {DATABASE_PATH}")
        print(f"     Run 'python database.py' to create it")
        return False
    
    return True

def check_templates():
    """Check if HTML templates exist"""
    print("\nChecking templates...")
    
    required_templates = [
        'base.html',
        'index.html',
        'upload.html',
        'query.html',
        'daily_snapshots.html',
        'generate_video.html',
        'categories.html',
        'import_drive.html',
        'view_snapshot.html',
        'stats.html'
    ]
    
    all_ok = True
    missing = []
    
    for template in required_templates:
        path = os.path.join('templates', template)
        if os.path.exists(path):
            print(f"  ✅ {template}")
        else:
            print(f"  ❌ {template} missing")
            missing.append(template)
            all_ok = False
    
    if missing:
        print(f"\n  Missing templates: {', '.join(missing)}")
    
    return all_ok

def main():
    print("=" * 60)
    print("AEROPONIC SNAPSHOT DATABASE - SYSTEM CHECK")
    print("=" * 60)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Directories", check_directories),
        ("Templates", check_templates),
        ("Database", check_database),
    ]
    
    results = {}
    
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"\n❌ Error during {check_name} check: {e}")
            results[check_name] = False
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for check_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {check_name}")
        if not result:
            all_passed = False
    
    print()
    
    if all_passed:
        print("🎉 All checks passed! System is ready.")
        print("\nTo start the application:")
        print("  python app.py")
        print("\nThen visit: http://localhost:5000")
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
        print("\nTo install dependencies:")
        print("  pip install -r requirements.txt")
        print("\nTo initialize database:")
        print("  python database.py")
    
    print()
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
