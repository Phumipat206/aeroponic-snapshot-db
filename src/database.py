import sqlite3
import os
import threading
from contextlib import contextmanager
from datetime import datetime
from src.config import DATABASE_PATH
from src.logger import get_logger

# Get logger for this module
logger = get_logger('database')


def _normalize_db_path(stored_path: str, base_folder: str) -> str:
    """Convert a stored filepath to a valid path on the current OS.
    Handles Windows paths stored in DB when running on Linux (and vice versa)."""
    if not stored_path:
        return stored_path
    if os.path.exists(stored_path):
        return stored_path
    folder_name = os.path.basename(base_folder)
    for sep in ('\\', '/'):
        marker = folder_name + sep
        idx = stored_path.find(marker)
        if idx != -1:
            relative = stored_path[idx + len(marker):]
            relative = relative.replace('\\', os.sep).replace('/', os.sep)
            return os.path.join(base_folder, relative)
    basename = os.path.basename(stored_path.replace('\\', '/'))
    return os.path.join(base_folder, basename)

# --- Connection Pool (Fix #5) ---
_local = threading.local()

VALID_ORDER_COLUMNS = {
    'capture_time ASC', 'capture_time DESC',
    'upload_time ASC', 'upload_time DESC',
    'file_size ASC', 'file_size DESC',
    'id ASC', 'id DESC',
    'filename ASC', 'filename DESC',
    'original_filename ASC', 'original_filename DESC',
}


@contextmanager
def get_db():
    """Context manager for database connections with connection reuse per thread."""
    conn = getattr(_local, 'connection', None)
    reused = conn is not None
    if not reused:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _local.connection = conn
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        if not reused:
            _local.connection = None
            conn.close()


def get_db_connection():
    """Create a database connection (legacy compatibility)"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize the database with required tables"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Create categories table for hierarchical classification
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES categories (id)
            )
        ''')

        # Create snapshots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                category_id INTEGER,
                capture_time TIMESTAMP NOT NULL,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_size INTEGER,
                width INTEGER,
                height INTEGER,
                source TEXT,
                tags TEXT,
                notes TEXT,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        ''')

        # เพิ่มคอลัมน์ project_name และ camera_id (Migration) — Fix #18: specific exception
        try:
            cursor.execute('ALTER TABLE snapshots ADD COLUMN project_name TEXT')
            logger.info("Added column: project_name")
        except sqlite3.OperationalError:
            pass  # คอลัมน์มีอยู่แล้ว

        try:
            cursor.execute('ALTER TABLE snapshots ADD COLUMN camera_id TEXT')
            logger.info("Added column: camera_id")
        except sqlite3.OperationalError:
            pass  # คอลัมน์มีอยู่แล้ว

        # Migration: add file_hash column for duplicate detection
        try:
            cursor.execute('ALTER TABLE snapshots ADD COLUMN file_hash TEXT')
            logger.info("Added column: file_hash")
        except sqlite3.OperationalError:
            pass  # column already exists

        # Create indexes for efficient querying
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_capture_time 
            ON snapshots (capture_time)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_category 
            ON snapshots (category_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_source 
            ON snapshots (source)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_project_name 
            ON snapshots (project_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_camera_id 
            ON snapshots (camera_id)
        ''')

        # Composite indexes for common query patterns
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_category_capture 
            ON snapshots (category_id, capture_time)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_project_camera 
            ON snapshots (project_name, camera_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_file_hash
            ON snapshots (file_hash)
        ''')

        # Create video_generations table to track generated videos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_filename TEXT NOT NULL,
                video_path TEXT NOT NULL,
                snapshot_count INTEGER,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                fps INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                query_params TEXT
            )
        ''')

        conn.commit()

        # Insert default categories if none exist
        cursor.execute('SELECT COUNT(*) FROM categories')
        if cursor.fetchone()[0] == 0:
            default_categories = [
                ('Root System', None, 'Root development and health monitoring'),
                ('Leaf System', None, 'Leaf growth and condition tracking'),
                ('Overall Plant', None, 'Full plant view snapshots'),
                ('Environment', None, 'Environmental conditions and setup'),
                ('Daily Growth', 1, 'Daily root system development'),
                ('Weekly Overview', 1, 'Weekly root system summary'),
                ('Daily Growth', 2, 'Daily leaf development'),
                ('Health Issues', 2, 'Leaf problems and diseases'),
            ]

            cursor.executemany(
                'INSERT INTO categories (name, parent_id, description) VALUES (?, ?, ?)',
                default_categories
            )
            conn.commit()

    logger.info(f"Database initialized at {DATABASE_PATH}")


def get_categories_tree():
    """Get categories in hierarchical structure"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM categories ORDER BY parent_id, name')
        categories = cursor.fetchall()
    return categories


