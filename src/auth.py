"""
Authentication & Security Module
=================================
Provides user login/logout, session management, password hashing,
and security settings (change password, manage sessions, 2FA toggle).
"""

import os
import json
import secrets
import hashlib
import time
import threading
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    session, request, redirect, url_for, flash, abort, jsonify
)

from src.logger import get_logger
from src.config import DATABASE_PATH

logger = get_logger('auth')


# =============================================================================
# ROLE & PERMISSION DEFINITIONS
# =============================================================================

# All permissions available in the system
ALL_PERMISSIONS = [
    'dashboard',         # View dashboard
    'upload',            # Upload snapshots
    'search',            # Search/query snapshots
    'view_snapshots',    # View snapshot details
    'edit_snapshots',    # Edit snapshot metadata
    'delete_snapshots',  # Delete snapshots
    'categories',        # View categories
    'manage_categories', # Add/delete categories
    'generate_video',    # Generate time-lapse videos
    'videos',            # View videos list
    'delete_videos',     # Delete videos
    'import_drive',      # Import from drive/folder
    'daily_snapshots',   # Daily snapshot search
    'stats',             # View statistics
    'online_access',     # Manage online access/tunnel
    'auto_sync',         # View auto-sync info
    'about',             # View about page
    'security',          # Access security settings
]

# Default permissions per role
ROLE_DEFAULTS = {
    'admin': ALL_PERMISSIONS.copy(),
    'editor': [
        'dashboard', 'upload', 'search', 'view_snapshots',
        'edit_snapshots', 'delete_snapshots',
        'categories', 'manage_categories',
        'generate_video', 'videos', 'delete_videos',
        'import_drive', 'daily_snapshots', 'stats',
        'auto_sync', 'about',
    ],
    'viewer': [
        'dashboard', 'search', 'view_snapshots',
        'categories', 'videos', 'daily_snapshots',
        'stats', 'about',
    ],
}

# Human-readable labels for permissions
PERMISSION_LABELS = {
    'dashboard':        'View Dashboard',
    'upload':           'Upload Snapshots',
    'search':           'Search Snapshots',
    'view_snapshots':   'View Snapshot Details',
    'edit_snapshots':   'Edit Snapshots',
    'delete_snapshots': 'Delete Snapshots',
    'categories':       'View Categories',
    'manage_categories':'Manage Categories',
    'generate_video':   'Generate Videos',
    'videos':           'View Videos',
    'delete_videos':    'Delete Videos',
    'import_drive':     'Import from Drive',
    'daily_snapshots':  'Daily Snapshot Search',
    'stats':            'View Statistics',
    'online_access':    'Online Access Settings',
    'auto_sync':        'Auto-Sync Settings',
    'about':            'View About Page',
    'security':         'Security Settings',
}

# Group permissions for UI display
PERMISSION_GROUPS = {
    'Snapshots': ['dashboard', 'upload', 'search', 'view_snapshots', 'edit_snapshots', 'delete_snapshots', 'daily_snapshots'],
    'Organization': ['categories', 'manage_categories', 'import_drive'],
    'Videos': ['generate_video', 'videos', 'delete_videos'],
    'System': ['stats', 'online_access', 'auto_sync', 'about', 'security'],
}

# ---------- Constants ----------
AUTH_DB_FILE = os.path.join(os.path.dirname(DATABASE_PATH), 'auth.json')
SESSION_TIMEOUT_MINUTES = int(os.getenv('SESSION_TIMEOUT', '60'))
MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', '5'))
LOCKOUT_DURATION_MINUTES = int(os.getenv('LOCKOUT_DURATION', '15'))

_auth_lock = threading.Lock()


# =============================================================================
# PASSWORD HASHING (using hashlib — no extra dependency)
# =============================================================================

