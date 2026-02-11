#!/usr/bin/env python3
"""
Simple API Upload Demo for Raspberry Pi
=======================================
This script demonstrates how to programmatically upload an image to the server.
It is designed to be called by a cron job or another automation tool.

Usage:
    python3 demo_upload.py <path_to_image> [options]

Options:
    --url <url>         Server URL (default: http://localhost:8443)
    --key <api_key>     API Key (must match .env)
    --cam <id>          Camera ID (e.g., cam1)
"""

import sys
import os
import argparse
import json
from datetime import datetime
import requests # pip install requests

# Default Configuration (Change these to match your setup)
DEFAULT_SERVER_URL = "http://localhost:8443"
# Retrieve this from your .env file on the server
DEFAULT_API_KEY = "rpi-cam1-secret-key-2024" 

def upload_image(filepath, server_url, api_key, camera_id="cam1"):
    if not os.path.exists(filepath):
        print(f"❌ Error: File not found: {filepath}")
        return False

    url = f"{server_url}/api/upload"
    
    # Metadata to send with the image
    data = {
        "api_key": api_key,
        "camera_id": camera_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notes": "Uploaded via demo script"
    }

    # Open the file in binary mode
    with open(filepath, "rb") as f:
        files = {"file": f}
        
        print(f"📤 Uploading {filepath} to {url}...")
        try:
            # Send POST request
            # verify=False is used if using self-signed SSL certs (common in dev)
            # In production with real certs, remove verify=False
            response = requests.post(url, data=data, files=files, timeout=30, verify=False)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print(f"✅ Success! Snapshot ID: {result['snapshot_id']}")
                    print(f"   Filename: {result['filename']}")
                    return True
                else:
                    print(f"❌ Upload failed: {result.get('error')}")
            else:
                print(f"❌ Server error (HTTP {response.status_code}): {response.text}")
                
        except Exception as e:
            print(f"❌ Connection error: {e}")

    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload image to Aeroponic Database")
    parser.add_argument("filepath", help="Path to image file")
    parser.add_argument("--url", default=DEFAULT_SERVER_URL, help="Server URL")
    parser.add_argument("--key", default=DEFAULT_API_KEY, help="API Key")
    parser.add_argument("--cam", default="cam1", help="Camera ID")
    
    args = parser.parse_args()
    
    upload_image(args.filepath, args.url, args.key, args.cam)
