"""
Batch Import Script for Aeroponic Snapshots
This script allows importing multiple snapshots from a folder structure
into the database using command line.

Supported folder structures:
    1. Flat: /images/*.jpg
    2. Camera folders: /cam1/*.jpg, /cam2/*.jpg
    3. Date-level folders: /cam1/1_01-15/*.jpg, /cam1/2_01-16/*.jpg
       Format: [sequence]_[MM-DD] (e.g., 1_01-15 = first batch on Jan 15)

Usage:
    python scripts/batch_import.py <folder_path> [options]

Options:
    --source <name>       Source name for imported snapshots (default: "Batch Import")
    --category <id>       Default category ID for imported snapshots
    --recursive          Recursively import from subdirectories (default: True)
    --tags <tags>        Comma-separated tags to add to all snapshots
    --parse-structure    Parse cam[n]/[n]_MM-DD folder structure for metadata
    
Examples:
    python scripts/batch_import.py "C:\\My Snapshots"
    python scripts/batch_import.py "C:\\Drive1" --source "Google Drive 1" --tags "drive1,imported"
    python scripts/batch_import.py "D:\\Aeroponic" --category 1 --source "External Drive"
    python scripts/batch_import.py "E:\\RaspberryPi" --parse-structure --source "RPi Cameras"
"""

import sys
import os
import argparse
import re
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.paths import ProjectPaths
from src.logger import get_logger
from src.database import add_snapshot, init_database, get_categories_tree
from src.utils import allowed_file, generate_unique_filename, get_image_dimensions, extract_datetime_from_filename
from src.config import UPLOAD_FOLDER
import shutil

# Setup logger
logger = get_logger('batch_import')


def parse_date_folder(folder_name):
    """
    Parse date-level folder name like "1_01-15" or "2_01-16"
    
    Format: [n]_MM-DD where:
        - n = sequence number (1, 2, 3, ...)
        - MM = month (01-12)
        - DD = day (01-31)
    
    Returns:
        dict with 'sequence', 'month', 'day' or None if not matching
    
    Examples:
        "1_01-15" -> {'sequence': 1, 'month': '01', 'day': '15', 'date_str': '01-15'}
        "2_12-25" -> {'sequence': 2, 'month': '12', 'day': '25', 'date_str': '12-25'}
    """
    # Pattern: [n]_MM-DD
    pattern = r'^(\d+)_(\d{2})-(\d{2})$'
    match = re.match(pattern, folder_name)
    
    if match:
        return {
            'sequence': int(match.group(1)),
            'month': match.group(2),
            'day': match.group(3),
            'date_str': f"{match.group(2)}-{match.group(3)}"
        }
    return None


def parse_camera_folder(folder_name):
    """
    Parse camera folder name like "cam1", "cam2", "camera_1", etc.
    
    Returns:
        dict with 'camera_id', 'camera_num' or None if not matching
    
    Examples:
        "cam1" -> {'camera_id': 'cam1', 'camera_num': 1}
        "camera_2" -> {'camera_id': 'camera_2', 'camera_num': 2}
    """
    # Pattern: cam[n] or camera_[n] or camera[n]
    patterns = [
        r'^cam(\d+)$',
        r'^camera_(\d+)$',
        r'^camera(\d+)$',
        r'^CAM(\d+)$',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, folder_name, re.IGNORECASE)
        if match:
            return {
                'camera_id': folder_name,
                'camera_num': int(match.group(1))
            }
    return None


def analyze_folder_structure(folder_path):
    """
    Analyze folder structure to detect camera and date-level folders.
    
    Returns:
        dict with structure info
    """
    structure = {
        'type': 'flat',  # flat, camera_only, camera_with_dates
        'cameras': [],
        'has_date_folders': False,
        'total_images': 0
    }
    
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if not os.path.isdir(item_path):
            continue
        
        cam_info = parse_camera_folder(item)
        if cam_info:
            structure['type'] = 'camera_only'
            cam_data = {
                'name': item,
                'camera_id': cam_info['camera_id'],
                'camera_num': cam_info['camera_num'],
                'date_folders': []
            }
            
            # Check for date subfolders
            for sub_item in os.listdir(item_path):
                sub_path = os.path.join(item_path, sub_item)
                if os.path.isdir(sub_path):
                    date_info = parse_date_folder(sub_item)
                    if date_info:
                        structure['has_date_folders'] = True
                        structure['type'] = 'camera_with_dates'
                        cam_data['date_folders'].append({
                            'name': sub_item,
                            **date_info
                        })
            
            structure['cameras'].append(cam_data)
    
    return structure


