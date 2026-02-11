#!/bin/bash
# =============================================================================
# Raspberry Pi Snapshot Upload Script (Bash version)
# =============================================================================
#
# Usage:
#     ./upload_snapshot.sh /path/to/image.jpg
#     ./upload_snapshot.sh   # Capture from camera and upload
#
# Crontab setup:
#     crontab -e
#     # Add this line:
#     */30 * * * * /home/pi/upload_snapshot.sh >> /home/pi/upload.log 2>&1
#
# =============================================================================

# CONFIGURATION — Edit these values to match your server setup
SERVER_URL="https://localhost:8443"   # Change to your server IP or tunnel URL
API_KEY="rpi-cam1-secret-key-2024"    # Must match API_KEYS in server's .env
CAMERA_ID="cam1"                      # This camera's identifier
PROJECT_NAME="Aeroponic System 1"     # Project name for categorization
SNAPSHOT_DIR="/home/pi/snapshots"     # Local directory for captured images

# =============================================================================

# Create snapshot directory if it doesn't exist
mkdir -p "$SNAPSHOT_DIR"

# Generate timestamp
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
DATE_STR=$(date +%Y-%m-%d\ %H:%M:%S)

echo "========================================"
echo "RASPBERRY PI SNAPSHOT UPLOAD"
echo "========================================"
echo "Time: $DATE_STR"
echo ""

# If an argument is provided, use that file; otherwise capture from camera
if [ -n "$1" ]; then
    IMAGE_PATH="$1"
    echo "Using existing image: $IMAGE_PATH"
else
    # Capture from camera
    IMAGE_PATH="$SNAPSHOT_DIR/snapshot_${TIMESTAMP}.jpg"

    echo "Capturing image from camera..."

    # Use libcamera-still for Raspberry Pi 4/5 (new camera stack)
    if command -v libcamera-still &> /dev/null; then
        libcamera-still -o "$IMAGE_PATH" --width 1920 --height 1080 -t 1000 --nopreview
    # Use raspistill for legacy camera stack
    elif command -v raspistill &> /dev/null; then
        raspistill -o "$IMAGE_PATH" -w 1920 -h 1080 -t 1000
    else
        echo "ERROR: No camera command found (libcamera-still or raspistill)"
        exit 1
    fi

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to capture image"
        exit 1
    fi

    echo "   Saved to: $IMAGE_PATH"
fi

# Check that the file exists
if [ ! -f "$IMAGE_PATH" ]; then
    echo "ERROR: Image file not found: $IMAGE_PATH"
    exit 1
fi

# Upload
echo ""
echo "Uploading to: $SERVER_URL"
echo "   Camera: $CAMERA_ID"
echo "   Project: $PROJECT_NAME"
echo ""

RESPONSE=$(curl -sk -w "\n%{http_code}" -X POST "${SERVER_URL}/api/upload" \
    -F "file=@${IMAGE_PATH}" \
    -F "api_key=${API_KEY}" \
    -F "camera_id=${CAMERA_ID}" \
    -F "project_name=${PROJECT_NAME}" \
    -F "timestamp=${TIMESTAMP}")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "Response: $BODY"
echo ""

if [ "$HTTP_CODE" = "200" ]; then
    # Check if success is true in JSON response
    if echo "$BODY" | grep -q '"success": true' || echo "$BODY" | grep -q '"success":true'; then
        echo "Upload successful!"

        # Extract info from response
        SNAPSHOT_ID=$(echo "$BODY" | grep -o '"snapshot_id": *[0-9]*' | grep -o '[0-9]*')
        FILENAME=$(echo "$BODY" | grep -o '"filename": *"[^"]*"' | cut -d'"' -f4)

        if [ -n "$SNAPSHOT_ID" ]; then
            echo "   Snapshot ID: $SNAPSHOT_ID"
        fi
        if [ -n "$FILENAME" ]; then
            echo "   Filename: $FILENAME"
        fi

        # Optionally delete local file after successful upload
        # rm -f "$IMAGE_PATH"

        echo "========================================"
        exit 0
    else
        echo "ERROR: Upload failed (API error)"
        echo "========================================"
        exit 1
    fi
else
    echo "ERROR: Upload failed (HTTP $HTTP_CODE)"
    echo "========================================"
    exit 1
fi
