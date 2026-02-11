"""
Folder Watcher - ระบบเฝ้าดูโฟลเดอร์อัตโนมัติ
================================================
สคริปต์นี้จะเฝ้าดูโฟลเดอร์ที่กำหนดและนำเข้ารูปภาพใหม่อัตโนมัติ

การใช้งาน:
    python scripts/folder_watcher.py --watch "C:/path/to/camera/folder" --category "หมวดหมู่"
    
ตัวอย่าง:
    python scripts/folder_watcher.py --watch "D:/CameraOutput" --category "Aeroponic System 1"
    python scripts/folder_watcher.py --watch "E:/GrowthPhotos" --category "ถาดปลูกที่ 1"
"""

import os
import sys
import time
import shutil
import argparse
import threading
from datetime import datetime
from pathlib import Path

# เพิ่ม project root สำหรับ import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.paths import ProjectPaths
from src.logger import get_logger

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("=" * 60)
    print("❌ ไม่พบ library 'watchdog'")
    print("กรุณาติดตั้งโดยใช้คำสั่ง:")
    print("   pip install watchdog")
    print("=" * 60)
    sys.exit(1)

from src.database import init_database as init_db, add_snapshot, get_category_by_name, add_category
from src.config import UPLOAD_FOLDER as SNAPSHOT_FOLDER
from src.utils import get_image_dimensions, extract_datetime_from_filename

# Setup logger
logger = get_logger('folder_watcher')

# รูปแบบไฟล์ที่รองรับ
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}

# สถานะการทำงาน
watcher_status = {
    'is_running': False,
    'watch_path': None,
    'category': None,
    'imported_count': 0,
    'last_import': None,
    'errors': []
}


class SnapshotHandler(FileSystemEventHandler):
    """Handler สำหรับจัดการไฟล์ใหม่ที่เข้ามา"""
    
    def __init__(self, category_name, verbose=True):
        self.category_name = category_name
        self.verbose = verbose
        self.processing = set()  # เก็บไฟล์ที่กำลังประมวลผล
        
    def log(self, message):
        """พิมพ์ข้อความพร้อม timestamp"""
        if self.verbose:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] {message}")
    
    def is_supported_image(self, path):
        """ตรวจสอบว่าเป็นไฟล์รูปภาพที่รองรับหรือไม่"""
        ext = Path(path).suffix.lower()
        return ext in SUPPORTED_EXTENSIONS
    
    def wait_for_file_complete(self, filepath, timeout=30):
        """รอจนกว่าไฟล์จะเขียนเสร็จสมบูรณ์"""
        last_size = -1
        stable_count = 0
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                current_size = os.path.getsize(filepath)
                if current_size == last_size and current_size > 0:
                    stable_count += 1
                    if stable_count >= 3:  # ขนาดคงที่ 3 ครั้ง = เขียนเสร็จ
                        return True
                else:
                    stable_count = 0
                    last_size = current_size
            except OSError:
                pass
            time.sleep(0.5)
        
        return False
    
    def import_image(self, filepath):
        """นำเข้ารูปภาพเข้าสู่ระบบ"""
        global watcher_status
        
        if filepath in self.processing:
            return
        
        self.processing.add(filepath)
        
        try:
            # รอให้ไฟล์เขียนเสร็จ
            if not self.wait_for_file_complete(filepath):
                self.log(f"⚠️ Timeout รอไฟล์: {filepath}")
                return
            
            filename = os.path.basename(filepath)
            
            # หา/สร้าง category
            category = get_category_by_name(self.category_name)
            if not category:
                add_category(self.category_name, parent_id=None, description=f"Auto-created from folder watcher")
                category = get_category_by_name(self.category_name)
            
            category_id = category['id']
            
            # สร้างโฟลเดอร์ปลายทาง
            dest_folder = os.path.join(SNAPSHOT_FOLDER, f"category_{category_id}")
            os.makedirs(dest_folder, exist_ok=True)
            
            # สร้างชื่อไฟล์ใหม่พร้อม timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = Path(filename).suffix
            new_filename = f"auto_{timestamp}_{filename}"
            dest_path = os.path.join(dest_folder, new_filename)
            
            # คัดลอกไฟล์
            shutil.copy2(filepath, dest_path)
            
            # Get image dimensions and file size
            file_size = os.path.getsize(dest_path)
            width, height = get_image_dimensions(dest_path)
            capture_time = extract_datetime_from_filename(filename)
            if not capture_time:
                capture_time = datetime.now()

            # เพิ่มข้อมูลลง database
            relative_path = os.path.relpath(dest_path, SNAPSHOT_FOLDER)
            add_snapshot(
                filename=new_filename,
                original_filename=filename,
                filepath=relative_path,
                category_id=category_id,
                capture_time=capture_time.strftime('%Y-%m-%d %H:%M:%S'),
                file_size=file_size,
                width=width,
                height=height,
                source='folder_watcher',
                notes=f"Auto-imported from: {filepath}"
            )

            # อัปเดตสถานะ
            watcher_status['imported_count'] += 1
            watcher_status['last_import'] = datetime.now().isoformat()
            
            self.log(f"✅ นำเข้าสำเร็จ: {filename} → หมวดหมู่ '{self.category_name}'")
            
        except Exception as e:
            error_msg = f"❌ เกิดข้อผิดพลาด: {filepath} - {str(e)}"
            self.log(error_msg)
            watcher_status['errors'].append({
                'time': datetime.now().isoformat(),
                'file': filepath,
                'error': str(e)
            })
            # เก็บแค่ 100 errors ล่าสุด
            if len(watcher_status['errors']) > 100:
                watcher_status['errors'] = watcher_status['errors'][-100:]
        
        finally:
            self.processing.discard(filepath)
    
    def on_created(self, event):
        """เรียกเมื่อมีไฟล์ใหม่ถูกสร้าง"""
        if event.is_directory:
            return
        
        if self.is_supported_image(event.src_path):
            self.log(f"📁 พบไฟล์ใหม่: {event.src_path}")
            # ใช้ thread แยกเพื่อไม่ให้ block
            thread = threading.Thread(target=self.import_image, args=(event.src_path,))
            thread.daemon = True
            thread.start()
    
    def on_moved(self, event):
        """เรียกเมื่อมีไฟล์ถูกย้ายเข้ามา"""
        if event.is_directory:
            return
        
        if self.is_supported_image(event.dest_path):
            self.log(f"📁 พบไฟล์ย้ายเข้ามา: {event.dest_path}")
            thread = threading.Thread(target=self.import_image, args=(event.dest_path,))
            thread.daemon = True
            thread.start()