def import_folder(folder_path, source_name='Batch Import', default_category=None, 
                 recursive=True, tags='', parse_structure=False):
    """
    Import all images from a folder into the database
    
    Args:
        folder_path: Path to the folder containing images
        source_name: Name to identify the source of imports
        default_category: Default category ID for snapshots
        recursive: Whether to search subdirectories
        tags: Tags to add to all imported snapshots
        parse_structure: Whether to parse cam[n]/[n]_MM-DD folder structure
    """
    
    if not os.path.exists(folder_path):
        print(f"❌ Error: Folder not found: {folder_path}")
        return 0, []
    
    if not os.path.isdir(folder_path):
        print(f"❌ Error: Not a directory: {folder_path}")
        return 0, []
    
    print(f"\n🔍 Scanning folder: {folder_path}")
    print(f"   Recursive: {recursive}")
    print(f"   Parse Structure: {parse_structure}")
    print(f"   Source: {source_name}")
    if default_category:
        print(f"   Category: {default_category}")
    if tags:
        print(f"   Tags: {tags}")
    
    # Analyze structure if parsing is enabled
    if parse_structure:
        print(f"\n📁 Analyzing folder structure...")
        structure = analyze_folder_structure(folder_path)
        print(f"   Structure type: {structure['type']}")
        print(f"   Cameras found: {len(structure['cameras'])}")
        print(f"   Has date folders: {structure['has_date_folders']}")
        
        if structure['cameras']:
            print(f"\n   📷 Cameras detected:")
            for cam in structure['cameras']:
                date_count = len(cam['date_folders'])
                print(f"      - {cam['camera_id']}: {date_count} date folders")
                for df in cam['date_folders'][:3]:  # Show first 3
                    print(f"        └── {df['name']} (seq:{df['sequence']}, date:{df['date_str']})")
                if date_count > 3:
                    print(f"        └── ... and {date_count - 3} more")
    
    print()
    
    imported_count = 0
    errors = []
    
    # Walk through directory
    if recursive:
        walk_iterator = os.walk(folder_path)
    else:
        walk_iterator = [(folder_path, [], os.listdir(folder_path))]
    
    for root, dirs, files in walk_iterator:
        for filename in files:
            if not allowed_file(filename):
                continue
            
            try:
                source_path = os.path.join(root, filename)
                relative_path = os.path.relpath(root, folder_path)
                
                # Parse folder structure for metadata
                camera_id = None
                project_name = None
                date_info = None
                
                if parse_structure and relative_path != '.':
                    path_parts = relative_path.split(os.sep)
                    
                    # Check first level for camera
                    if len(path_parts) >= 1:
                        cam_info = parse_camera_folder(path_parts[0])
                        if cam_info:
                            camera_id = cam_info['camera_id']
                    
                    # Check second level for date
                    if len(path_parts) >= 2:
                        date_info = parse_date_folder(path_parts[1])
                
                # Try to extract capture time from filename
                capture_time = extract_datetime_from_filename(filename)
                
                # If date_info exists, try to use it for capture date
                if not capture_time and date_info:
                    try:
                        current_year = datetime.now().year
                        capture_time = datetime(
                            current_year, 
                            int(date_info['month']), 
                            int(date_info['day']),
                            12, 0, 0  # Default to noon
                        )
                    except ValueError:
                        pass
                
                if not capture_time:
                    # Use file modification time as fallback
                    mtime = os.path.getmtime(source_path)
                    capture_time = datetime.fromtimestamp(mtime)
                
                # Generate unique filename with camera prefix
                if camera_id:
                    prefixed_filename = f"{camera_id}_{filename}"
                else:
                    prefixed_filename = filename
                unique_filename = generate_unique_filename(prefixed_filename)
                
                # Determine destination path
                if default_category:
                    category_dir = os.path.join(UPLOAD_FOLDER, f"category_{default_category}")
                    os.makedirs(category_dir, exist_ok=True)
                    dest_path = os.path.join(category_dir, unique_filename)
                else:
                    dest_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                
                # Copy file
                shutil.copy2(source_path, dest_path)
                
                # Get image info
                file_size = os.path.getsize(dest_path)
                width, height = get_image_dimensions(dest_path)
                
                # Build tags with structured data
                tag_parts = []
                if tags:
                    tag_parts.append(tags)
                if relative_path != '.':
                    tag_parts.append(relative_path.replace(os.sep, '/'))
                if camera_id:
                    tag_parts.append(f"camera:{camera_id}")
                if date_info:
                    tag_parts.append(f"date:{date_info['date_str']}")
                    tag_parts.append(f"seq:{date_info['sequence']}")
                
                combined_tags = ','.join(filter(None, tag_parts))
                
                # Build notes
                notes_parts = [f"Batch imported from: {source_path}"]
                if camera_id:
                    notes_parts.append(f"Camera: {camera_id}")
                if date_info:
                    notes_parts.append(f"Date folder: {date_info['date_str']} (seq {date_info['sequence']})")
                
                # Add to database
                snapshot_id = add_snapshot(
                    filename=unique_filename,
                    original_filename=filename,
                    filepath=dest_path,
                    category_id=default_category,
                    capture_time=capture_time,
                    file_size=file_size,
                    width=width,
                    height=height,
                    source=source_name,
                    tags=combined_tags,
                    notes=' | '.join(notes_parts)
                )
                
                imported_count += 1
                
                # Enhanced logging
                if camera_id and date_info:
                    print(f"✅ [{imported_count}] {camera_id}/{date_info['date_str']}/{filename} → ID {snapshot_id}")
                elif camera_id:
                    print(f"✅ [{imported_count}] {camera_id}/{filename} → ID {snapshot_id}")
                else:
                    print(f"✅ [{imported_count}] {filename} → ID {snapshot_id}")
                
            except Exception as e:
                error_msg = f"{filename}: {str(e)}"
                errors.append(error_msg)
                print(f"❌ Error importing {filename}: {e}")
                continue
    
    return imported_count, errors

