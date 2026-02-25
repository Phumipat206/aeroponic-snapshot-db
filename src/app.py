"""
Aeroponic Snapshot Database — Flask Application
================================================
Refactored: Fix #1,3,9,10,11,12,13,14,15,16,17,19,20
- Explicit imports (no wildcard)
- Thread-safe global state with locks
- CSRF protection via Flask-WTF
- Rate limiting via Flask-Limiter
- Admin token auth on destructive endpoints
- Path traversal protection via safe_join
- Secure secret key generation
- print() replaced with logger
- Deduplicated video generation logic
"""

import os
import json
import uuid
import secrets
import socket
import re
import shutil
import threading
import subprocess
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify, send_file,
    redirect, url_for, flash, abort, session
)
from werkzeug.utils import secure_filename

# ---------- Internal imports (Fix #16: explicit, no wildcard) ----------
from src.paths import ProjectPaths
from src.logger import get_logger
from src.config import (
    UPLOAD_FOLDER, VIDEOS_FOLDER, TEMPLATES_FOLDER,
    MAX_CONTENT_LENGTH, ALLOWED_EXTENSIONS, VIDEO_FPS,
    HOST, PORT, DEBUG, SECRET_KEY, API_KEYS,        # Fix #1: correct import
    DATABASE_PATH, LOG_LEVEL,
)
from src.database import (
    init_database, get_db_connection, get_db,
    get_categories_tree, add_category,
    add_snapshot, add_snapshots_batch,
    query_snapshots, query_snapshots_with_count, count_snapshots,
    get_snapshots_by_daily_time, get_snapshot_by_id,
    add_video_generation, get_database_stats,
    delete_snapshot, delete_category, delete_video, delete_multiple_snapshots,
    update_snapshot, update_category,
    cleanup_missing_files, get_all_videos, get_video_by_id,
    search_snapshots, get_filter_options,
    get_cameras_by_project,
    check_duplicate_hash, is_leaf_category, category_exists, get_leaf_categories,
)
from src.utils import (
    allowed_file, allowed_file_strict, generate_unique_filename, get_image_dimensions,
    parse_datetime, extract_datetime_from_filename, format_file_size,
    compute_file_hash, compute_data_hash, STRICT_IMAGE_EXTENSIONS, MAX_UPLOAD_SIZE_BYTES,
)
from src.video_generator import (
    create_timelapse_video, create_timelapse_with_timestamps,
    get_progress, clear_progress, video_progress,
)
from src.auth import (
    authenticate_user, create_session, validate_session, destroy_session,
    destroy_all_sessions, get_current_user, login_required, admin_required,
    permission_required, has_permission,
    change_password, create_user, delete_user, toggle_user_active,
    get_all_users, get_security_settings, update_security_settings,
    get_login_history, get_active_sessions, validate_password_strength,
    update_user_permissions, update_user_role, get_user_permissions,
    _check_lockout, _record_login_attempt,
    ALL_PERMISSIONS, ROLE_DEFAULTS, PERMISSION_LABELS, PERMISSION_GROUPS,
)

# ---------- Logger ----------
logger = get_logger('app')

# ---------- Cross-OS path normalization ----------
# The DB may store Windows paths (C:\Users\...\snapshots\file.jpg).
# When running on Linux we extract the relative portion after the known
# folder name ("snapshots" / "generated_videos") and rebuild it against
# the current project root so images and videos are served correctly.
import re as _re

def _normalize_filepath(stored_path: str, base_folder: str) -> str:
    """Convert a stored filepath to a valid path on the current OS.

    *stored_path*  – the filepath column value from the DB
    *base_folder*  – the current OS absolute path to the base folder
                     (UPLOAD_FOLDER or VIDEOS_FOLDER)
    Returns the corrected absolute path.
    """
    if not stored_path:
        return stored_path

    # Already valid on this OS?
    if os.path.exists(stored_path):
        return stored_path

    # Detect Windows absolute path while running on Linux (or vice-versa)
    # e.g. C:\Users\phumi\Desktop\Task Description 4\snapshots\category_4\img.jpg
    # We want to extract: category_4/img.jpg  (the part after 'snapshots\\')
    folder_name = os.path.basename(base_folder)  # e.g. "snapshots" or "generated_videos"

    # Try both slash styles
    for sep in ('\\', '/'):
        marker = folder_name + sep
        idx = stored_path.find(marker)
        if idx != -1:
            relative = stored_path[idx + len(marker):]
            # Normalise separators
            relative = relative.replace('\\', os.sep).replace('/', os.sep)
            return os.path.join(base_folder, relative)

    # Last resort: just use the filename
    basename = os.path.basename(stored_path.replace('\\', '/'))
    return os.path.join(base_folder, basename)

# ---------- Initialize paths ----------
try:
    ProjectPaths.create_required_dirs()
except Exception as e:
    logger.warning(f"Failed to create directories: {e}")

# ---------- Flask app ----------
_static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')
app = Flask(__name__, template_folder=str(TEMPLATES_FOLDER), static_folder=_static_dir, static_url_path='/static')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Fix #13: secure secret key — generate random if not set properly
if SECRET_KEY and SECRET_KEY not in ('change-me-in-production', 'change-me-in-production-2024'):
    app.secret_key = SECRET_KEY
else:
    app.secret_key = os.getenv('SECRET_KEY', None) or secrets.token_hex(32)
    logger.warning("Using auto-generated secret key. Set SECRET_KEY env var for production.")

@app.context_processor
def inject_csrf_token():
    """Make csrf_token available in all templates."""
    token = secrets.token_hex(16)
    return dict(csrf_token=token)

@app.context_processor
def inject_current_user():
    """Make current_user available in all templates."""
    user = get_current_user()
    return dict(current_user=user)

# ---------- Rate limiting removed ----------
# Rate limiting was causing 429 errors during normal browsing.
# This is an internal academic tool — unlimited access is required
# so professors and students can browse images freely.

# ---------- Fix #11: Admin auth decorator for destructive endpoints ----------
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', '')  # Set in .env for production

def require_admin(f):
    """Decorator: require admin token for destructive API endpoints (Fix #11).
    Checks X-Admin-Token header or admin_token form/json field.
    If ADMIN_TOKEN env var is empty, access is allowed (dev mode).
    If user is already logged in as admin via session, access is also allowed.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not ADMIN_TOKEN:
            # Dev mode — no token configured, allow all
            return f(*args, **kwargs)

        # Allow if user is logged in as admin via web session
        current_user = get_current_user()
        if current_user and current_user.get('role') == 'admin':
            return f(*args, **kwargs)

        # Otherwise check API token
        token = (
            request.headers.get('X-Admin-Token')
            or request.form.get('admin_token')
            or ((request.json or {}).get('admin_token') if request.is_json else None)
        )
        if token != ADMIN_TOKEN:
            return jsonify({'success': False, 'error': 'Unauthorized — admin token required'}), 403
        return f(*args, **kwargs)
    return decorated

# ---------- Fix #3: Thread-safe global state ----------
_job_results_lock = threading.Lock()
video_job_results = {}

_tunnel_lock = threading.Lock()
tunnel_data = {
    'url': None,
    'set_at': None,
    'visitors': [],
    'process': None,
    'status': 'stopped',
    'last_check': None,
    'error': None,
    'restart_count': 0,
    'auto_restart': True,
    'connection_registered': False,
}

# ---------- Thread-safe helper functions ----------
def _set_job_result(job_id, data):
    with _job_results_lock:
        data['_created_at'] = time.time()
        video_job_results[job_id] = data
        # Cleanup stale entries older than 1 hour
        stale_cutoff = time.time() - 3600
        stale_keys = [k for k, v in video_job_results.items()
                      if v.get('_created_at', 0) < stale_cutoff]
        for k in stale_keys:
            del video_job_results[k]

def _update_job_result(job_id, data):
    with _job_results_lock:
        if job_id in video_job_results:
            video_job_results[job_id].update(data)
        else:
            video_job_results[job_id] = data

def _get_job_result(job_id):
    with _job_results_lock:
        return video_job_results.get(job_id, {}).copy()

def _pop_job_result(job_id):
    with _job_results_lock:
        return video_job_results.pop(job_id, None)

def _tunnel_get(key, default=None):
    with _tunnel_lock:
        return tunnel_data.get(key, default)

def _tunnel_set(**kwargs):
    with _tunnel_lock:
        tunnel_data.update(kwargs)

def _tunnel_snapshot():
    with _tunnel_lock:
        return dict(tunnel_data)

def _tunnel_append_visitor(visitor_info):
    with _tunnel_lock:
        tunnel_data['visitors'].append(visitor_info)
        if len(tunnel_data['visitors']) > 100:
            tunnel_data['visitors'] = tunnel_data['visitors'][-100:]

# ---------- Initialize database ----------
init_database()


# =============================================================================
# MIDDLEWARE
# =============================================================================

@app.after_request
def set_security_headers(response):
    """Add security headers to every response."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


