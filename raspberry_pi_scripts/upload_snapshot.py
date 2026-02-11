#!/usr/bin/env python3
"""
Raspberry Pi Snapshot Upload Script
====================================
Automatically upload images from Raspberry Pi to the Aeroponic server.

Installation:
    pip3 install requests

Usage:
    python3 upload_snapshot.py /path/to/image.jpg
    python3 upload_snapshot.py /path/to/image.jpg --camera cam1 --project "Aeroponic System 1"
    python3 upload_snapshot.py --capture   # Capture from camera and upload
    python3 upload_snapshot.py --test      # Test server connectivity

Crontab examples:
    # Upload every 30 minutes
    */30 * * * * /usr/bin/python3 /home/pi/upload_snapshot.py --capture >> /home/pi/upload.log 2>&1

    # Upload every hour
    0 * * * * /usr/bin/python3 /home/pi/upload_snapshot.py --capture >> /home/pi/upload.log 2>&1

    # Upload at 6 AM, 12 PM, 6 PM
    0 6,12,18 * * * /usr/bin/python3 /home/pi/upload_snapshot.py --capture >> /home/pi/upload.log 2>&1
"""

import os
import sys
import argparse
import requests
from datetime import datetime

# =============================================================================
# CONFIGURATION — Edit these values to match your server setup
# =============================================================================

# Server URL — use the server's IP address or Cloudflare tunnel URL
SERVER_URL = "https://localhost:8443"  # Change to your server IP or tunnel URL
# Example: SERVER_URL = "https://192.168.1.100:8443"
# Example: SERVER_URL = "https://random-words.trycloudflare.com"

# API Key — must match one of the keys in the server's .env file (API_KEYS=...)
API_KEY = "rpi-cam1-secret-key-2024"

# Default camera ID
DEFAULT_CAMERA_ID = "cam1"

# Default project name
DEFAULT_PROJECT_NAME = ""

# =============================================================================


