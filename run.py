"""
Main entry point for running the Aeroponic Snapshot Database application.
Run this file to start the Flask server.

Usage:
    python run.py

This script will:
1. Setup paths and configuration
2. Create required directories
3. Setup logging
4. Start the Flask server
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.paths import ProjectPaths
from src.logger import get_logger
from src.config import HOST, PORT, DEBUG

# Initialize paths and directories
try:
    ProjectPaths.create_required_dirs()
    ProjectPaths.verify_structure()
except RuntimeError as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# Setup logger
logger = get_logger('app')

# Import app
try:
    from src.app import app
except ImportError as e:
    logger.error(f"Failed to import app: {e}")
    print(f"❌ Failed to import Flask app: {e}")
    sys.exit(1)

if __name__ == '__main__':
    # SSL/TLS support
    ssl_context = None
    cert_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'certs', 'cert.pem')
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'certs', 'key.pem')
    use_ssl = os.environ.get('USE_SSL', 'false').lower() in ('1', 'true', 'yes')

    if use_ssl and os.path.exists(cert_file) and os.path.exists(key_file):
        ssl_context = (cert_file, key_file)
        protocol = "https"
        print(f"🔒 SSL/TLS ENABLED — using certs from certs/")
    else:
        protocol = "http"
        if use_ssl:
            print("⚠️  USE_SSL=true but certs not found in certs/ — running without SSL")

    print("=" * 60)
    print("🌱 Aeroponic Snapshot Database")
    print("=" * 60)
    print(f"📁 Project Root: {ProjectPaths.ROOT}")
    print(f"📁 Snapshots: {ProjectPaths.SNAPSHOTS}")
    print(f"📁 Videos: {ProjectPaths.VIDEOS}")
    print(f"📁 Logs: {ProjectPaths.LOGS}")
    print(f"🗄️  Database: {ProjectPaths.DATABASE}")
    print("=" * 60)
    print(f"🌐 Starting server at {protocol}://{HOST}:{PORT}")
    print("📝 Press Ctrl+C to stop the server")
    print("=" * 60)
    
    logger.info("=" * 60)
    logger.info(f"Starting Aeroponic Snapshot Database Server")
    logger.info(f"Host: {HOST}, Port: {PORT}, Debug: {DEBUG}")
    logger.info("=" * 60)
    
    # Check if AUTO_START_TUNNEL is set
    auto_start_tunnel = os.environ.get('AUTO_START_TUNNEL', '').lower() in ('1', 'true', 'yes')
    
    if auto_start_tunnel:
        print("=" * 60)
        print("🌐 AUTO ONLINE ACCESS ENABLED")
        print("   Tunnel will start automatically after server is ready...")
        print("=" * 60)
        
        import threading
        import time
        import urllib.request
        import json
        
        def start_tunnel_after_delay():
            """Wait for server to be ready then start tunnel"""
            time.sleep(3)  # Wait for Flask to fully start
            try:
                # Start tunnel via API using urllib (built-in)
                url = f'http://127.0.0.1:{PORT}/api/tunnel/start'
                req = urllib.request.Request(url, method='POST', data=b'')
                req.add_header('Content-Type', 'application/json')
                
                with urllib.request.urlopen(req, timeout=90) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    
                if data.get('success') and data.get('url'):
                    print("")
                    print("=" * 60)
                    print("🎉 ONLINE ACCESS READY!")
                    print(f"🔗 Share URL: {data['url']}")
                    print("=" * 60)
                    print("")
                    logger.info(f"Tunnel started: {data['url']}")
                else:
                    error = data.get('error', 'Unknown error')
                    print(f"⚠️  Tunnel start issue: {error}")
                    logger.warning(f"Tunnel start issue: {error}")
            except Exception as e:
                print(f"⚠️  Could not auto-start tunnel: {e}")
                logger.warning(f"Could not auto-start tunnel: {e}")
        
        # Start tunnel in background thread
        tunnel_thread = threading.Thread(target=start_tunnel_after_delay, daemon=True)
        tunnel_thread.start()
    
    try:
        app.run(host=HOST, port=PORT, debug=DEBUG, ssl_context=ssl_context)
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        print(f"❌ Server error: {e}")
        sys.exit(1)
    finally:
        logger.info("Server stopped")