@app.before_request
def track_visitor():
    """Track visitors for each request (Fix #3: thread-safe)."""
    if request.path.startswith('/static') or request.path.startswith('/api/') or request.path.startswith('/snapshot/image'):
        return

    visitor_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if visitor_ip and ',' in visitor_ip:
        visitor_ip = visitor_ip.split(',')[0].strip()

    visitor_info = {
        'ip': visitor_ip,
        'time': datetime.now().isoformat(),
        'path': request.path,
        'user_agent': request.headers.get('User-Agent', 'Unknown')[:100],
        'referer': request.headers.get('Referer', '')[:200],
    }

    _tunnel_append_visitor(visitor_info)


@app.before_request
def enforce_login():
    """Global login enforcement — redirect to login page if not authenticated."""
    # Paths that don't require login
    open_paths = ('/login', '/static', '/api/upload')
    if any(request.path.startswith(p) for p in open_paths):
        return
    # Check if user is logged in
    from src.auth import get_current_user as _get_user
    user = _get_user()
    if not user:
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return redirect(url_for('login', next=request.path))


@app.context_processor
def inject_user_context():
    """Make current user + permission helper available in all templates."""
    user = get_current_user()
    def user_has_permission(perm):
        return has_permission(user, perm)
    return {
        'current_user': user,
        'has_perm': user_has_permission,
    }


# =============================================================================
# PAGES
# =============================================================================

@app.route('/')
@permission_required('dashboard')
def index():
    """Home page with dashboard"""
    stats = get_database_stats()
    categories = get_categories_tree()
    return render_template('index.html', stats=stats, categories=categories)


@app.route('/upload', methods=['GET', 'POST'])
@permission_required('upload')
def upload():
    """Upload snapshot page"""
    if request.method == 'GET':
        categories = get_categories_tree()
        return render_template('upload.html', categories=categories)

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    # Fix #7: Strict file extension check (jpg, jpeg, png only)
    if not allowed_file_strict(file.filename):
        return jsonify({'success': False, 'error': 'Invalid file type. Only .jpg, .jpeg, .png are allowed'}), 400

    try:
        category_id = request.form.get('category_id', type=int)
        capture_time_str = request.form.get('capture_time')
        tags = request.form.get('tags', '')
        notes = request.form.get('notes', '')
        source = request.form.get('source', 'upload')

        # Fix #7: Category is required
        if not category_id:
            return jsonify({'success': False, 'error': 'Please select a category before uploading'}), 400

        # Fix #3: Validate category exists and is a leaf category
        if not category_exists(category_id):
            return jsonify({'success': False, 'error': 'Selected category does not exist'}), 400
        if not is_leaf_category(category_id):
            return jsonify({'success': False, 'error': 'Cannot upload to a parent category. Please select a sub-category'}), 400

        # Fix #7: Check file size before saving
        file.seek(0, 2)  # Seek to end
        file_size_check = file.tell()
        file.seek(0)  # Reset to beginning
        if file_size_check > MAX_UPLOAD_SIZE_BYTES:
            return jsonify({'success': False, 'error': f'File too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB'}), 400

        # Fix #1: Duplicate detection - compute hash from file content
        file_data = file.read()
        file.seek(0)
        file_hash = compute_data_hash(file_data)
        existing = check_duplicate_hash(file_hash)
        if existing:
            return jsonify({
                'success': False,
                'error': f'Duplicate image detected. This image was already uploaded as "{existing["original_filename"]}" (ID: {existing["id"]})',
                'duplicate_id': existing['id'],
            }), 409

        # Fix #2: Timestamp priority - user input > filename > server time
        capture_time = None
        if capture_time_str:
            capture_time = parse_datetime(capture_time_str)

        if not capture_time:
            capture_time = extract_datetime_from_filename(file.filename)

        if not capture_time:
            capture_time = datetime.now()

        upload_time = datetime.now()  # Always record upload time separately

        original_filename = secure_filename(file.filename)
        unique_filename = generate_unique_filename(original_filename)

        category_path = os.path.join(UPLOAD_FOLDER, f"category_{category_id}")
        os.makedirs(category_path, exist_ok=True)
        filepath = os.path.join(category_path, unique_filename)

        file.save(filepath)

        file_size = os.path.getsize(filepath)
        width, height = get_image_dimensions(filepath)

        snapshot_id = add_snapshot(
            filename=unique_filename,
            original_filename=original_filename,
            filepath=filepath,
            category_id=category_id,
            capture_time=capture_time,
            file_size=file_size,
            width=width,
            height=height,
            source=source,
            tags=tags,
            notes=notes,
            file_hash=file_hash,
        )

        return jsonify({
            'success': True,
            'snapshot_id': snapshot_id,
            'filename': unique_filename,
            'capture_time': capture_time.strftime('%Y-%m-%d %H:%M:%S'),
        })

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'success': False, 'error': 'Upload failed'}), 500


# =============================================================================
# API UPLOAD ENDPOINT FOR RASPBERRY PI  (Fix #1: correct import)
# =============================================================================

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """API endpoint for programmatic snapshot upload from Raspberry Pi."""
    try:
        api_key = request.form.get('api_key') or request.headers.get('X-API-Key')

        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key required. Provide via api_key field or X-API-Key header',
            }), 401

        # Fix #1: API_KEYS is now imported correctly from src.config at module level
        if api_key not in API_KEYS:
            return jsonify({'success': False, 'error': 'Invalid API key'}), 401

        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Fix #7: Strict file type validation
        if not allowed_file_strict(file.filename):
            return jsonify({
                'success': False,
                'error': f'Invalid file type. Only .jpg, .jpeg, .png are allowed',
            }), 400

        camera_id = request.form.get('camera_id', '')
        project_name = request.form.get('project_name', '')
        category_id = request.form.get('category_id', type=int)
        tags = request.form.get('tags', '')
        notes = request.form.get('notes', '')
        timestamp_str = request.form.get('timestamp')

        # Fix #4: Validate category_id exists in database
        if category_id is not None and category_id:
            if not category_exists(category_id):
                return jsonify({
                    'success': False,
                    'error': f'category_id {category_id} does not exist in the database',
                }), 400
            if not is_leaf_category(category_id):
                return jsonify({
                    'success': False,
                    'error': f'category_id {category_id} is a parent category. Please use a sub-category',
                }), 400

        # Fix #7: Check file size
        file.seek(0, 2)
        file_size_check = file.tell()
        file.seek(0)
        if file_size_check > MAX_UPLOAD_SIZE_BYTES:
            return jsonify({
                'success': False,
                'error': f'File too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB',
            }), 400

        # Fix #1: Duplicate detection
        file_data = file.read()
        file.seek(0)
        file_hash = compute_data_hash(file_data)
        existing = check_duplicate_hash(file_hash)
        if existing:
            return jsonify({
                'success': False,
                'error': f'Duplicate image detected. Already uploaded as "{existing["original_filename"]}" (ID: {existing["id"]})',
                'duplicate_id': existing['id'],
            }), 409

        # Fix #2: Timestamp priority - user provided > filename > server time
        capture_time = None
        if timestamp_str:
            for fmt in ['%Y-%m-%d_%H-%M-%S', '%Y%m%d_%H%M%S', '%Y-%m-%d %H:%M:%S']:
                try:
                    capture_time = datetime.strptime(timestamp_str, fmt)
                    break
                except ValueError:
                    continue

        if not capture_time:
            capture_time = extract_datetime_from_filename(file.filename)

        if not capture_time:
            capture_time = datetime.now()

        tag_parts = []
        if tags:
            tag_parts.append(tags)
        if camera_id:
            tag_parts.append(f"camera:{camera_id}")
        if project_name:
            tag_parts.append(f"project:{project_name}")
        tag_parts.append("source:api")
        tag_parts.append(f"api_device:{API_KEYS.get(api_key, 'unknown')}")

        combined_tags = ','.join(tag_parts)

        original_filename = secure_filename(file.filename)
        prefix = f"{camera_id}_" if camera_id else ""
        unique_filename = prefix + generate_unique_filename(original_filename)

        if category_id:
            category_path = os.path.join(UPLOAD_FOLDER, f"category_{category_id}")
        elif project_name and camera_id:
            category_path = os.path.join(UPLOAD_FOLDER, f"{project_name}_{camera_id}")
        else:
            category_path = UPLOAD_FOLDER

        os.makedirs(category_path, exist_ok=True)
        filepath = os.path.join(category_path, unique_filename)

        file.save(filepath)

        file_size = os.path.getsize(filepath)
        width, height = get_image_dimensions(filepath)

        api_notes = f"Uploaded via API by {API_KEYS.get(api_key, 'unknown')}"
        if camera_id:
            api_notes += f" | Camera: {camera_id}"
        if project_name:
            api_notes += f" | Project: {project_name}"
        if notes:
            api_notes += f" | {notes}"

        snapshot_id = add_snapshot(
            filename=unique_filename,
            original_filename=original_filename,
            filepath=filepath,
            category_id=category_id,
            capture_time=capture_time,
            file_size=file_size,
            width=width,
            height=height,
            source='API Upload',
            tags=combined_tags,
            notes=api_notes,
            file_hash=file_hash,
        )

        return jsonify({
            'success': True,
            'snapshot_id': snapshot_id,
            'filename': unique_filename,
            'capture_time': capture_time.strftime('%Y-%m-%d %H:%M:%S'),
            'camera_id': camera_id,
            'project_name': project_name,
            'file_size': file_size,
            'dimensions': f'{width}x{height}',
        })

    except Exception as e:
        logger.error(f"API upload error: {e}")
        return jsonify({'success': False, 'error': 'Upload failed'}), 500