def add_category(name, parent_id=None, description=''):
    """Add a new category"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO categories (name, parent_id, description) VALUES (?, ?, ?)',
            (name, parent_id, description)
        )
        conn.commit()
        category_id = cursor.lastrowid
    return category_id


def get_category_by_name(name):
    """Get a category by name. Returns dict or None."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM categories WHERE name = ?', (name,))
        row = cursor.fetchone()
        return dict(row) if row else None


def check_duplicate_hash(file_hash):
    """Check if a file with the same hash already exists in the database.
    Returns the existing snapshot dict if duplicate, None otherwise."""
    if not file_hash:
        return None
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM snapshots WHERE file_hash = ? LIMIT 1', (file_hash,))
        row = cursor.fetchone()
        return dict(row) if row else None


def is_leaf_category(category_id):
    """Check if a category is a leaf (has no children). Returns True if leaf, False if parent."""
    if category_id is None:
        return True
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM categories WHERE parent_id = ?', (category_id,))
        child_count = cursor.fetchone()[0]
        return child_count == 0


def category_exists(category_id):
    """Check if a category_id exists in the database."""
    if category_id is None:
        return True
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM categories WHERE id = ?', (category_id,))
        return cursor.fetchone()[0] > 0


def get_leaf_categories():
    """Get only leaf categories (those with no children)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.* FROM categories c
            WHERE NOT EXISTS (
                SELECT 1 FROM categories child WHERE child.parent_id = c.id
            )
            ORDER BY c.parent_id, c.name
        ''')
        return cursor.fetchall()


def add_snapshot(filename, original_filename, filepath, category_id,
                 capture_time, file_size, width, height, source='upload',
                 tags='', notes='', project_name=None, camera_id=None, file_hash=None):
    """Add a new snapshot to the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO snapshots 
            (filename, original_filename, filepath, category_id, capture_time, 
             file_size, width, height, source, tags, notes, project_name, camera_id, file_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (filename, original_filename, filepath, category_id, capture_time,
              file_size, width, height, source, tags, notes, project_name, camera_id, file_hash))
        conn.commit()
        snapshot_id = cursor.lastrowid
    return snapshot_id