class FolderWatcher:
    """คลาสหลักสำหรับจัดการ Folder Watcher"""
    
    def __init__(self):
        self.observer = None
        self.handler = None
    
    def start(self, watch_path, category_name, verbose=True):
        """เริ่มเฝ้าดูโฟลเดอร์"""
        global watcher_status
        
        if self.observer and self.observer.is_alive():
            print("⚠️ Watcher กำลังทำงานอยู่แล้ว")
            return False
        
        # ตรวจสอบโฟลเดอร์
        if not os.path.exists(watch_path):
            print(f"❌ ไม่พบโฟลเดอร์: {watch_path}")
            return False
        
        if not os.path.isdir(watch_path):
            print(f"❌ ไม่ใช่โฟลเดอร์: {watch_path}")
            return False
        
        # เริ่มต้น database
        init_db()
        
        # สร้าง handler และ observer
        self.handler = SnapshotHandler(category_name, verbose)
        self.observer = Observer()
        self.observer.schedule(self.handler, watch_path, recursive=True)
        self.observer.start()
        
        # อัปเดตสถานะ
        watcher_status['is_running'] = True
        watcher_status['watch_path'] = watch_path
        watcher_status['category'] = category_name
        
        print("=" * 60)
        print("🔄 Folder Watcher เริ่มทำงานแล้ว!")
        print("=" * 60)
        print(f"📁 เฝ้าดูโฟลเดอร์: {watch_path}")
        print(f"📂 หมวดหมู่: {category_name}")
        print(f"🖼️ รองรับไฟล์: {', '.join(SUPPORTED_EXTENSIONS)}")
        print("-" * 60)
        print("กด Ctrl+C เพื่อหยุดการทำงาน")
        print("=" * 60)
        
        return True
    
    def stop(self):
        """หยุดเฝ้าดูโฟลเดอร์"""
        global watcher_status
        
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None
        
        watcher_status['is_running'] = False
        print("\n✅ หยุด Folder Watcher แล้ว")
    
    def get_status(self):
        """ดูสถานะปัจจุบัน"""
        return watcher_status


def scan_existing_files(watch_path, category_name, verbose=True):
    """สแกนและนำเข้าไฟล์ที่มีอยู่แล้วในโฟลเดอร์"""
    print(f"\n🔍 กำลังสแกนไฟล์ที่มีอยู่ใน: {watch_path}")
    
    handler = SnapshotHandler(category_name, verbose)
    count = 0
    
    for root, dirs, files in os.walk(watch_path):
        for filename in files:
            filepath = os.path.join(root, filename)
            if handler.is_supported_image(filepath):
                handler.import_image(filepath)
                count += 1
    
    print(f"✅ สแกนและนำเข้าไฟล์ทั้งหมด {count} ไฟล์")
    return count


def main():
    """ฟังก์ชันหลัก"""
    parser = argparse.ArgumentParser(
        description="Folder Watcher - เฝ้าดูโฟลเดอร์และนำเข้ารูปภาพอัตโนมัติ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ตัวอย่างการใช้งาน:
  python folder_watcher.py --watch "D:/CameraOutput" --category "ระบบ Aeroponic 1"
  python folder_watcher.py --watch "E:/Photos" --category "ถาดปลูก A" --scan
  python folder_watcher.py --watch "./input" --category "Test" --quiet
        """
    )
    
    parser.add_argument(
        '--watch', '-w',
        required=True,
        help='โฟลเดอร์ที่ต้องการเฝ้าดู'
    )
    
    parser.add_argument(
        '--category', '-c',
        required=True,
        help='ชื่อหมวดหมู่สำหรับรูปภาพที่นำเข้า'
    )
    
    parser.add_argument(
        '--scan', '-s',
        action='store_true',
        help='สแกนและนำเข้าไฟล์ที่มีอยู่แล้วก่อนเริ่มเฝ้าดู'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='โหมดเงียบ - แสดงเฉพาะข้อความสำคัญ'
    )
    
    args = parser.parse_args()
    
    # แปลง path เป็น absolute path
    watch_path = os.path.abspath(args.watch)
    
    # สแกนไฟล์ที่มีอยู่ก่อน (ถ้าเลือก)
    if args.scan:
        scan_existing_files(watch_path, args.category, not args.quiet)
    
    # เริ่ม watcher
    watcher = FolderWatcher()
    if watcher.start(watch_path, args.category, not args.quiet):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            watcher.stop()


# สำหรับเรียกใช้จาก Flask app
def start_watcher_thread(watch_path, category_name):
    """เริ่ม watcher ใน background thread"""
    watcher = FolderWatcher()
    if watcher.start(watch_path, category_name):
        return watcher
    return None


if __name__ == "__main__":
    main()