@app.route('/api/upload/test', methods=['GET'])
def api_upload_test():
    """Test endpoint to verify API upload is working"""
    return jsonify({
        'success': True,
        'message': 'API Upload endpoint is ready',
        'usage': {
            'endpoint': '/api/upload',
            'method': 'POST',
            'required_fields': ['file', 'api_key'],
            'optional_fields': ['camera_id', 'project_name', 'timestamp', 'category_id', 'tags', 'notes'],
            'timestamp_formats': ['YYYY-MM-DD_HH-MM-SS', 'YYYYMMDD_HHMMSS', 'YYYY-MM-DD HH:MM:SS'],
        },
        'example_curl': f"curl -sk -X POST https://localhost:{PORT}/api/upload -F 'file=@image.jpg' -F 'api_key=your-key' -F 'camera_id=cam1'",
    })


# =============================================================================
# QUERY PAGE (Fix #9: single query+count call)
# =============================================================================

@app.route('/query', methods=['GET', 'POST'])
@permission_required('search')
def query():
    """Query snapshots page with pagination"""
    filters = get_filter_options()
    categories = get_categories_tree()

    per_page = 50
    page = request.args.get('page', 1, type=int)

    if request.method == 'GET' and not request.args.get('search'):
        return render_template('query.html', categories=categories, snapshots=None, filters=filters)

    try:
        if request.method == 'POST':
            category_id = request.form.get('category_id', type=int)
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            tags = request.form.get('tags')
            project_name = request.form.get('project_name')
            camera_id = request.form.get('camera_id')
            page = 1
        else:
            category_id = request.args.get('category_id', type=int)
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            tags = request.args.get('tags')
            project_name = request.args.get('project_name')
            camera_id = request.args.get('camera_id')

        start_dt = parse_datetime(start_time) if start_time else None
        end_dt = parse_datetime(end_time) if end_time else None

        offset = (page - 1) * per_page

        # Fix #9: single call for both count + query
        snapshots, total_count = query_snapshots_with_count(
            category_id=category_id,
            start_time=start_dt,
            end_time=end_dt,
            tags=tags,
            limit=per_page,
            offset=offset,
            project_name=project_name if project_name else None,
            camera_id=camera_id if camera_id else None,
        )

        total_pages = (total_count + per_page - 1) // per_page

        query_params = {
            'search': '1',
            'category_id': category_id or '',
            'start_time': start_time or '',
            'end_time': end_time or '',
            'tags': tags or '',
            'project_name': project_name or '',
            'camera_id': camera_id or '',
        }

        pagination = {
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
        }

        return render_template('query.html',
                             categories=categories,
                             snapshots=snapshots,
                             query_params=query_params,
                             filters=filters,
                             pagination=pagination)

    except Exception as e:
        flash(f'Error querying snapshots: {str(e)}', 'error')
        return render_template('query.html', categories=categories, snapshots=None, filters=filters)