def add_snapshots_batch(snapshot_list):
    """Add multiple snapshots in a single transaction (Fix #10)

    Args:
        snapshot_list: list of dicts with keys matching add_snapshot params

    Returns:
        int: number of successfully inserted snapshots
    """
    if not snapshot_list:
        return 0
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.executemany('''
            INSERT INTO snapshots 
            (filename, original_filename, filepath, category_id, capture_time, 
             file_size, width, height, source, tags, notes, project_name, camera_id, file_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            (s['filename'], s['original_filename'], s['filepath'], s.get('category_id'),
             s['capture_time'], s.get('file_size', 0), s.get('width', 0), s.get('height', 0),
             s.get('source', 'upload'), s.get('tags', ''), s.get('notes', ''),
             s.get('project_name'), s.get('camera_id'), s.get('file_hash'))
            for s in snapshot_list
        ])
        conn.commit()
    return len(snapshot_list)


def _build_filter_clause(category_id=None, start_time=None, end_time=None,
                          source=None, tags=None, project_name=None, camera_id=None):
    """Build shared WHERE clause for query/count (eliminates duplication)."""
    clauses = []
    params = []

    if category_id is not None:
        clauses.append('category_id = ?')
        params.append(category_id)
    if start_time:
        clauses.append('capture_time >= ?')
        params.append(start_time)
    if end_time:
        clauses.append('capture_time <= ?')
        params.append(end_time)
    if source:
        clauses.append('source = ?')
        params.append(source)
    if tags:
        clauses.append('tags LIKE ?')
        params.append(f'%{tags}%')
    if project_name:
        clauses.append('project_name = ?')
        params.append(project_name)
    if camera_id:
        clauses.append('camera_id = ?')
        params.append(camera_id)

    where = ' AND '.join(clauses) if clauses else '1=1'
    return where, params


def query_snapshots(category_id=None, start_time=None, end_time=None,
                    source=None, tags=None, limit=None, offset=0,
                    order_by='capture_time DESC', project_name=None, camera_id=None):
    """Query snapshots with various filters"""
    # Fix #2: SQL Injection — whitelist ORDER BY
    if order_by not in VALID_ORDER_COLUMNS:
        order_by = 'capture_time DESC'

    where, params = _build_filter_clause(
        category_id, start_time, end_time, source, tags, project_name, camera_id)

    query = f'SELECT * FROM snapshots WHERE {where} ORDER BY {order_by}'

    if limit:
        query += ' LIMIT ? OFFSET ?'
        params.extend([limit, offset])

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        snapshots = cursor.fetchall()
    return snapshots


def query_snapshots_with_count(category_id=None, start_time=None, end_time=None,
                               source=None, tags=None, limit=None, offset=0,
                               order_by='capture_time DESC', project_name=None, camera_id=None):
    """Query snapshots AND count in one connection (Fix #9)

    Returns:
        tuple: (snapshots_list, total_count)
    """
    if order_by not in VALID_ORDER_COLUMNS:
        order_by = 'capture_time DESC'

    where, params = _build_filter_clause(
        category_id, start_time, end_time, source, tags, project_name, camera_id)

    with get_db() as conn:
        cursor = conn.cursor()

        # Count
        cursor.execute(f'SELECT COUNT(*) FROM snapshots WHERE {where}', params)
        total_count = cursor.fetchone()[0]

        # Query
        query = f'SELECT * FROM snapshots WHERE {where} ORDER BY {order_by}'
        query_params = list(params)
        if limit:
            query += ' LIMIT ? OFFSET ?'
            query_params.extend([limit, offset])
        cursor.execute(query, query_params)
        snapshots = cursor.fetchall()

    return snapshots, total_count


def count_snapshots(category_id=None, start_time=None, end_time=None,
                    source=None, tags=None, project_name=None, camera_id=None):
    """Count total snapshots matching filters (for pagination)"""
    where, params = _build_filter_clause(
        category_id, start_time, end_time, source, tags, project_name, camera_id)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM snapshots WHERE {where}', params)
        count = cursor.fetchone()[0]
    return count


def get_snapshots_by_daily_time(hour, minute, tolerance_minutes=5, project_name=None, camera_id=None):
    """Get snapshots captured at approximately the same time each day"""
    with get_db() as conn:
        cursor = conn.cursor()

        query = '''
            SELECT * FROM snapshots
            WHERE 
                CAST(strftime('%H', capture_time) AS INTEGER) = ?
                AND ABS(CAST(strftime('%M', capture_time) AS INTEGER) - ?) <= ?
        '''
        params = [hour, minute, tolerance_minutes]

        if project_name:
            query += ' AND project_name = ?'
            params.append(project_name)

        if camera_id:
            query += ' AND camera_id = ?'
            params.append(camera_id)

        query += ' ORDER BY capture_time'

        cursor.execute(query, params)
        snapshots = cursor.fetchall()
    return snapshots


def get_snapshot_by_id(snapshot_id):
    """Get a specific snapshot by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM snapshots WHERE id = ?', (snapshot_id,))
        snapshot = cursor.fetchone()
    return snapshot


def add_video_generation(video_filename, video_path, snapshot_count,
                         start_time, end_time, fps, query_params=''):
    """Record a generated video in the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO video_generations 
            (video_filename, video_path, snapshot_count, start_time, end_time, fps, query_params)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (video_filename, video_path, snapshot_count, start_time, end_time, fps, query_params))
        conn.commit()
        video_id = cursor.lastrowid
    return video_id


def get_database_stats():
    """Get database statistics — Fix #8: combined into 2 queries instead of 5"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                COUNT(*) AS total_snapshots,
                COALESCE(SUM(file_size), 0) AS total_size_bytes,
                MIN(capture_time) AS earliest_snapshot,
                MAX(capture_time) AS latest_snapshot
            FROM snapshots
        ''')
        row = cursor.fetchone()

        stats = {
            'total_snapshots': row['total_snapshots'],
            'total_size_bytes': row['total_size_bytes'],
            'earliest_snapshot': row['earliest_snapshot'],
            'latest_snapshot': row['latest_snapshot'],
        }

        cursor.execute('''
            SELECT 
                (SELECT COUNT(*) FROM categories) AS total_categories,
                (SELECT COUNT(*) FROM video_generations) AS total_videos
        ''')
        row2 = cursor.fetchone()
        stats['total_categories'] = row2['total_categories']
        stats['total_videos'] = row2['total_videos']

    return stats