def _hash_password(password: str, salt: str = None) -> tuple:
    """Hash a password with PBKDF2-HMAC-SHA256. Returns (hash_hex, salt_hex)."""
    if salt is None:
        salt = secrets.token_hex(32)
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations=100_000,
    )
    return pw_hash.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a password against stored hash."""
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations=100_000,
    )
    return secrets.compare_digest(pw_hash.hex(), stored_hash)


# =============================================================================
# AUTH DATA PERSISTENCE (JSON file)
# =============================================================================

def _get_permissions_for_role(role: str) -> list:
    """Get default permissions for a role."""
    return ROLE_DEFAULTS.get(role, ROLE_DEFAULTS['viewer']).copy()


def _default_auth_data() -> dict:
    """Return default auth data with admin user."""
    pw_hash, salt = _hash_password('admin')
    return {
        'users': {
            'admin': {
                'password_hash': pw_hash,
                'salt': salt,
                'role': 'admin',
                'display_name': 'Administrator',
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'is_active': True,
                'require_2fa': False,
                'permissions': ALL_PERMISSIONS.copy(),
            }
        },
        'security_settings': {
            'require_login': True,           # Require login for all pages
            'session_timeout_minutes': SESSION_TIMEOUT_MINUTES,
            'max_login_attempts': MAX_LOGIN_ATTEMPTS,
            'lockout_duration_minutes': LOCKOUT_DURATION_MINUTES,
            'password_min_length': 8,
            'enforce_strong_password': True,
            'log_login_activity': True,
            'allowed_ips': [],               # Empty = allow all
        },
        'login_attempts': {},                # {ip: {count, last_attempt}}
        'active_sessions': {},               # {session_id: {user, ip, created, last_active}}
        'login_history': [],                 # [{user, ip, time, success}]
    }


def _load_auth_data() -> dict:
    """Load auth data from JSON file."""
    with _auth_lock:
        if not os.path.exists(AUTH_DB_FILE):
            data = _default_auth_data()
            _save_auth_data_unsafe(data)
            return data
        try:
            with open(AUTH_DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Ensure all keys exist (migration-safe)
            defaults = _default_auth_data()
            for key in defaults:
                if key not in data:
                    data[key] = defaults[key]
            for key in defaults['security_settings']:
                if key not in data.get('security_settings', {}):
                    data['security_settings'][key] = defaults['security_settings'][key]
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load auth data: {e}")
            return _default_auth_data()


def _save_auth_data(data: dict):
    """Save auth data to JSON file (thread-safe)."""
    with _auth_lock:
        _save_auth_data_unsafe(data)


def _save_auth_data_unsafe(data: dict):
    """Save auth data — must be called within _auth_lock."""
    try:
        os.makedirs(os.path.dirname(AUTH_DB_FILE) or '.', exist_ok=True)
        with open(AUTH_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Failed to save auth data: {e}")


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

def create_session(username: str, ip: str) -> str:
    """Create a new session for the user. Returns session_id."""
    session_id = secrets.token_hex(32)
    data = _load_auth_data()
    data['active_sessions'][session_id] = {
        'user': username,
        'ip': ip,
        'created': datetime.now().isoformat(),
        'last_active': datetime.now().isoformat(),
        'user_agent': request.headers.get('User-Agent', '')[:200],
    }
    # Update last login
    if username in data['users']:
        data['users'][username]['last_login'] = datetime.now().isoformat()
    _save_auth_data(data)
    return session_id


def validate_session(session_id: str) -> dict | None:
    """Validate session and return user info, or None if invalid."""
    if not session_id:
        return None
    data = _load_auth_data()
    sess = data.get('active_sessions', {}).get(session_id)
    if not sess:
        return None

    # Check timeout
    timeout = data['security_settings'].get('session_timeout_minutes', SESSION_TIMEOUT_MINUTES)
    last_active = datetime.fromisoformat(sess['last_active'])
    if datetime.now() - last_active > timedelta(minutes=timeout):
        # Session expired
        del data['active_sessions'][session_id]
        _save_auth_data(data)
        return None

    # Update last active
    sess['last_active'] = datetime.now().isoformat()
    _save_auth_data(data)

    user = data['users'].get(sess['user'])
    if not user or not user.get('is_active', True):
        return None

    # Get permissions — admin always gets all
    role = user.get('role', 'viewer')
    if role == 'admin':
        perms = ALL_PERMISSIONS.copy()
    else:
        perms = user.get('permissions', _get_permissions_for_role(role))

    return {
        'username': sess['user'],
        'role': role,
        'display_name': user.get('display_name', sess['user']),
        'permissions': perms,
    }


def destroy_session(session_id: str):
    """Remove a session."""
    data = _load_auth_data()
    data['active_sessions'].pop(session_id, None)
    _save_auth_data(data)


def destroy_all_sessions(username: str = None):
    """Remove all sessions, optionally for a specific user."""
    data = _load_auth_data()
    if username:
        data['active_sessions'] = {
            k: v for k, v in data['active_sessions'].items()
            if v.get('user') != username
        }
    else:
        data['active_sessions'] = {}
    _save_auth_data(data)


# =============================================================================
# LOGIN ATTEMPT TRACKING
# =============================================================================

def _check_lockout(ip: str) -> tuple:
    """Check if an IP is locked out. Returns (is_locked, remaining_seconds)."""
    data = _load_auth_data()
    settings = data['security_settings']
    attempts = data.get('login_attempts', {}).get(ip)
    if not attempts:
        return False, 0

    max_attempts = settings.get('max_login_attempts', MAX_LOGIN_ATTEMPTS)
    lockout_minutes = settings.get('lockout_duration_minutes', LOCKOUT_DURATION_MINUTES)

    if attempts['count'] >= max_attempts:
        last = datetime.fromisoformat(attempts['last_attempt'])
        lockout_end = last + timedelta(minutes=lockout_minutes)
        if datetime.now() < lockout_end:
            remaining = (lockout_end - datetime.now()).total_seconds()
            return True, int(remaining)
        else:
            # Lockout expired, reset
            data['login_attempts'].pop(ip, None)
            _save_auth_data(data)
            return False, 0
    return False, 0


def _record_login_attempt(ip: str, username: str, success: bool):
    """Record a login attempt."""
    data = _load_auth_data()

    # Record in history
    if data['security_settings'].get('log_login_activity', True):
        data.setdefault('login_history', [])
        data['login_history'].append({
            'user': username,
            'ip': ip,
            'time': datetime.now().isoformat(),
            'success': success,
            'user_agent': request.headers.get('User-Agent', '')[:200],
        })
        # Keep last 500 entries
        data['login_history'] = data['login_history'][-500:]

    if success:
        data.get('login_attempts', {}).pop(ip, None)
    else:
        attempts = data.setdefault('login_attempts', {}).get(ip, {'count': 0, 'last_attempt': None})
        attempts['count'] = attempts.get('count', 0) + 1
        attempts['last_attempt'] = datetime.now().isoformat()
        data['login_attempts'][ip] = attempts

    _save_auth_data(data)


# =============================================================================
# USER MANAGEMENT
# =============================================================================

def authenticate_user(username: str, password: str) -> dict | None:
    """Authenticate a user. Returns user dict or None."""
    data = _load_auth_data()
    user = data['users'].get(username)
    if not user:
        return None
    if not user.get('is_active', True):
        return None
    if _verify_password(password, user['password_hash'], user['salt']):
        role = user.get('role', 'viewer')
        if role == 'admin':
            perms = ALL_PERMISSIONS.copy()
        else:
            perms = user.get('permissions', _get_permissions_for_role(role))
        return {
            'username': username,
            'role': role,
            'display_name': user.get('display_name', username),
            'permissions': perms,
        }
    return None


def change_password(username: str, new_password: str) -> bool:
    """Change user password."""
    data = _load_auth_data()
    if username not in data['users']:
        return False
    pw_hash, salt = _hash_password(new_password)
    data['users'][username]['password_hash'] = pw_hash
    data['users'][username]['salt'] = salt
    _save_auth_data(data)
    logger.info(f"Password changed for user: {username}")
    return True


def create_user(username: str, password: str, role: str = 'viewer',
                display_name: str = '', permissions: list = None) -> bool:
    """Create a new user with role and permissions."""
    data = _load_auth_data()
    if username in data['users']:
        return False
    if role not in ROLE_DEFAULTS:
        role = 'viewer'
    pw_hash, salt = _hash_password(password)
    user_perms = permissions if permissions is not None else _get_permissions_for_role(role)
    data['users'][username] = {
        'password_hash': pw_hash,
        'salt': salt,
        'role': role,
        'display_name': display_name or username,
        'created_at': datetime.now().isoformat(),
        'last_login': None,
        'is_active': True,
        'require_2fa': False,
        'permissions': user_perms,
    }
    _save_auth_data(data)
    logger.info(f"User created: {username} (role: {role})")
    return True


def delete_user(username: str) -> bool:
    """Delete a user (cannot delete last admin)."""
    data = _load_auth_data()
    if username not in data['users']:
        return False
    # Don't delete the last admin
    admin_count = sum(1 for u in data['users'].values() if u.get('role') == 'admin' and u.get('is_active'))
    if data['users'][username].get('role') == 'admin' and admin_count <= 1:
        return False
    del data['users'][username]
    # Also destroy their sessions
    data['active_sessions'] = {
        k: v for k, v in data['active_sessions'].items()
        if v.get('user') != username
    }
    _save_auth_data(data)
    logger.info(f"User deleted: {username}")
    return True


def toggle_user_active(username: str) -> bool:
    """Toggle user active status."""
    data = _load_auth_data()
    if username not in data['users']:
        return False
    user = data['users'][username]
    # Don't deactivate the last admin
    if user.get('role') == 'admin' and user.get('is_active', True):
        admin_count = sum(1 for u in data['users'].values()
                         if u.get('role') == 'admin' and u.get('is_active'))
        if admin_count <= 1:
            return False
    user['is_active'] = not user.get('is_active', True)
    if not user['is_active']:
        # Destroy sessions for deactivated user
        data['active_sessions'] = {
            k: v for k, v in data['active_sessions'].items()
            if v.get('user') != username
        }
    _save_auth_data(data)
    return True


def get_all_users() -> list:
    """Get all users (without sensitive data)."""
    data = _load_auth_data()
    users = []
    for uname, udata in data['users'].items():
        role = udata.get('role', 'viewer')
        perms = udata.get('permissions', _get_permissions_for_role(role))
        users.append({
            'username': uname,
            'role': role,
            'display_name': udata.get('display_name', uname),
            'created_at': udata.get('created_at'),
            'last_login': udata.get('last_login'),
            'is_active': udata.get('is_active', True),
            'permissions': perms,
        })
    return users


def update_user_permissions(username: str, permissions: list) -> bool:
    """Update permissions for a user."""
    data = _load_auth_data()
    if username not in data['users']:
        return False
    # Admin always keeps all permissions
    if data['users'][username].get('role') == 'admin':
        data['users'][username]['permissions'] = ALL_PERMISSIONS.copy()
    else:
        # Only allow valid permissions
        valid = [p for p in permissions if p in ALL_PERMISSIONS]
        data['users'][username]['permissions'] = valid
    _save_auth_data(data)
    logger.info(f"Permissions updated for user: {username}")
    return True


def update_user_role(username: str, new_role: str) -> bool:
    """Update the role of a user and reset to role defaults."""
    data = _load_auth_data()
    if username not in data['users']:
        return False
    if new_role not in ROLE_DEFAULTS:
        return False
    # Don't demote the last admin
    user = data['users'][username]
    if user.get('role') == 'admin' and new_role != 'admin':
        admin_count = sum(1 for u in data['users'].values()
                         if u.get('role') == 'admin' and u.get('is_active'))
        if admin_count <= 1:
            return False
    data['users'][username]['role'] = new_role
    data['users'][username]['permissions'] = _get_permissions_for_role(new_role)
    _save_auth_data(data)
    logger.info(f"Role changed for {username}: {new_role}")
    return True


def get_user_permissions(username: str) -> list:
    """Get permissions for a specific user."""
    data = _load_auth_data()
    user = data['users'].get(username)
    if not user:
        return []
    if user.get('role') == 'admin':
        return ALL_PERMISSIONS.copy()
    return user.get('permissions', _get_permissions_for_role(user.get('role', 'viewer')))


def get_security_settings() -> dict:
    """Get current security settings."""
    data = _load_auth_data()
    return data.get('security_settings', {})


def update_security_settings(new_settings: dict) -> bool:
    """Update security settings."""
    data = _load_auth_data()
    allowed_keys = {
        'require_login', 'session_timeout_minutes', 'max_login_attempts',
        'lockout_duration_minutes', 'password_min_length',
        'enforce_strong_password', 'log_login_activity', 'allowed_ips',
    }
    for key, value in new_settings.items():
        if key in allowed_keys:
            data['security_settings'][key] = value
    _save_auth_data(data)
    logger.info(f"Security settings updated: {list(new_settings.keys())}")
    return True


def get_login_history(limit: int = 50) -> list:
    """Get recent login history."""
    data = _load_auth_data()
    history = data.get('login_history', [])
    return list(reversed(history[-limit:]))


def get_active_sessions() -> list:
    """Get all active sessions."""
    data = _load_auth_data()
    sessions = []
    for sid, sdata in data.get('active_sessions', {}).items():
        sessions.append({
            'session_id': sid[:8] + '...',  # Truncated for display
            'full_id': sid,
            'user': sdata.get('user'),
            'ip': sdata.get('ip'),
            'created': sdata.get('created'),
            'last_active': sdata.get('last_active'),
            'user_agent': sdata.get('user_agent', ''),
        })
    return sessions


def validate_password_strength(password: str) -> tuple:
    """Validate password strength. Returns (is_valid, message)."""
    data = _load_auth_data()
    settings = data.get('security_settings', {})
    min_len = settings.get('password_min_length', 8)

    if len(password) < min_len:
        return False, f'Password must be at least {min_len} characters'

    if settings.get('enforce_strong_password', True):
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)

        if not (has_upper and has_lower and has_digit):
            return False, 'Password must contain uppercase, lowercase, and numbers'

    return True, 'OK'


# =============================================================================
# FLASK DECORATORS
# =============================================================================

def login_required(f):
    """Decorator: always require login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        session_id = session.get('session_id')
        user = validate_session(session_id)
        if not user:
            session.clear()
            flash('Please sign in', 'warning')
            return redirect(url_for('login', next=request.path))
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: require admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        session_id = session.get('session_id')
        user = validate_session(session_id)
        if not user:
            flash('Please sign in', 'warning')
            return redirect(url_for('login', next=request.path))
        if user.get('role') != 'admin':
            flash('Admin privileges required', 'error')
            return redirect(url_for('index'))
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def permission_required(permission: str):
    """Decorator: require a specific permission.

    Usage:
        @app.route('/upload')
        @permission_required('upload')
        def upload():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            session_id = session.get('session_id')
            user = validate_session(session_id)
            if not user:
                session.clear()
                if request.path.startswith('/api/'):
                    return jsonify({'success': False, 'error': 'Authentication required'}), 401
                flash('Please sign in', 'warning')
                return redirect(url_for('login', next=request.path))
            # Admin always has access
            if user.get('role') == 'admin':
                request.current_user = user
                return f(*args, **kwargs)
            # Check specific permission
            user_perms = user.get('permissions', [])
            if permission not in user_perms:
                if request.path.startswith('/api/'):
                    return jsonify({'success': False, 'error': 'Permission denied'}), 403
                flash('You do not have permission to access this page', 'error')
                return redirect(url_for('index'))
            request.current_user = user
            return f(*args, **kwargs)
        return decorated
    return decorator


def has_permission(user: dict, permission: str) -> bool:
    """Check if a user dict has a specific permission."""
    if not user:
        return False
    if user.get('role') == 'admin':
        return True
    return permission in user.get('permissions', [])


def get_current_user() -> dict | None:
    """Get the currently logged-in user, or None."""
    session_id = session.get('session_id')
    if not session_id:
        return None
    return validate_session(session_id)