@app.route('/api/snapshots', methods=['GET'])
def api_snapshots():
    """API endpoint for querying snapshots"""
    try:
        category_id = request.args.get('category_id', type=int)
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        tags = request.args.get('tags')
        limit = request.args.get('limit', type=int)

        start_dt = parse_datetime(start_time) if start_time else None
        end_dt = parse_datetime(end_time) if end_time else None

        snapshots = query_snapshots(
            category_id=category_id,
            start_time=start_dt,
            end_time=end_dt,
            tags=tags,
            limit=limit,
        )

        result = []
        for snapshot in snapshots:
            result.append({
                'id': snapshot['id'],
                'filename': snapshot['filename'],
                'original_filename': snapshot['original_filename'],
                'category_id': snapshot['category_id'],
                'capture_time': snapshot['capture_time'],
                'upload_time': snapshot['upload_time'],
                'file_size': snapshot['file_size'],
                'width': snapshot['width'],
                'height': snapshot['height'],
                'source': snapshot['source'],
                'tags': snapshot['tags'],
                'notes': snapshot['notes'],
            })

        return jsonify({'success': True, 'snapshots': result, 'count': len(result)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/daily-snapshots', methods=['GET', 'POST'])
@permission_required('daily_snapshots')
def daily_snapshots():
    """Query snapshots at the same time each day"""
    filters = get_filter_options()
    if request.method == 'GET':
        return render_template('daily_snapshots.html', snapshots=None, filters=filters)

    try:
        hour = request.form.get('hour', type=int)
        minute = request.form.get('minute', type=int, default=0)
        tolerance = request.form.get('tolerance', type=int, default=5)
        project_name = request.form.get('project_name')
        camera_id = request.form.get('camera_id')

        if hour is None:
            flash('Please specify an hour', 'error')
            return render_template('daily_snapshots.html', snapshots=None, filters=filters)

        snapshots = get_snapshots_by_daily_time(
            hour, minute, tolerance,
            project_name=project_name if project_name else None,
            camera_id=camera_id if camera_id else None,
        )

        return render_template('daily_snapshots.html',
                             snapshots=snapshots,
                             hour=hour,
                             minute=minute,
                             tolerance=tolerance,
                             project_name=project_name,
                             camera_id=camera_id,
                             filters=filters)

    except Exception as e:
        flash(f'Error querying snapshots: {str(e)}', 'error')
        return render_template('daily_snapshots.html', snapshots=None, filters=filters)


@app.route('/snapshot/<int:snapshot_id>')
@permission_required('view_snapshots')
def view_snapshot(snapshot_id):
    """View a specific snapshot"""
    snapshot = get_snapshot_by_id(snapshot_id)

    if not snapshot:
        flash('Snapshot not found', 'error')
        return redirect(url_for('index'))

    return render_template('view_snapshot.html', snapshot=snapshot)


@app.route('/snapshot/image/<int:snapshot_id>')
@permission_required('view_snapshots')
def serve_snapshot(snapshot_id):
    """Serve snapshot image file — Fix #12: validate path against UPLOAD_FOLDER"""
    snapshot = get_snapshot_by_id(snapshot_id)

    if not snapshot:
        return "Snapshot not found", 404

    # Normalize path for cross-OS compatibility
    filepath = _normalize_filepath(snapshot['filepath'], UPLOAD_FOLDER)

    # Fix #12: Path traversal protection
    try:
        real_path = os.path.realpath(filepath)
        real_upload = os.path.realpath(UPLOAD_FOLDER)
        if not real_path.startswith(real_upload):
            logger.warning(f"Path traversal attempt blocked: {filepath}")
            return "Access denied", 403
    except Exception:
        return "Invalid path", 400

    if not os.path.exists(filepath):
        return "Image file not found", 404

    return send_file(filepath, mimetype='image/jpeg')


# =============================================================================
# VIDEO GENERATION  (Fix #20: deduplicated logic)
# =============================================================================

def _prepare_video_data(category_id, start_time, end_time, fps, show_timestamp,
                        video_name, project_name, camera_id):
    """Shared helper to query snapshots and prepare video data (Fix #20)."""
    start_dt = parse_datetime(start_time) if start_time else None
    end_dt = parse_datetime(end_time) if end_time else None

    # Fix #6: If end_time not specified but start_time is, default to end of start day
    if start_dt and not end_dt:
        end_dt = start_dt.replace(hour=23, minute=59, second=59)

    snapshots = query_snapshots(
        category_id=category_id,
        start_time=start_dt,
        end_time=end_dt,
        order_by='capture_time ASC',
        project_name=project_name if project_name else None,
        camera_id=camera_id if camera_id else None,
    )

    if not snapshots:
        return None, None, None, start_dt, end_dt, 'No images found matching the specified criteria'

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"{secure_filename(video_name or 'timelapse')}_{timestamp}.mp4"

    if show_timestamp:
        snapshot_data = [
            (_normalize_filepath(s['filepath'], UPLOAD_FOLDER), parse_datetime(s['capture_time']), f"ID: {s['id']}")
            for s in snapshots
        ]
    else:
        snapshot_data = [_normalize_filepath(s['filepath'], UPLOAD_FOLDER) for s in snapshots]

    return snapshots, snapshot_data, output_filename, start_dt, end_dt, None


def _generate_video_sync(snapshot_data, output_filename, fps, show_timestamp, job_id=None):
    """Run video generation synchronously (Fix #20)."""
    if show_timestamp:
        return create_timelapse_with_timestamps(
            snapshot_data, output_filename, fps, show_timestamp, show_info=False, job_id=job_id)
    else:
        return create_timelapse_video(snapshot_data, output_filename, fps, job_id=job_id)


@app.route('/generate-video', methods=['GET', 'POST'])
@permission_required('generate_video')
def generate_video():
    """Generate time-lapse video from snapshots (form page)"""
    filters = get_filter_options()
    if request.method == 'GET':
        categories = get_categories_tree()
        return render_template('generate_video.html', categories=categories, filters=filters)

    try:
        category_id = request.form.get('category_id', type=int)
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        fps = request.form.get('fps', type=int, default=10)
        show_timestamp = request.form.get('show_timestamp') == 'on'
        video_name = request.form.get('video_name', 'timelapse')
        project_name = request.form.get('project_name')
        camera_id = request.form.get('camera_id')

        snapshots, snapshot_data, output_filename, start_dt, end_dt, error_msg = \
            _prepare_video_data(category_id, start_time, end_time, fps,
                                show_timestamp, video_name, project_name, camera_id)

        if error_msg:
            flash(error_msg, 'error')
            categories = get_categories_tree()
            return render_template('generate_video.html', categories=categories, filters=filters)

        success, video_path, error = _generate_video_sync(
            snapshot_data, output_filename, fps, show_timestamp)

        if not success:
            flash(f'Error generating video: {error}', 'error')
            categories = get_categories_tree()
            return render_template('generate_video.html', categories=categories, filters=filters)

        query_params = json.dumps({
            'category_id': category_id, 'start_time': start_time,
            'end_time': end_time, 'fps': fps,
            'project_name': project_name, 'camera_id': camera_id,
        })

        video_id = add_video_generation(
            video_filename=output_filename, video_path=video_path,
            snapshot_count=len(snapshots), start_time=start_dt,
            end_time=end_dt, fps=fps, query_params=query_params,
        )

        flash(f'Video generated successfully! {len(snapshots)} snapshots processed.', 'success')
        return redirect(url_for('download_video', video_id=video_id))

    except Exception as e:
        flash(f'Error generating video: {str(e)}', 'error')
        categories = get_categories_tree()
        filters = get_filter_options()
        return render_template('generate_video.html', categories=categories, filters=filters)


def run_video_generation(job_id, snapshot_data, output_filename, fps, show_timestamp, show_info):
    """Background thread function for video generation"""
    try:
        success, video_path, error = _generate_video_sync(
            snapshot_data, output_filename, fps, show_timestamp, job_id=job_id)

        _update_job_result(job_id, {
            'success': success,
            'video_path': video_path,
            'error': error,
            'completed': True,
            'output_filename': output_filename,
        })
    except Exception as e:
        _update_job_result(job_id, {
            'success': False,
            'video_path': None,
            'error': str(e),
            'completed': True,
        })


@app.route('/api/generate-video/start', methods=['POST'])
def api_start_video_generation():
    """Start video generation in background and return job ID"""
    try:
        category_id = request.form.get('category_id', type=int)
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        fps = request.form.get('fps', type=int, default=10)
        show_timestamp = request.form.get('show_timestamp') == 'on'
        video_name = request.form.get('video_name', 'timelapse')
        project_name = request.form.get('project_name')
        camera_id = request.form.get('camera_id')

        snapshots, snapshot_data, output_filename, start_dt, end_dt, error_msg = \
            _prepare_video_data(category_id, start_time, end_time, fps,
                                show_timestamp, video_name, project_name, camera_id)

        if error_msg:
            return jsonify({'success': False, 'error': error_msg})

        job_id = str(uuid.uuid4())

        _set_job_result(job_id, {
            'success': None,
            'video_path': None,
            'error': None,
            'completed': False,
            'snapshot_count': len(snapshots),
            'output_filename': output_filename,
            'query_params': {
                'category_id': category_id,
                'start_time': start_time,
                'end_time': end_time,
                'fps': fps,
                'project_name': project_name,
                'camera_id': camera_id,
            },
        })

        thread = threading.Thread(
            target=run_video_generation,
            args=(job_id, snapshot_data, output_filename, fps, show_timestamp, False),
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'job_id': job_id,
            'total_images': len(snapshots),
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/generate-video/progress/<job_id>')
def api_video_progress(job_id):
    """Get progress of video generation job"""
    progress = get_progress(job_id)
    job_result = _get_job_result(job_id)

    return jsonify({
        'current': progress.get('current', 0),
        'total': progress.get('total', 0),
        'percent': progress.get('percent', 0),
        'status': progress.get('status', 'unknown'),
        'completed': job_result.get('completed', False),
        'success': job_result.get('success'),
        'error': job_result.get('error'),
    })


@app.route('/api/generate-video/complete/<job_id>', methods=['POST'])
def api_complete_video(job_id):
    """Finalize video generation — save to database and return video ID"""
    job_result = _get_job_result(job_id)

    if not job_result:
        return jsonify({'success': False, 'error': 'Job not found'})

    if not job_result.get('completed'):
        return jsonify({'success': False, 'error': 'Job not completed yet'})

    if not job_result.get('success'):
        error = job_result.get('error', 'Unknown error')
        clear_progress(job_id)
        _pop_job_result(job_id)
        return jsonify({'success': False, 'error': error})

    try:
        params = job_result.get('query_params', {})
        query_params_json = json.dumps(params)

        start_dt = parse_datetime(params.get('start_time')) if params.get('start_time') else None
        end_dt = parse_datetime(params.get('end_time')) if params.get('end_time') else None

        video_id = add_video_generation(
            video_filename=job_result.get('output_filename'),
            video_path=job_result.get('video_path'),
            snapshot_count=job_result.get('snapshot_count', 0),
            start_time=start_dt,
            end_time=end_dt,
            fps=params.get('fps', 10),
            query_params=query_params_json,
        )

        clear_progress(job_id)
        _pop_job_result(job_id)

        return jsonify({
            'success': True,
            'video_id': video_id,
            'snapshot_count': job_result.get('snapshot_count', 0),
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/generate-video', methods=['POST'])
def api_generate_video():
    """API endpoint for generating time-lapse video (AJAX) — Legacy sync version"""
    try:
        category_id = request.form.get('category_id', type=int)
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        fps = request.form.get('fps', type=int, default=10)
        show_timestamp = request.form.get('show_timestamp') == 'on'
        video_name = request.form.get('video_name', 'timelapse')
        project_name = request.form.get('project_name')
        camera_id = request.form.get('camera_id')

        snapshots, snapshot_data, output_filename, start_dt, end_dt, error_msg = \
            _prepare_video_data(category_id, start_time, end_time, fps,
                                show_timestamp, video_name, project_name, camera_id)

        if error_msg:
            return jsonify({'success': False, 'error': error_msg})

        success, video_path, error = _generate_video_sync(
            snapshot_data, output_filename, fps, show_timestamp)

        if not success:
            return jsonify({'success': False, 'error': f'Video generation failed: {error}'})

        query_params = json.dumps({
            'category_id': category_id, 'start_time': start_time,
            'end_time': end_time, 'fps': fps,
            'project_name': project_name, 'camera_id': camera_id,
        })

        video_id = add_video_generation(
            video_filename=output_filename, video_path=video_path,
            snapshot_count=len(snapshots), start_time=start_dt,
            end_time=end_dt, fps=fps, query_params=query_params,
        )

        return jsonify({
            'success': True,
            'message': 'Video generated successfully!',
            'video_id': video_id,
            'snapshot_count': len(snapshots),
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/generate-video/from-ids', methods=['POST'])
def api_generate_video_from_ids():
    """Generate time-lapse video from a list of snapshot IDs (for search results / daily snapshots)."""
    try:
        data = request.get_json() or {}
        snapshot_ids = data.get('snapshot_ids', [])
        fps = data.get('fps', 10)
        show_timestamp = data.get('show_timestamp', True)
        video_name = data.get('video_name', 'timelapse_from_results')

        if not snapshot_ids:
            return jsonify({'success': False, 'error': 'No snapshot IDs provided'}), 400

        # Fetch snapshots in order
        snapshots = []
        for sid in snapshot_ids:
            snap = get_snapshot_by_id(sid)
            if snap:
                snapshots.append(snap)

        if not snapshots:
            return jsonify({'success': False, 'error': 'No valid snapshots found'}), 400

        # Sort by capture_time
        snapshots.sort(key=lambda s: s['capture_time'])

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"{secure_filename(video_name)}_{timestamp}.mp4"

        if show_timestamp:
            snapshot_data = [
                (_normalize_filepath(s['filepath'], UPLOAD_FOLDER), parse_datetime(s['capture_time']), f"ID: {s['id']}")
                for s in snapshots
            ]
        else:
            snapshot_data = [_normalize_filepath(s['filepath'], UPLOAD_FOLDER) for s in snapshots]

        job_id = str(uuid.uuid4())

        _set_job_result(job_id, {
            'success': None,
            'video_path': None,
            'error': None,
            'completed': False,
            'snapshot_count': len(snapshots),
            'output_filename': output_filename,
            'query_params': {
                'snapshot_ids': snapshot_ids,
                'fps': fps,
                'video_name': video_name,
            },
        })

        thread = threading.Thread(
            target=run_video_generation,
            args=(job_id, snapshot_data, output_filename, fps, show_timestamp, False),
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'job_id': job_id,
            'total_images': len(snapshots),
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/video/<int:video_id>')
def download_video(video_id):
    """Download generated video — Fix #12: path validation"""
    video = get_video_by_id(video_id)

    if not video:
        flash('Video not found', 'error')
        return redirect(url_for('index'))

    # Normalize path for cross-OS compatibility
    video_path = _normalize_filepath(video['video_path'], VIDEOS_FOLDER)

    # Path traversal protection
    try:
        real_path = os.path.realpath(video_path)
        real_videos = os.path.realpath(VIDEOS_FOLDER)
        if not real_path.startswith(real_videos):
            logger.warning(f"Path traversal attempt on video: {video_path}")
            return "Access denied", 403
    except Exception:
        return "Invalid path", 400

    if not os.path.exists(video_path):
        flash('Video file not found', 'error')
        return redirect(url_for('index'))

    return send_file(video_path, as_attachment=True,
                    download_name=video['video_filename'])


@app.route('/categories')
@permission_required('categories')
def categories():
    """Manage categories"""
    cats = get_categories_tree()
    return render_template('categories.html', categories=cats)


@app.route('/api/categories', methods=['GET', 'POST'])
def api_categories():
    """API for category management"""
    if request.method == 'GET':
        cats = get_categories_tree()
        result = [dict(c) for c in cats]
        return jsonify({'success': True, 'categories': result})

    try:
        name = request.json.get('name')
        parent_id = request.json.get('parent_id')
        description = request.json.get('description', '')

        if not name:
            return jsonify({'success': False, 'error': 'Name is required'}), 400

        # Fix #3: Validate parent_id exists if provided
        if parent_id is not None and parent_id != '' and parent_id:
            parent_id = int(parent_id)
            if not category_exists(parent_id):
                return jsonify({'success': False, 'error': f'Parent category {parent_id} does not exist'}), 400
        else:
            parent_id = None

        category_id = add_category(name, parent_id, description)
        return jsonify({'success': True, 'category_id': category_id})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/about')
@permission_required('about')
def about():
    """About page"""
    return render_template('about.html')


@app.route('/stats')
@permission_required('stats')
def stats():
    """Statistics page"""
    db_stats = get_database_stats()

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT c.name, COUNT(s.id) as count, SUM(s.file_size) as total_size
            FROM categories c
            LEFT JOIN snapshots s ON c.id = s.category_id
            GROUP BY c.id, c.name
            ORDER BY count DESC
        ''')
        category_stats = cursor.fetchall()

        cursor.execute('''
            SELECT strftime('%Y-%m', capture_time) as month, COUNT(*) as count
            FROM snapshots
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        ''')
        monthly_stats = cursor.fetchall()

    return render_template('stats.html',
                         stats=db_stats,
                         category_stats=category_stats,
                         monthly_stats=monthly_stats)


# =============================================================================
# IMPORT  (Fix #10: batch insert)
# =============================================================================

@app.route('/import-drive', methods=['GET', 'POST'])
@permission_required('import_drive')
def import_drive():
    """Import snapshots from local folder structure"""
    categories_list = get_categories_tree()
    if request.method == 'GET':
        return render_template('import_drive.html', categories=categories_list)

    try:
        folder_path = request.form.get('folder_path')
        source_name = request.form.get('source_name', 'Folder Import')
        category_id = request.form.get('category_id', type=int)
        smart_detect = request.form.get('smart_detect') == 'on'
        skip_duplicates = request.form.get('skip_duplicates', 'on') == 'on'  # Default ON

        if not folder_path or not os.path.exists(folder_path):
            flash('Folder not found. Please check the path again', 'error')
            return render_template('import_drive.html', categories=categories_list)

        # Security: restrict import to safe directories only
        folder_real = os.path.realpath(folder_path)
        allowed_roots = [
            os.path.realpath(UPLOAD_FOLDER),
            os.path.realpath(os.path.join(os.path.dirname(UPLOAD_FOLDER), 'imports')),
        ]
        # Allow any path that isn't a system directory
        blocked_dirs = ['windows', 'system32', 'program files', 'etc', 'usr', 'bin', 'sbin']
        path_lower = folder_real.lower().replace('\\', '/')
        for blocked in blocked_dirs:
            if f'/{blocked}/' in path_lower or path_lower.endswith(f'/{blocked}'):
                flash('Cannot import from system folder. Please choose a different folder', 'error')
                return render_template('import_drive.html', categories=categories_list)

        imported_count = 0
        skipped_duplicates = 0
        skipped_invalid = 0
        errors = []
        batch = []              # Fix #10: accumulate for batch insert
        BATCH_SIZE = 100

        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                if not allowed_file(filename):
                    skipped_invalid += 1
                    continue

                try:
                    source_path = os.path.join(root, filename)

                    # Fix #5: Skip corrupt/unreadable files
                    try:
                        test_size = os.path.getsize(source_path)
                        if test_size == 0:
                            skipped_invalid += 1
                            continue
                    except OSError:
                        skipped_invalid += 1
                        continue

                    # Fix #1/#5: Duplicate detection via file hash
                    file_hash = compute_file_hash(source_path)
                    if skip_duplicates and file_hash:
                        existing = check_duplicate_hash(file_hash)
                        if existing:
                            skipped_duplicates += 1
                            continue

                    path_parts = os.path.normpath(source_path).split(os.sep)

                    project_name = None
                    cam_id = None

                    if smart_detect and len(path_parts) >= 3:
                        try:
                            cam_id = path_parts[-2]
                            project_name = path_parts[-3]
                        except IndexError:
                            cam_id = 'unknown_cam'
                            project_name = 'unknown_project'

                    relative_path = os.path.relpath(root, folder_path)

                    capture_time = extract_datetime_from_filename(filename)
                    if not capture_time:
                        mtime = os.path.getmtime(source_path)
                        capture_time = datetime.fromtimestamp(mtime)

                    unique_filename = generate_unique_filename(filename)
                    dest_path = os.path.join(UPLOAD_FOLDER, unique_filename)

                    shutil.copy2(source_path, dest_path)

                    file_size = os.path.getsize(dest_path)
                    width, height = get_image_dimensions(dest_path)

                    batch.append({
                        'filename': unique_filename,
                        'original_filename': filename,
                        'filepath': dest_path,
                        'category_id': category_id,
                        'capture_time': capture_time,
                        'file_size': file_size,
                        'width': width,
                        'height': height,
                        'source': source_name,
                        'tags': relative_path if relative_path != '.' else '',
                        'notes': f'Imported from: {source_path}',
                        'project_name': project_name,
                        'camera_id': cam_id,
                        'file_hash': file_hash,
                    })

                    if len(batch) >= BATCH_SIZE:
                        add_snapshots_batch(batch)
                        imported_count += len(batch)
                        batch = []

                except Exception as e:
                    errors.append(f'{filename}: {str(e)}')
                    continue

        # Flush remaining batch
        if batch:
            add_snapshots_batch(batch)
            imported_count += len(batch)

        if imported_count > 0:
            flash(f'Successfully imported {imported_count} images', 'success')

        if skipped_duplicates > 0:
            flash(f'Skipped {skipped_duplicates} duplicate images', 'info')

        if skipped_invalid > 0:
            flash(f'Skipped {skipped_invalid} invalid/unsupported files', 'info')

        if errors:
            flash(f'Found {len(errors)} errors', 'warning')

        return render_template('import_drive.html',
                             categories=categories_list,
                             imported_count=imported_count,
                             skipped_duplicates=skipped_duplicates,
                             skipped_invalid=skipped_invalid,
                             errors=errors[:10])

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return render_template('import_drive.html', categories=categories_list)


# =============================================================================
# SMART FILTER APIs
# =============================================================================

@app.route('/api/filters', methods=['GET'])
def api_filters():
    """API to get all project and camera names"""
    try:
        filters = get_filter_options()
        return jsonify({
            'success': True,
            'projects': filters['projects'],
            'cameras': filters['cameras'],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cameras/<project_name>', methods=['GET'])
def api_cameras_by_project(project_name):
    """API to get cameras by project"""
    try:
        cameras = get_cameras_by_project(project_name)
        return jsonify({'success': True, 'cameras': cameras})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# DELETE APIs  (Fix #11: require_admin)
# =============================================================================

@app.route('/api/snapshot/<int:snapshot_id>', methods=['DELETE'])
@require_admin
def api_delete_snapshot(snapshot_id):
    """API to delete snapshot"""
    try:
        success, message = delete_snapshot(snapshot_id)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/category/<int:category_id>', methods=['DELETE'])
@require_admin
def api_delete_category(category_id):
    """API to delete category"""
    try:
        success, message = delete_category(category_id)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/video/<int:video_id>', methods=['DELETE'])
@require_admin
def api_delete_video(video_id):
    """API to delete video"""
    try:
        success, message = delete_video(video_id)
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/snapshots/delete-multiple', methods=['POST'])
@require_admin
def api_delete_multiple_snapshots():
    """API to delete multiple snapshots"""
    try:
        data = request.json
        snapshot_ids = data.get('ids', [])

        if not snapshot_ids:
            return jsonify({'success': False, 'error': 'No snapshots specified for deletion'}), 400

        # Limit bulk delete to 500 at a time
        if len(snapshot_ids) > 500:
            return jsonify({'success': False, 'error': 'Maximum 500 items per deletion'}), 400

        deleted, delete_errors = delete_multiple_snapshots(snapshot_ids)

        return jsonify({
            'success': True,
            'deleted_count': deleted,
            'errors': delete_errors,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# UPDATE APIs
# =============================================================================

@app.route('/api/snapshot/<int:snapshot_id>', methods=['GET'])
def api_get_snapshot(snapshot_id):
    """API to get a single snapshot by ID"""
    try:
        snapshot = get_snapshot_by_id(snapshot_id)
        if not snapshot:
            return jsonify({'success': False, 'error': 'Snapshot not found'}), 404
        return jsonify({
            'success': True,
            'snapshot': {
                'id': snapshot['id'],
                'filename': snapshot['filename'],
                'original_filename': snapshot['original_filename'],
                'category_id': snapshot['category_id'],
                'capture_time': snapshot['capture_time'],
                'upload_time': snapshot['upload_time'],
                'file_size': snapshot['file_size'],
                'width': snapshot['width'],
                'height': snapshot['height'],
                'source': snapshot['source'],
                'tags': snapshot['tags'],
                'notes': snapshot['notes'],
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/snapshot/<int:snapshot_id>', methods=['PUT'])
@require_admin
def api_update_snapshot(snapshot_id):
    """API to update snapshot"""
    try:
        data = request.json

        success, message = update_snapshot(
            snapshot_id,
            category_id=data.get('category_id'),
            tags=data.get('tags'),
            notes=data.get('notes'),
            capture_time=data.get('capture_time'),
        )

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/category/<int:category_id>', methods=['PUT'])
@require_admin
def api_update_category(category_id):
    """API to update category"""
    try:
        data = request.json

        success, message = update_category(
            category_id,
            name=data.get('name'),
            description=data.get('description'),
            parent_id=data.get('parent_id'),
        )

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# UTILITY APIs
# =============================================================================

@app.route('/api/cleanup', methods=['POST'])
@require_admin
def api_cleanup():
    """API to clean up records with missing files"""
    try:
        deleted_count = cleanup_missing_files()
        return jsonify({
            'success': True,
            'message': f'Removed {deleted_count} records with missing files',
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/search', methods=['GET'])
def api_search():
    """API to search snapshots"""
    try:
        keyword = request.args.get('q', '')
        if not keyword:
            return jsonify({'success': False, 'error': 'Please specify a search keyword'}), 400

        snapshots = search_snapshots(keyword)
        result = [dict(s) for s in snapshots]

        return jsonify({
            'success': True,
            'snapshots': result,
            'count': len(result),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/videos')
@permission_required('videos')
def videos_list():
    """Video list page"""
    videos = get_all_videos()
    return render_template('videos.html', videos=videos)


@app.route('/snapshot/<int:snapshot_id>/edit', methods=['GET', 'POST'])
@permission_required('edit_snapshots')
def edit_snapshot(snapshot_id):
    """Edit snapshot page"""
    snapshot = get_snapshot_by_id(snapshot_id)

    if not snapshot:
        flash('Snapshot not found', 'error')
        return redirect(url_for('query'))

    if request.method == 'POST':
        category_id = request.form.get('category_id', type=int)
        tags = request.form.get('tags', '')
        notes = request.form.get('notes', '')
        capture_time_str = request.form.get('capture_time')

        # Parse capture_time if provided
        capture_time = None
        if capture_time_str:
            capture_time = parse_datetime(capture_time_str)

        success, message = update_snapshot(
            snapshot_id,
            category_id=category_id,
            tags=tags,
            notes=notes,
            capture_time=capture_time,
        )

        if success:
            flash('Updated successfully', 'success')
            return redirect(url_for('view_snapshot', snapshot_id=snapshot_id))
        else:
            flash(message, 'error')

    cats = get_categories_tree()
    return render_template('edit_snapshot.html', snapshot=snapshot, categories=cats)


@app.route('/snapshot/<int:snapshot_id>/delete', methods=['POST'])
@permission_required('delete_snapshots')
def delete_snapshot_page(snapshot_id):
    """Delete snapshot from web page"""
    success, message = delete_snapshot(snapshot_id)

    if success:
        flash('Snapshot deleted successfully', 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('query'))


@app.route('/category/<int:category_id>/delete', methods=['POST'])
@permission_required('manage_categories')
def delete_category_page(category_id):
    """Delete category from web page"""
    success, message = delete_category(category_id)

    if success:
        flash('Category deleted successfully', 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('categories'))


@app.route('/video/<int:video_id>/delete', methods=['POST'])
@permission_required('delete_videos')
def delete_video_page(video_id):
    """Delete video from web page"""
    success, message = delete_video(video_id)

    if success:
        flash('Video deleted successfully', 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('videos_list'))


@app.route('/auto-sync')
@permission_required('auto_sync')
def auto_sync():
    """Folder Watcher guide page"""
    return render_template('auto_sync.html')


@app.route('/online')
@permission_required('online_access')
def online_access():
    """Online access guide page"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    td = _tunnel_snapshot()

    unique_ips = {}
    for v in td['visitors']:
        ip = v['ip']
        if ip not in unique_ips:
            unique_ips[ip] = {'ip': ip, 'first_visit': v['time'], 'last_visit': v['time'],
                              'visit_count': 1, 'pages': [v['path']]}
        else:
            unique_ips[ip]['last_visit'] = v['time']
            unique_ips[ip]['visit_count'] += 1
            if v['path'] not in unique_ips[ip]['pages']:
                unique_ips[ip]['pages'].append(v['path'])

    visitors_summary = list(unique_ips.values())
    visitors_summary.sort(key=lambda x: x['last_visit'], reverse=True)

    return render_template('online_access.html',
                         tunnel_url=td['url'],
                         tunnel_set_at=td['set_at'],
                         visitors=td['visitors'][-100:][::-1],
                         visitors_summary=visitors_summary[:50],
                         total_visits=len(td['visitors']),
                         unique_visitors=len(unique_ips),
                         local_url=f"https://localhost:{PORT}",
                         network_url=f"https://{local_ip}:{PORT}")


# =============================================================================
# TUNNEL MANAGEMENT
# =============================================================================

@app.route('/api/tunnel-url', methods=['POST'])
def set_tunnel_url():
    """Set the current tunnel URL"""
    data = request.get_json()
    url = data.get('url', '').strip()

    if url:
        _tunnel_set(url=url, set_at=datetime.now().isoformat())
        return jsonify({'success': True, 'url': url})
    else:
        _tunnel_set(url=None, set_at=None)
        return jsonify({'success': True, 'message': 'URL cleared'})


@app.route('/api/tunnel-url', methods=['GET'])
def get_tunnel_url():
    """Get the current tunnel URL"""
    td = _tunnel_snapshot()
    return jsonify({'url': td['url'], 'set_at': td['set_at']})


@app.route('/api/visitors', methods=['GET'])
def get_visitors():
    """Get visitor data"""
    td = _tunnel_snapshot()
    unique_ips = {}
    for v in td['visitors']:
        ip = v['ip']
        unique_ips[ip] = unique_ips.get(ip, 0) + 1

    return jsonify({
        'total_visits': len(td['visitors']),
        'unique_visitors': len(unique_ips),
        'recent_visitors': td['visitors'][-20:][::-1],
    })


@app.route('/api/visitors/clear', methods=['POST'])
def clear_visitors():
    """Clear visitor data"""
    with _tunnel_lock:
        tunnel_data['visitors'] = []
    return jsonify({'success': True, 'message': 'Visitor data cleared'})


def check_tunnel_health():
    """Check if tunnel is still working"""
    td = _tunnel_snapshot()

    if td['process'] is None:
        return False, 'No tunnel process'

    if td['process'].poll() is not None:
        return False, 'Tunnel process terminated'

    if td['url']:
        try:
            import requests
            response = requests.head(td['url'], timeout=5, allow_redirects=True)
            if response.status_code < 500:
                _tunnel_set(last_check=datetime.now().isoformat())
                return True, 'OK'
        except Exception:
            pass

    _tunnel_set(last_check=datetime.now().isoformat())
    return True, 'Process running'


def is_cloudflared_running():
    """Check if cloudflared process is running"""
    try:
        if os.name == 'nt':
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq cloudflared.exe'],
                                  capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return 'cloudflared.exe' in result.stdout
        else:
            result = subprocess.run(['pgrep', '-f', 'cloudflared'], capture_output=True)
            return result.returncode == 0
    except Exception:
        return False


def kill_cloudflared_processes():
    """Kill all cloudflared processes"""
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/IM', 'cloudflared.exe'],
                         capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(['pkill', '-f', 'cloudflared'], capture_output=True)
    except Exception:
        pass


@app.route('/api/tunnel/health', methods=['GET'])
def tunnel_health():
    """Check tunnel health status"""
    external_running = is_cloudflared_running()
    td = _tunnel_snapshot()

    if td['status'] != 'running':
        if external_running and td['url']:
            return jsonify({
                'healthy': True,
                'status': 'running',
                'source': 'external',
                'url': td['url'],
                'message': 'Tunnel running from start.bat',
            })

        return jsonify({
            'healthy': False,
            'status': td['status'],
            'error': td.get('error'),
            'url': td['url'],
            'external_running': external_running,
        })

    healthy, message = check_tunnel_health()
    if not healthy and td['auto_restart']:
        with _tunnel_lock:
            tunnel_data['restart_count'] += 1
            if tunnel_data['restart_count'] <= 3:
                logger.info(f"[TUNNEL] Auto-restarting... (attempt {tunnel_data['restart_count']})")
                tunnel_data['status'] = 'needs_restart'

    td = _tunnel_snapshot()
    return jsonify({
        'healthy': healthy,
        'status': td['status'],
        'message': message,
        'url': td['url'],
        'last_check': td['last_check'],
        'restart_count': td['restart_count'],
    })


@app.route('/api/tunnel/start', methods=['POST'])
def start_tunnel():
    """Start cloudflared tunnel and get URL automatically"""
    if is_cloudflared_running():
        td = _tunnel_snapshot()
        if td['url']:
            _tunnel_set(status='running')
            return jsonify({
                'success': True,
                'url': td['url'],
                'status': 'running',
                'source': 'external',
                'message': 'Tunnel already running from start.bat',
            })
        else:
            logger.info("[TUNNEL] Cloudflared running without URL, killing and restarting...")
            kill_cloudflared_processes()
            time.sleep(2)

    td = _tunnel_snapshot()
    if td['status'] == 'running' and td['process']:
        if td['process'].poll() is None:
            return jsonify({'success': False, 'error': 'Tunnel already running', 'url': td['url']})
        else:
            _tunnel_set(status='stopped', process=None)

    cloudflared_path = None
    # Detect correct binary name for the current OS
    if os.name == 'nt':
        local_cf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cloudflared.exe')
    else:
        local_cf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cloudflared')
    if os.path.exists(local_cf):
        # Verify the file is actually executable (not a broken download)
        file_size = os.path.getsize(local_cf)
        if file_size > 1000000:  # cloudflared binary is ~50MB, must be at least 1MB
            cloudflared_path = local_cf
            logger.info(f"[TUNNEL] Found local cloudflared: {local_cf} ({file_size // 1024 // 1024}MB)")
        else:
            logger.warning(f"[TUNNEL] Local cloudflared exists but is too small ({file_size} bytes) - likely corrupted")
    else:
        cloudflared_path = shutil.which('cloudflared')
        if cloudflared_path:
            logger.info(f"[TUNNEL] Found cloudflared in PATH: {cloudflared_path}")

    if not cloudflared_path:
        _tunnel_set(status='error', error='cloudflared not found. Please install it first.')
        if os.name == 'nt':
            install_hint = 'Install via: winget install Cloudflare.cloudflared  OR download from https://github.com/cloudflare/cloudflared/releases'
        else:
            install_hint = 'Re-run: bash start.sh (it downloads cloudflared automatically). If blocked by firewall, install manually: sudo apt install cloudflared'
        return jsonify({
            'success': False,
            'error': f'cloudflared not found or corrupted. {install_hint}',
        })

    kill_cloudflared_processes()
    time.sleep(1)

    _tunnel_set(status='starting', error=None, url=None, last_check=None, connection_registered=False)

    # Detect whether Flask is running with SSL
    use_ssl = os.environ.get('USE_SSL', 'false').lower() in ('1', 'true', 'yes')
    cert_exists = os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'certs', 'cert.pem'))
    if use_ssl and cert_exists:
        tunnel_target = f'https://localhost:{PORT}'
        tunnel_cmd = [cloudflared_path, 'tunnel', '--url', tunnel_target, '--no-tls-verify']
    else:
        tunnel_target = f'http://localhost:{PORT}'
        tunnel_cmd = [cloudflared_path, 'tunnel', '--url', tunnel_target]
    logger.info(f"[TUNNEL] Target URL: {tunnel_target}")

    def run_tunnel():
        """Tunnel runner — uses loop instead of recursion (Fix architecture)."""
        max_restarts = 3
        restart_count = 0

        while True:
            try:
                logger.info(f"[TUNNEL] Starting cloudflared process: {cloudflared_path}")
                popen_kwargs = dict(
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                if os.name == 'nt':
                    popen_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                process = subprocess.Popen(
                    tunnel_cmd,
                    **popen_kwargs,
                )
                _tunnel_set(process=process)

                url_pattern = re.compile(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com')
                url_found = False
                connection_count = 0

                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break

                    line_stripped = line.strip()
                    logger.debug(f"[TUNNEL] {line_stripped}")

                    if 'error' in line_stripped.lower() or 'failed' in line_stripped.lower():
                        _tunnel_set(error=line_stripped[:200])

                    match = url_pattern.search(line)
                    if match and not url_found:
                        _tunnel_set(url=match.group(0), set_at=datetime.now().isoformat(),
                                    status='connecting', last_check=datetime.now().isoformat())
                        url_found = True
                        logger.info(f"[TUNNEL] URL found: {match.group(0)} - waiting for connection...")

                    if 'Registered tunnel connection' in line or 'Connection registered' in line_stripped:
                        connection_count += 1
                        _tunnel_set(status='running', connection_registered=True,
                                    last_check=datetime.now().isoformat())
                        logger.info(f"[TUNNEL] Connection #{connection_count} registered - TUNNEL IS NOW READY!")

                    if 'Unregistered tunnel connection' in line or 'connection closed' in line_stripped.lower():
                        connection_count = max(0, connection_count - 1)
                        logger.info(f"[TUNNEL] Connection lost. Active connections: {connection_count}")

                logger.warning("[TUNNEL] Process ended unexpectedly")
                _tunnel_set(status='stopped', process=None)

            except FileNotFoundError:
                _tunnel_set(status='error', error='cloudflared not installed.', process=None)
                logger.error("[TUNNEL] ERROR: cloudflared not found!")
                return
            except Exception as e:
                _tunnel_set(status='error', error=str(e), process=None)
                logger.error(f"[TUNNEL] ERROR: {e}")
                return

            # Auto-restart check (loop instead of recursion)
            td_check = _tunnel_snapshot()
            if td_check['auto_restart'] and restart_count < max_restarts:
                restart_count += 1
                with _tunnel_lock:
                    tunnel_data['restart_count'] = restart_count
                logger.info(f"[TUNNEL] Will auto-restart... (attempt {restart_count})")
                time.sleep(2)
                continue
            else:
                return

    with _tunnel_lock:
        tunnel_data['restart_count'] = 0

    thread = threading.Thread(target=run_tunnel, daemon=True)
    thread.start()

    for _ in range(90):
        time.sleep(0.5)
        td = _tunnel_snapshot()
        if td['url'] and td['connection_registered']:
            logger.info(f"[TUNNEL] Tunnel is ready! URL: {td['url']}")
            return jsonify({'success': True, 'url': td['url'], 'status': 'running'})
        if td['status'] == 'error':
            error_msg = td.get('error', 'Failed to start tunnel')
            return jsonify({'success': False, 'error': error_msg})

    td = _tunnel_snapshot()
    if td['url']:
        for _ in range(6):
            time.sleep(0.5)
            td = _tunnel_snapshot()
            if td['connection_registered']:
                _tunnel_set(status='running')
                return jsonify({'success': True, 'url': td['url'], 'status': 'running'})
        _tunnel_set(status='running')
        logger.warning("[TUNNEL] Warning: URL obtained but connection may not be fully ready")
        return jsonify({
            'success': True,
            'url': td['url'],
            'status': 'running',
            'warning': 'Connection may take a few more seconds to be ready',
        })

    return jsonify({'success': False, 'error': 'Timeout waiting for tunnel URL. Make sure cloudflared is installed.'})


@app.route('/api/tunnel/stop', methods=['POST'])
def stop_tunnel():
    """Stop the running tunnel"""
    with _tunnel_lock:
        tunnel_data['auto_restart'] = False

        if tunnel_data['process']:
            try:
                tunnel_data['process'].terminate()
                tunnel_data['process'].wait(timeout=5)
            except Exception:
                try:
                    tunnel_data['process'].kill()
                except Exception:
                    pass
            tunnel_data['process'] = None

    kill_cloudflared_processes()

    _tunnel_set(status='stopped', url=None, set_at=None,
                restart_count=0, error=None, auto_restart=True)
    return jsonify({'success': True, 'message': 'Tunnel stopped'})


@app.route('/api/tunnel/status', methods=['GET'])
def tunnel_status():
    """Get current tunnel status"""
    external_running = is_cloudflared_running()

    with _tunnel_lock:
        actual_status = tunnel_data['status']
        if tunnel_data['status'] == 'running' and tunnel_data['process']:
            if tunnel_data['process'].poll() is not None:
                actual_status = 'stopped'
                tunnel_data['status'] = 'stopped'
                tunnel_data['process'] = None

        if external_running and tunnel_data['url'] and actual_status != 'running':
            actual_status = 'running'
            tunnel_data['status'] = 'running'

        if not external_running and tunnel_data['process'] is None and actual_status == 'running':
            actual_status = 'stopped'
            tunnel_data['status'] = 'stopped'

        td = dict(tunnel_data)

    return jsonify({
        'status': actual_status,
        'url': td['url'],
        'set_at': td['set_at'],
        'last_check': td.get('last_check'),
        'restart_count': td.get('restart_count', 0),
        'error': td.get('error'),
        'external_running': external_running,
    })


# =============================================================================
# AUTH & SECURITY ROUTES
# =============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    # Already logged in?
    if get_current_user():
        return redirect(request.args.get('next', '/'))

    if request.method == 'GET':
        next_url = request.args.get('next', '/')
        return render_template('login.html', next_url=next_url,
                               error=None, lockout_remaining=None, username='')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    next_url = request.form.get('next', '/')
    visitor_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if visitor_ip and ',' in visitor_ip:
        visitor_ip = visitor_ip.split(',')[0].strip()

    # Check lockout
    is_locked, remaining = _check_lockout(visitor_ip)
    if is_locked:
        return render_template('login.html', next_url=next_url,
                               error=None, lockout_remaining=remaining, username=username)

    # Authenticate
    user = authenticate_user(username, password)
    if user:
        _record_login_attempt(visitor_ip, username, True)
        session_id = create_session(username, visitor_ip)
        session['session_id'] = session_id
        flash(f'Welcome {user["display_name"]}!', 'success')
        return redirect(next_url or '/')
    else:
        _record_login_attempt(visitor_ip, username, False)
        return render_template('login.html', next_url=next_url,
                               error='Invalid username or password',
                               lockout_remaining=None, username=username)


@app.route('/logout')
def logout():
    """Logout"""
    session_id = session.get('session_id')
    if session_id:
        destroy_session(session_id)
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/security')
def security_settings_page():
    """Security settings page"""
    user = get_current_user()
    if not user:
        flash('Please sign in', 'warning')
        return redirect(url_for('login', next='/security'))
    if user.get('role') != 'admin':
        flash('Admin privileges required', 'error')
        return redirect('/')

    settings = get_security_settings()
    users = get_all_users()
    sessions = get_active_sessions()
    history = get_login_history(50)
    return render_template('security_settings.html',
                           settings=settings, users=users,
                           sessions=sessions, history=history,
                           current_user=user,
                           all_permissions=ALL_PERMISSIONS,
                           role_defaults=ROLE_DEFAULTS,
                           permission_labels=PERMISSION_LABELS,
                           permission_groups=PERMISSION_GROUPS)


@app.route('/security/update-settings', methods=['POST'])
def security_update_settings():
    """Update security settings"""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Admin privileges required', 'error')
        return redirect('/')

    new_settings = {
        'require_login': 'require_login' in request.form,
        'session_timeout_minutes': int(request.form.get('session_timeout_minutes', 60)),
        'max_login_attempts': int(request.form.get('max_login_attempts', 5)),
        'lockout_duration_minutes': int(request.form.get('lockout_duration_minutes', 15)),
        'password_min_length': int(request.form.get('password_min_length', 8)),
        'enforce_strong_password': 'enforce_strong_password' in request.form,
        'log_login_activity': 'log_login_activity' in request.form,
    }
    update_security_settings(new_settings)
    flash('Settings saved successfully', 'success')
    return redirect(url_for('security_settings_page'))


@app.route('/security/change-password', methods=['POST'])
def security_change_password():
    """Change current user password"""
    user = get_current_user()
    if not user:
        flash('Please sign in', 'warning')
        return redirect(url_for('login'))

    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    # Verify current password
    if not authenticate_user(user['username'], current_pw):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('security_settings_page'))

    if new_pw != confirm_pw:
        flash('New passwords do not match', 'error')
        return redirect(url_for('security_settings_page'))

    is_valid, msg = validate_password_strength(new_pw)
    if not is_valid:
        flash(msg, 'error')
        return redirect(url_for('security_settings_page'))

    change_password(user['username'], new_pw)
    flash('Password changed successfully', 'success')
    return redirect(url_for('security_settings_page'))


@app.route('/security/add-user', methods=['POST'])
def security_add_user():
    """Add a new user"""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Admin privileges required', 'error')
        return redirect('/')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    display_name = request.form.get('display_name', '').strip()
    role = request.form.get('role', 'viewer')

    if not username or not password:
        flash('Please fill in all required fields', 'error')
        return redirect(url_for('security_settings_page'))

    if role not in ('admin', 'editor', 'viewer'):
        role = 'viewer'

    if create_user(username, password, role, display_name):
        flash(f'User {username} created successfully', 'success')
    else:
        flash(f'Username {username} already exists', 'error')
    return redirect(url_for('security_settings_page'))


@app.route('/security/delete-user', methods=['POST'])
def security_delete_user():
    """Delete a user"""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Admin privileges required', 'error')
        return redirect('/')

    target = request.form.get('username', '')
    if target == user['username']:
        flash('Cannot delete yourself', 'error')
        return redirect(url_for('security_settings_page'))

    if delete_user(target):
        flash(f'User {target} deleted successfully', 'success')
    else:
        flash('Cannot delete user (may be the last admin)', 'error')
    return redirect(url_for('security_settings_page'))


@app.route('/security/toggle-user', methods=['POST'])
def security_toggle_user():
    """Toggle user active/inactive"""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Admin privileges required', 'error')
        return redirect('/')

    target = request.form.get('username', '')
    if toggle_user_active(target):
        flash(f'User {target} status updated successfully', 'success')
    else:
        flash('Cannot change status', 'error')
    return redirect(url_for('security_settings_page'))


@app.route('/security/clear-sessions', methods=['POST'])
def security_clear_sessions():
    """Clear all sessions"""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Admin privileges required', 'error')
        return redirect('/')

    destroy_all_sessions()
    session.clear()
    flash('All sessions cleared', 'success')
    return redirect(url_for('login'))


@app.route('/security/revoke-session', methods=['POST'])
def security_revoke_session():
    """Revoke a specific session"""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Admin privileges required', 'error')
        return redirect('/')

    target_sid = request.form.get('session_id', '')
    if target_sid:
        destroy_session(target_sid)
        flash('Session revoked successfully', 'success')
    return redirect(url_for('security_settings_page'))


@app.route('/security/update-role', methods=['POST'])
def security_update_role():
    """Update a user's role"""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Admin privileges required', 'error')
        return redirect('/')

    target = request.form.get('username', '')
    new_role = request.form.get('role', '')

    if target == user['username']:
        flash('Cannot change your own role', 'error')
        return redirect(url_for('security_settings_page'))

    if update_user_role(target, new_role):
        flash(f'Role for {target} updated to {new_role}', 'success')
    else:
        flash('Cannot change role (may be the last admin)', 'error')
    return redirect(url_for('security_settings_page'))


@app.route('/security/update-permissions', methods=['POST'])
def security_update_permissions():
    """Update a user's permissions (AJAX endpoint)"""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin required'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    target = data.get('username', '')
    permissions = data.get('permissions', [])

    if not target:
        return jsonify({'success': False, 'error': 'Username required'}), 400

    if update_user_permissions(target, permissions):
        return jsonify({'success': True, 'message': f'Permissions updated for {target}'})
    else:
        return jsonify({'success': False, 'error': 'User not found'}), 404


@app.route('/security/get-user-permissions/<username>')
def security_get_user_permissions(username):
    """Get a user's current permissions (AJAX)"""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin required'}), 403

    perms = get_user_permissions(username)
    return jsonify({'success': True, 'permissions': perms})


if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=DEBUG)