# ==================== DELETE FUNCTIONS ====================

def delete_snapshot(snapshot_id):
    """ลบ snapshot จากฐานข้อมูลและลบไฟล์"""
    from src.config import UPLOAD_FOLDER
    with get_db() as conn:
        cursor = conn.cursor()

        # ดึงข้อมูล filepath ก่อนลบ
        cursor.execute('SELECT filepath FROM snapshots WHERE id = ?', (snapshot_id,))
        row = cursor.fetchone()

        if row:
            filepath = _normalize_db_path(row['filepath'], UPLOAD_FOLDER)
            # ลบไฟล์ถ้ามีอยู่
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except OSError as e:
                logger.warning(f"Could not remove file {filepath}: {e}")

            # ลบจากฐานข้อมูล
            cursor.execute('DELETE FROM snapshots WHERE id = ?', (snapshot_id,))
            conn.commit()
            return True, "ลบ snapshot สำเร็จ"

    return False, "ไม่พบ snapshot"


def delete_category(category_id):
    """ลบหมวดหมู่ (ถ้าไม่มี snapshot หรือหมวดหมู่ย่อยใช้อยู่)"""
    with get_db() as conn:
        cursor = conn.cursor()

        # ตรวจสอบว่ามี snapshot ใช้อยู่ไหม
        cursor.execute('SELECT COUNT(*) FROM snapshots WHERE category_id = ?', (category_id,))
        if cursor.fetchone()[0] > 0:
            return False, "ไม่สามารถลบได้ มี snapshot ใช้หมวดหมู่นี้อยู่"

        # ตรวจสอบว่ามีหมวดหมู่ลูกไหม
        cursor.execute('SELECT COUNT(*) FROM categories WHERE parent_id = ?', (category_id,))
        if cursor.fetchone()[0] > 0:
            return False, "ไม่สามารถลบได้ มีหมวดหมู่ย่อยอยู่"

        cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        conn.commit()
    return True, "ลบหมวดหมู่สำเร็จ"


