import cv2
import os
import threading
import numpy as np
import subprocess
import shutil
from datetime import datetime
from PIL import Image
from src.config import VIDEOS_FOLDER, VIDEO_FPS
from src.logger import get_logger

# Get logger for this module
logger = get_logger('video_generator')

# Global progress tracking for video generation jobs
# Protected by a lock (Fix #3)
_progress_lock = threading.Lock()
video_progress = {}


def update_progress(job_id, current, total, status='processing'):
    """Update progress for a video generation job"""
    if job_id:
        with _progress_lock:
            video_progress[job_id] = {
                'current': current,
                'total': total,
                'percent': int((current / total) * 100) if total > 0 else 0,
                'status': status
            }


def get_progress(job_id):
    """Get progress for a video generation job"""
    with _progress_lock:
        return video_progress.get(job_id, {'current': 0, 'total': 0, 'percent': 0, 'status': 'unknown'}).copy()


def clear_progress(job_id):
    """Clear progress for a completed job"""
    with _progress_lock:
        video_progress.pop(job_id, None)


# --- Fix #7: Cache codec test result ---
_codec_cache = None
_codec_cache_lock = threading.Lock()


def get_video_codec():
    """
    Get the best available video codec for the system.
    Caches the result after first probe (Fix #7).
    """
    global _codec_cache
    
    with _codec_cache_lock:
        if _codec_cache is not None:
            return _codec_cache

    # Try different codecs in order of preference
    codecs_to_try = [
        ('XVID', '.avi'),
        ('MJPG', '.avi'),
        ('mp4v', '.mp4'),
        ('DIVX', '.avi'),
        ('WMV1', '.wmv'),
    ]

    os.makedirs(VIDEOS_FOLDER, exist_ok=True)

    for codec, ext in codecs_to_try:
        try:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            test_path = os.path.join(VIDEOS_FOLDER, '_codec_test' + ext)
            test_writer = cv2.VideoWriter(test_path, fourcc, 1, (100, 100))
            if test_writer.isOpened():
                test_writer.release()
                if os.path.exists(test_path):
                    os.remove(test_path)
                logger.info(f"Using video codec: {codec}")
                result = (fourcc, ext)
                with _codec_cache_lock:
                    _codec_cache = result
                return result
            if os.path.exists(test_path):
                os.remove(test_path)
        except Exception as e:
            logger.warning(f"Codec {codec} failed: {e}")
            continue

    # Default fallback
    logger.info("Using fallback codec: MJPG")
    result = (cv2.VideoWriter_fourcc(*'MJPG'), '.avi')
    with _codec_cache_lock:
        _codec_cache = result
    return result


def create_timelapse_video(snapshot_paths, output_filename, fps=VIDEO_FPS, job_id=None):
    """
    Create a time-lapse video from a list of snapshot file paths

    Args:
        snapshot_paths: List of full paths to snapshot images
        output_filename: Name for the output video file
        fps: Frames per second for the video
        job_id: Optional job ID for progress tracking

    Returns:
        tuple: (success, video_path, error_message)
    """
    if not snapshot_paths:
        return False, None, "No snapshots provided"

    total_images = len(snapshot_paths)

    try:
        os.makedirs(VIDEOS_FOLDER, exist_ok=True)
        output_path = os.path.join(VIDEOS_FOLDER, output_filename)

        update_progress(job_id, 0, total_images, 'preparing')

        first_img = cv2.imread(snapshot_paths[0])
        if first_img is None:
            return False, None, f"Could not read first image: {snapshot_paths[0]}"

        height, width, layers = first_img.shape

        fourcc, ext = get_video_codec()

        output_base = os.path.splitext(output_filename)[0]
        output_path = os.path.join(VIDEOS_FOLDER, output_base + ext)

        video_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not video_writer.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            output_path = os.path.join(VIDEOS_FOLDER, output_base + '.avi')
            video_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

            if not video_writer.isOpened():
                return False, None, "Failed to initialize video writer"

        for i, img_path in enumerate(snapshot_paths):
            try:
                update_progress(job_id, i + 1, total_images, 'processing')

                img = cv2.imread(img_path)

                if img is None:
                    logger.warning(f"Could not read image {img_path}, skipping...")
                    continue

                if img.shape[0] != height or img.shape[1] != width:
                    img = cv2.resize(img, (width, height))

                video_writer.write(img)

            except Exception as e:
                logger.error(f"Error processing image {img_path}: {e}")
                continue

        video_writer.release()

        update_progress(job_id, total_images, total_images, 'encoding')

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            update_progress(job_id, total_images, total_images, 'complete')
            return True, output_path, None
        else:
            return False, None, "Video file was not created or is empty"

    except Exception as e:
        return False, None, f"Error creating video: {str(e)}"