def upload_snapshot(image_path, camera_id=None, project_name=None, 
                   timestamp=None, tags=None, notes=None, server_url=None, api_key=None):
    """
    Upload snapshot to server via API
    
    Args:
        image_path: Path to image file
        camera_id: Camera identifier (e.g., cam1, cam2)
        project_name: Project name for categorization
        timestamp: Capture timestamp (datetime object or string)
        tags: Additional tags (comma-separated)
        notes: Additional notes
        server_url: Server URL (overrides config)
        api_key: API key (overrides config)
    
    Returns:
        dict with upload result
    """
    # Use defaults if not specified
    server_url = server_url or SERVER_URL
    api_key = api_key or API_KEY
    camera_id = camera_id or DEFAULT_CAMERA_ID
    project_name = project_name or DEFAULT_PROJECT_NAME
    
    # Validate image file
    if not os.path.exists(image_path):
        return {'success': False, 'error': f'File not found: {image_path}'}
    
    if not os.path.isfile(image_path):
        return {'success': False, 'error': f'Not a file: {image_path}'}
    
    # Prepare timestamp
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    elif isinstance(timestamp, datetime):
        timestamp = timestamp.strftime('%Y-%m-%d_%H-%M-%S')
    
    # Prepare upload URL
    upload_url = f"{server_url.rstrip('/')}/api/upload"
    
    # Prepare form data
    data = {
        'api_key': api_key,
        'camera_id': camera_id,
        'timestamp': timestamp,
    }
    
    if project_name:
        data['project_name'] = project_name
    if tags:
        data['tags'] = tags
    if notes:
        data['notes'] = notes
    
    # Open and upload file
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (os.path.basename(image_path), f, 'image/jpeg')}
            
            print(f"📤 Uploading: {image_path}")
            print(f"   Server: {server_url}")
            print(f"   Camera: {camera_id}")
            if project_name:
                print(f"   Project: {project_name}")
            
            response = requests.post(upload_url, data=data, files=files, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"✅ Upload successful!")
                    print(f"   Snapshot ID: {result.get('snapshot_id')}")
                    print(f"   Filename: {result.get('filename')}")
                    print(f"   Capture time: {result.get('capture_time')}")
                    return result
                else:
                    error_msg = result.get('error', 'Unknown error')
                    print(f"❌ Upload failed: {error_msg}")
                    return {'success': False, 'error': error_msg}
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                print(f"❌ Upload failed: {error_msg}")
                return {'success': False, 'error': error_msg}
                
    except requests.exceptions.ConnectionError:
        error_msg = f"Cannot connect to server: {server_url}"
        print(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}
    except requests.exceptions.Timeout:
        error_msg = "Request timeout"
        print(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error: {error_msg}")
        return {'success': False, 'error': error_msg}


def capture_and_upload(camera_id=None, project_name=None, output_dir="/tmp"):
    """
    Capture image from camera and upload (Raspberry Pi with camera module)
    
    Requires: picamera2 library
    """
    try:
        from picamera2 import Picamera2
        
        # Generate filename with timestamp
        timestamp = datetime.now()
        filename = f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(output_dir, filename)
        
        # Capture image
        print(f"📷 Capturing image...")
        picam2 = Picamera2()
        config = picam2.create_still_configuration()
        picam2.configure(config)
        picam2.start()
        picam2.capture_file(filepath)
        picam2.stop()
        picam2.close()
        
        print(f"   Saved to: {filepath}")
        
        # Upload
        result = upload_snapshot(
            filepath, 
            camera_id=camera_id,
            project_name=project_name,
            timestamp=timestamp
        )
        
        # Optionally delete local file after upload
        # if result.get('success'):
        #     os.remove(filepath)
        
        return result
        
    except ImportError:
        print("❌ picamera2 library not installed")
        print("   Install with: pip install picamera2")
        return {'success': False, 'error': 'picamera2 not installed'}
    except Exception as e:
        print(f"❌ Capture error: {e}")
        return {'success': False, 'error': str(e)}


def main():
    parser = argparse.ArgumentParser(
        description='Upload snapshot to Aeroponic Monitoring System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('image_path', nargs='?', 
                       help='Path to image file (optional if using --capture)')
    parser.add_argument('--camera', '-c', default=DEFAULT_CAMERA_ID,
                       help=f'Camera ID (default: {DEFAULT_CAMERA_ID})')
    parser.add_argument('--project', '-p', default=DEFAULT_PROJECT_NAME,
                       help='Project name')
    parser.add_argument('--server', '-s', default=SERVER_URL,
                       help=f'Server URL (default: {SERVER_URL})')
    parser.add_argument('--api-key', '-k', default=API_KEY,
                       help='API key for authentication')
    parser.add_argument('--tags', '-t', default='',
                       help='Comma-separated tags')
    parser.add_argument('--notes', '-n', default='',
                       help='Additional notes')
    parser.add_argument('--capture', action='store_true',
                       help='Capture from camera and upload (Raspberry Pi only)')
    parser.add_argument('--test', action='store_true',
                       help='Test connection to server')
    
    args = parser.parse_args()
    
    # Test connection
    if args.test:
        print(f"🔍 Testing connection to {args.server}...")
        try:
            response = requests.get(f"{args.server.rstrip('/')}/api/upload/test", timeout=10)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Server is ready!")
                print(f"   Message: {result.get('message')}")
                print(f"\n📝 Usage example:")
                print(f"   {result.get('example_curl')}")
            else:
                print(f"❌ Server returned: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to server: {args.server}")
        except Exception as e:
            print(f"❌ Error: {e}")
        return
    
    # Capture and upload
    if args.capture:
        result = capture_and_upload(
            camera_id=args.camera,
            project_name=args.project
        )
        sys.exit(0 if result.get('success') else 1)
    
    # Upload existing file
    if not args.image_path:
        parser.print_help()
        print("\n❌ Error: Please specify an image path or use --capture")
        sys.exit(1)
    
    # Print header
    print("=" * 50)
    print("RASPBERRY PI SNAPSHOT UPLOAD")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    result = upload_snapshot(
        image_path=args.image_path,
        camera_id=args.camera,
        project_name=args.project,
        tags=args.tags,
        notes=args.notes,
        server_url=args.server,
        api_key=args.api_key
    )
    
    print()
    print("=" * 50)
    
    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