def delete_video(video_id):
    """ลบวิดีโอจากฐานข้อมูลและลบไฟล์"""
    from src.config import VIDEOS_FOLDER
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('SELECT video_path FROM video_generations WHERE id = ?', (video_id,))
        row = cursor.fetchone()

        if row:
            video_path = _normalize_db_path(row['video_path'], VIDEOS_FOLDER)
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
            except OSError as e:
                logger.warning(f"Could not remove video file {video_path}: {e}")

            cursor.execute('DELETE FROM video_generations WHERE id = ?', (video_id,))
            conn.commit()
            return True, "ลบวิดีโอสำเร็จ"

    return False, "ไม่พบวิดีโอ"


def delete_multiple_snapshots(snapshot_ids):
    """ลบหลาย snapshot พร้อมกัน — Fix #4: single connection, batch delete"""
    from src.config import UPLOAD_FOLDER
    if not snapshot_ids:
        return 0, []

    deleted = 0
    errors = []

    with get_db() as conn:
        cursor = conn.cursor()

        # Fetch all filepaths in one query
        placeholders = ','.join('?' for _ in snapshot_ids)
        cursor.execute(
            f'SELECT id, filepath FROM snapshots WHERE id IN ({placeholders})',
            list(snapshot_ids)
        )
        rows = cursor.fetchall()

        found_ids = set()
        for row in rows:
            found_ids.add(row['id'])
            filepath = _normalize_db_path(row['filepath'], UPLOAD_FOLDER)
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except OSError as e:
                logger.warning(f"Could not remove file {filepath}: {e}")

        # Delete all found snapshots in one statement
        if found_ids:
            id_list = list(found_ids)
            placeholders = ','.join('?' for _ in id_list)
            cursor.execute(
                f'DELETE FROM snapshots WHERE id IN ({placeholders})',
                id_list
            )
            conn.commit()
            deleted = cursor.rowcount

        # Report missing IDs
        for sid in snapshot_ids:
            if sid not in found_ids:
                errors.append(f"ID {sid}: ไม่พบ snapshot")

    return deleted, errors


# ==================== UPDATE FUNCTIONS ====================

def update_snapshot(snapshot_id, category_id=None, tags=None, notes=None, capture_time=None):
    """อัพเดทข้อมูล snapshot"""
    with get_db() as conn:
        cursor = conn.cursor()

        updates = []
        params = []

        if category_id is not None:
            updates.append('category_id = ?')
            params.append(category_id if category_id != 0 else None)

        if tags is not None:
            updates.append('tags = ?')
            params.append(tags)

        if notes is not None:
            updates.append('notes = ?')
            params.append(notes)

        if capture_time is not None:
            updates.append('capture_time = ?')
            params.append(capture_time)

        if updates:
            params.append(snapshot_id)
            query = f"UPDATE snapshots SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            return True, "อัพเดทสำเร็จ"

    return False, "ไม่มีข้อมูลที่จะอัพเดท"


def update_category(category_id, name=None, description=None, parent_id=None):
    """อัพเดทข้อมูลหมวดหมู่"""
    with get_db() as conn:
        cursor = conn.cursor()

        updates = []
        params = []

        if name is not None:
            updates.append('name = ?')
            params.append(name)

        if description is not None:
            updates.append('description = ?')
            params.append(description)

        if parent_id is not None:
            updates.append('parent_id = ?')
            params.append(parent_id if parent_id != 0 else None)

        if updates:
            params.append(category_id)
            query = f"UPDATE categories SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            return True, "อัพเดทหมวดหมู่สำเร็จ"

    return False, "ไม่มีข้อมูลที่จะอัพเดท"


# ==================== UTILITY FUNCTIONS ====================