def create_timelapse_with_timestamps(snapshot_data, output_filename, fps=VIDEO_FPS,
                                     show_timestamp=True, show_info=True, job_id=None):
    """
    Create a time-lapse video with timestamp overlays

    Args:
        snapshot_data: List of tuples (filepath, capture_time, optional_info)
        output_filename: Name for the output video file
        fps: Frames per second
        show_timestamp: Whether to overlay timestamp on each frame
        show_info: Whether to show additional info
        job_id: Optional job ID for progress tracking

    Returns:
        tuple: (success, video_path, error_message)
    """
    if not snapshot_data:
        return False, None, "No snapshots provided"

    total_images = len(snapshot_data)

    try:
        os.makedirs(VIDEOS_FOLDER, exist_ok=True)
        output_path = os.path.join(VIDEOS_FOLDER, output_filename)

        update_progress(job_id, 0, total_images, 'preparing')

        first_img = cv2.imread(snapshot_data[0][0])
        if first_img is None:
            return False, None, f"Could not read first image: {snapshot_data[0][0]}"

        height, width, layers = first_img.shape

        fourcc, ext = get_video_codec()

        output_base = os.path.splitext(output_filename)[0]
        output_path = os.path.join(VIDEOS_FOLDER, output_base + ext)

        video_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not video_writer.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            output_path = os.path.join(VIDEOS_FOLDER, output_base + '.avi')
            video_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

            if not video_writer.isOpened():
                return False, None, "Failed to initialize video writer"

        for i, data in enumerate(snapshot_data):
            try:
                update_progress(job_id, i + 1, total_images, 'processing')

                img_path = data[0]
                capture_time = data[1] if len(data) > 1 else None
                info = data[2] if len(data) > 2 else None

                img = cv2.imread(img_path)

                if img is None:
                    logger.warning(f"Could not read image {img_path}, skipping...")
                    continue

                if img.shape[0] != height or img.shape[1] != width:
                    img = cv2.resize(img, (width, height))

                if show_timestamp and capture_time:
                    timestamp_text = capture_time.strftime('%Y-%m-%d %H:%M:%S')

                    overlay = img.copy()
                    cv2.rectangle(overlay, (10, 10), (400, 60), (0, 0, 0), -1)
                    img = cv2.addWeighted(overlay, 0.6, img, 0.4, 0)

                    cv2.putText(img, timestamp_text, (20, 45),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

                if show_info and info:
                    cv2.putText(img, str(info), (20, height - 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

                video_writer.write(img)

            except Exception as e:
                logger.error(f"Error processing image: {e}")
                continue

        video_writer.release()

        update_progress(job_id, total_images, total_images, 'encoding')

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            update_progress(job_id, total_images, total_images, 'complete')
            return True, output_path, None
        else:
            return False, None, "Video file was not created or is empty"

    except Exception as e:
        return False, None, f"Error creating video: {str(e)}"


def create_comparison_video(snapshot_groups, output_filename, fps=VIDEO_FPS):
    """
    Create a video with side-by-side comparison of multiple snapshot sequences

    Args:
        snapshot_groups: List of lists, each containing paths to a sequence of snapshots
        output_filename: Name for output video
        fps: Frames per second

    Returns:
        tuple: (success, video_path, error_message)
    """
    if not snapshot_groups or not any(snapshot_groups):
        return False, None, "No snapshot groups provided"

    try:
        os.makedirs(VIDEOS_FOLDER, exist_ok=True)
        output_path = os.path.join(VIDEOS_FOLDER, output_filename)

        max_length = max(len(group) for group in snapshot_groups)
        num_groups = len(snapshot_groups)

        first_images = []
        for group in snapshot_groups:
            if group:
                img = cv2.imread(group[0])
                if img is not None:
                    first_images.append(img)

        if not first_images:
            return False, None, "Could not read any images"

        sample_height, sample_width = first_images[0].shape[:2]
        output_width = sample_width * num_groups
        output_height = sample_height

        fourcc, ext = get_video_codec()

        output_base = os.path.splitext(output_filename)[0]
        output_path = os.path.join(VIDEOS_FOLDER, output_base + ext)

        video_writer = cv2.VideoWriter(output_path, fourcc, fps,
                                       (output_width, output_height))

        if not video_writer.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            output_path = os.path.join(VIDEOS_FOLDER, output_base + '.avi')
            video_writer = cv2.VideoWriter(output_path, fourcc, fps,
                                           (output_width, output_height))

            if not video_writer.isOpened():
                return False, None, "Failed to initialize video writer"

        for frame_idx in range(max_length):
            combined_frame = None

            for group_idx, group in enumerate(snapshot_groups):
                img_idx = min(frame_idx, len(group) - 1) if group else 0

                if group and img_idx < len(group):
                    img = cv2.imread(group[img_idx])
                    if img is not None:
                        img = cv2.resize(img, (sample_width, sample_height))
                    else:
                        img = np.zeros((sample_height, sample_width, 3), dtype=np.uint8)
                else:
                    img = np.zeros((sample_height, sample_width, 3), dtype=np.uint8)

                if combined_frame is None:
                    combined_frame = img
                else:
                    combined_frame = np.hstack((combined_frame, img))

            video_writer.write(combined_frame)

        video_writer.release()

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True, output_path, None
        else:
            return False, None, "Video file was not created or is empty"

    except Exception as e:
        return False, None, f"Error creating comparison video: {str(e)}"
