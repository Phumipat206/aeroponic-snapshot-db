# Aeroponic Snapshot Database - API Usage Examples

"""
This file contains examples of how to use the database and video generation
functions programmatically without the web interface.

Usage:
    python scripts/examples.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.paths import ProjectPaths
from src.logger import get_logger
from src.database import *
from src.video_generator import *
from src.utils import *
from datetime import datetime, timedelta

# Setup logger
logger = get_logger('examples')

# ============================================================================
# Example 1: Query all snapshots from the last 7 days
# ============================================================================

def example_recent_snapshots():
    """Get snapshots from the last 7 days"""
    print("Example 1: Recent Snapshots")
    print("-" * 50)
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)
    
    snapshots = query_snapshots(
        start_time=start_time,
        end_time=end_time,
        order_by='capture_time DESC'
    )
    
    print(f"Found {len(snapshots)} snapshots in the last 7 days")
    for snapshot in snapshots[:5]:  # Show first 5
        print(f"  - {snapshot['original_filename']} ({snapshot['capture_time']})")
    print()

# ============================================================================
# Example 2: Get snapshots at 9 AM each day for time-lapse
# ============================================================================

def example_daily_9am_timelapse():
    """Create time-lapse from daily 9 AM snapshots"""
    print("Example 2: Daily 9 AM Time-lapse")
    print("-" * 50)
    
    # Get snapshots around 9 AM each day (±10 minutes)
    snapshots = get_snapshots_by_daily_time(hour=9, minute=0, tolerance_minutes=10)
    
    print(f"Found {len(snapshots)} snapshots around 9 AM")
    
    if len(snapshots) >= 2:
        # Prepare snapshot data with timestamps
        snapshot_data = [
            (s['filepath'], parse_datetime(s['capture_time']), f"Day {i+1}")
            for i, s in enumerate(snapshots)
        ]
        
        # Generate video
        output_filename = f"daily_9am_timelapse_{datetime.now().strftime('%Y%m%d')}.mp4"
        success, video_path, error = create_timelapse_with_timestamps(
            snapshot_data,
            output_filename,
            fps=5,  # Slower for daily review
            show_timestamp=True
        )
        
        if success:
            print(f"✅ Video created: {video_path}")
        else:
            print(f"❌ Error: {error}")
    else:
        print("Not enough snapshots to create video")
    print()

# ============================================================================
# Example 3: Query by category and create video
# ============================================================================

def example_category_video():
    """Create video from a specific category"""
    print("Example 3: Category-based Video")
    print("-" * 50)
    
    # Get all categories
    categories = get_categories_tree()
    print("Available categories:")
    for cat in categories:
        print(f"  [{cat['id']}] {cat['name']}")
    
    # Example: Get snapshots from category 1 (Root System)
    category_id = 1
    snapshots = query_snapshots(
        category_id=category_id,
        order_by='capture_time ASC',
        limit=100
    )
    
    print(f"\nFound {len(snapshots)} snapshots in category {category_id}")
    
    if len(snapshots) >= 2:
        paths = [s['filepath'] for s in snapshots]
        output_filename = f"category_{category_id}_timelapse.mp4"
        
        success, video_path, error = create_timelapse_video(
            paths,
            output_filename,
            fps=10
        )
        
        if success:
            print(f"✅ Video created: {video_path}")
        else:
            print(f"❌ Error: {error}")
    print()

# ============================================================================
# Example 4: Add a new snapshot programmatically
# ============================================================================

def example_add_snapshot():
    """Add a snapshot to the database"""
    print("Example 4: Add Snapshot Programmatically")
    print("-" * 50)
    
    # Example snapshot details
    image_path = "path/to/your/image.jpg"
    
    # Check if file exists
    if not os.path.exists(image_path):
        print("⚠️  Image file not found. This is just an example.")
        print()
        return
    
    # Get image dimensions
    width, height = get_image_dimensions(image_path)
    
    # Add to database
    snapshot_id = add_snapshot(
        filename=os.path.basename(image_path),
        original_filename=os.path.basename(image_path),
        filepath=image_path,
        category_id=1,  # Root System
        capture_time=datetime.now(),
        file_size=os.path.getsize(image_path),
        width=width,
        height=height,
        source='Python Script',
        tags='example,test',
        notes='Added via Python script'
    )
    
    print(f"✅ Snapshot added with ID: {snapshot_id}")
    print()

# ============================================================================
# Example 5: Get database statistics
# ============================================================================

def example_statistics():
    """Display database statistics"""
    print("Example 5: Database Statistics")
    print("-" * 50)
    
    stats = get_database_stats()
    
    print(f"Total Snapshots: {stats['total_snapshots']}")
    print(f"Total Categories: {stats['total_categories']}")
    print(f"Total Videos: {stats['total_videos']}")
    print(f"Total Storage: {stats['total_size_bytes'] / (1024**3):.2f} GB")
    print(f"Earliest Snapshot: {stats['earliest_snapshot']}")
    print(f"Latest Snapshot: {stats['latest_snapshot']}")
    print()

# ============================================================================
# Example 6: Create comparison video (side-by-side)
# ============================================================================

def example_comparison_video():
    """Create side-by-side comparison video"""
    print("Example 6: Comparison Video")
    print("-" * 50)
    
    # Get snapshots from two different categories
    category1_snapshots = query_snapshots(category_id=1, limit=30, order_by='capture_time ASC')
    category2_snapshots = query_snapshots(category_id=2, limit=30, order_by='capture_time ASC')
    
    if len(category1_snapshots) >= 2 and len(category2_snapshots) >= 2:
        snapshot_groups = [
            [s['filepath'] for s in category1_snapshots],
            [s['filepath'] for s in category2_snapshots]
        ]
        
        output_filename = f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        success, video_path, error = create_comparison_video(
            snapshot_groups,
            output_filename,
            fps=10
        )
        
        if success:
            print(f"✅ Comparison video created: {video_path}")
        else:
            print(f"❌ Error: {error}")
    else:
        print("Not enough snapshots in both categories")
    print()

# ============================================================================
# Example 7: Filter by tags and date range
# ============================================================================

def example_advanced_query():
    """Advanced query with multiple filters"""
    print("Example 7: Advanced Query")
    print("-" * 50)
    
    # Query with multiple criteria
    snapshots = query_snapshots(
        category_id=1,
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 31),
        tags='growth',
        limit=50
    )
    
    print(f"Found {len(snapshots)} snapshots matching criteria:")
    print("  - Category: 1")
    print("  - Date Range: January 2026")
    print("  - Tags: growth")
    print()
    
    # Group by date
    from collections import defaultdict
    by_date = defaultdict(list)
    
    for snapshot in snapshots:
        date = snapshot['capture_time'][:10]
        by_date[date].append(snapshot)
    
    print("Snapshots by date:")
    for date, snaps in sorted(by_date.items()):
        print(f"  {date}: {len(snaps)} snapshots")
    print()

# ============================================================================
# Main function to run all examples
# ============================================================================

def run_all_examples():
    """Run all example functions"""
    print("\n" + "=" * 60)
    print("AEROPONIC SNAPSHOT DATABASE - API EXAMPLES")
    print("=" * 60 + "\n")
    
    # Initialize database
    init_database()
    
    # Run examples
    example_statistics()
    example_recent_snapshots()
    # example_daily_9am_timelapse()  # Uncomment if you have daily snapshots
    # example_category_video()  # Uncomment if you have categorized snapshots
    # example_add_snapshot()  # Uncomment to test adding snapshots
    # example_comparison_video()  # Uncomment if you have multiple categories
    example_advanced_query()
    
    print("=" * 60)
    print("Examples completed! Review the code to learn more.")
    print("=" * 60)

if __name__ == '__main__':
    run_all_examples()