def cleanup_missing_files():
    """ลบ record ที่ไฟล์หายไปแล้ว — Fix #6: batched processing, not all-in-memory"""
    from src.config import UPLOAD_FOLDER
    deleted_count = 0
    batch_size = 500

    with get_db() as conn:
        cursor = conn.cursor()

        # Process in batches to avoid loading everything into memory
        offset = 0
        ids_to_delete = []

        while True:
            cursor.execute(
                'SELECT id, filepath FROM snapshots LIMIT ? OFFSET ?',
                (batch_size, offset)
            )
            rows = cursor.fetchall()
            if not rows:
                break

            for row in rows:
                norm_path = _normalize_db_path(row['filepath'], UPLOAD_FOLDER)
                if not os.path.exists(norm_path):
                    ids_to_delete.append(row['id'])

            offset += batch_size

        # Batch delete missing
        if ids_to_delete:
            placeholders = ','.join('?' for _ in ids_to_delete)
            cursor.execute(
                f'DELETE FROM snapshots WHERE id IN ({placeholders})',
                ids_to_delete
            )
            conn.commit()
            deleted_count = cursor.rowcount

    return deleted_count


def get_all_videos():
    """ดึงรายการวิดีโอทั้งหมด"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM video_generations ORDER BY created_at DESC')
        videos = cursor.fetchall()
    return videos


def get_video_by_id(video_id):
    """ดึงข้อมูลวิดีโอตาม ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM video_generations WHERE id = ?', (video_id,))
        video = cursor.fetchone()
    return video


def get_category_by_id(category_id):
    """ดึงข้อมูลหมวดหมู่ตาม ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
        category = cursor.fetchone()
    return category


def search_snapshots(keyword):
    """ค้นหา snapshot จาก tags, notes, filename"""
    with get_db() as conn:
        cursor = conn.cursor()
        search_term = f'%{keyword}%'
        cursor.execute('''
            SELECT * FROM snapshots 
            WHERE tags LIKE ? 
               OR notes LIKE ? 
               OR original_filename LIKE ?
            ORDER BY capture_time DESC
        ''', (search_term, search_term, search_term))
        snapshots = cursor.fetchall()
    return snapshots


def get_category_snapshot_count():
    """นับจำนวน snapshot ในแต่ละหมวดหมู่"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.id, c.name, COUNT(s.id) as snapshot_count
            FROM categories c
            LEFT JOIN snapshots s ON c.id = s.category_id
            GROUP BY c.id, c.name
            ORDER BY snapshot_count DESC
        ''')
        result = cursor.fetchall()
    return result


def get_distinct_projects():
    """ดึงรายชื่อ Project ทั้งหมดที่ไม่ซ้ำกัน"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT project_name FROM snapshots 
            WHERE project_name IS NOT NULL AND project_name != ''
            ORDER BY project_name
        ''')
        result = [row['project_name'] for row in cursor.fetchall()]
    return result


def get_distinct_cameras():
    """ดึงรายชื่อ Camera ทั้งหมดที่ไม่ซ้ำกัน"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT camera_id FROM snapshots 
            WHERE camera_id IS NOT NULL AND camera_id != ''
            ORDER BY camera_id
        ''')
        result = [row['camera_id'] for row in cursor.fetchall()]
    return result


def get_cameras_by_project(project_name):
    """ดึงรายชื่อ Camera ในโปรเจกต์ที่ระบุ"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT camera_id FROM snapshots 
            WHERE project_name = ? AND camera_id IS NOT NULL AND camera_id != ''
            ORDER BY camera_id
        ''', (project_name,))
        result = [row['camera_id'] for row in cursor.fetchall()]
    return result


def get_filter_options():
    """ดึงตัวเลือก Filter ทั้งหมด (Projects และ Cameras) — single connection"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT project_name FROM snapshots 
            WHERE project_name IS NOT NULL AND project_name != ''
            ORDER BY project_name
        ''')
        projects = [row['project_name'] for row in cursor.fetchall()]

        cursor.execute('''
            SELECT DISTINCT camera_id FROM snapshots 
            WHERE camera_id IS NOT NULL AND camera_id != ''
            ORDER BY camera_id
        ''')
        cameras = [row['camera_id'] for row in cursor.fetchall()]

    return {
        'projects': projects,
        'cameras': cameras,
    }


if __name__ == '__main__':
    init_database()
    logger.info("Database initialized successfully!")