def main():
    parser = argparse.ArgumentParser(
        description='Batch import aeroponic snapshots from a folder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('folder_path', help='Path to folder containing snapshots')
    parser.add_argument('--source', default='Batch Import', 
                       help='Source name for imported snapshots')
    parser.add_argument('--category', type=int, 
                       help='Default category ID for snapshots')
    parser.add_argument('--no-recursive', action='store_true',
                       help='Do not search subdirectories')
    parser.add_argument('--tags', default='',
                       help='Comma-separated tags to add to all snapshots')
    parser.add_argument('--parse-structure', action='store_true',
                       help='Parse cam[n]/[n]_MM-DD folder structure for metadata')
    parser.add_argument('--analyze-only', action='store_true',
                       help='Only analyze folder structure, do not import')
    
    args = parser.parse_args()
    
    # Ensure database is initialized
    print("📊 Initializing database...")
    init_database()
    
    # Analyze only mode
    if args.analyze_only:
        print("\n" + "=" * 60)
        print("FOLDER STRUCTURE ANALYSIS")
        print("=" * 60)
        structure = analyze_folder_structure(args.folder_path)
        print(f"\n📁 Folder: {args.folder_path}")
        print(f"   Structure type: {structure['type']}")
        print(f"   Cameras found: {len(structure['cameras'])}")
        print(f"   Has date folders: {structure['has_date_folders']}")
        
        if structure['cameras']:
            print(f"\n📷 Camera Details:")
            for cam in structure['cameras']:
                print(f"\n   {cam['camera_id']}:")
                for df in cam['date_folders']:
                    print(f"      └── {df['name']} (sequence: {df['sequence']}, date: {df['date_str']})")
        
        print("\n💡 To import with structure parsing, run:")
        print(f"   python batch_import.py \"{args.folder_path}\" --parse-structure")
        return
    
    # Show available categories if category option is used
    if args.category:
        categories = get_categories_tree()
        print("\n📁 Available Categories:")
        for cat in categories:
            indent = "  " if cat['parent_id'] else ""
            print(f"   {indent}[{cat['id']}] {cat['name']}")
        print()
    
    # Start import
    print("=" * 60)
    print("BATCH IMPORT STARTED")
    print("=" * 60)
    
    start_time = datetime.now()
    
    imported_count, errors = import_folder(
        folder_path=args.folder_path,
        source_name=args.source,
        default_category=args.category,
        recursive=not args.no_recursive,
        tags=args.tags,
        parse_structure=args.parse_structure
    )
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Print summary
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully imported: {imported_count} snapshots")
    print(f"⏱️  Time taken: {duration:.2f} seconds")
    
    if errors:
        print(f"❌ Errors: {len(errors)}")
        print("\nFirst 10 errors:")
        for error in errors[:10]:
            print(f"   - {error}")
    
    print("\n💡 Next steps:")
    print("   1. Run 'python app.py' to start the web interface")
    print("   2. Visit http://localhost:5000 to view imported snapshots")
    print("   3. Use the Query page to search and filter snapshots")
    print("   4. Generate time-lapse videos from the imported snapshots")
    print()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    main()
