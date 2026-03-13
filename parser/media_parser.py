import os
import re


IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.bmp', '.tiff'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.wmv', '.flv', '.3gp'}

# Exact folder name → category label
CATEGORY_MAP = {
    'posts':            'Posts',
    'archived_posts':   'Archived Posts',
    'stories':          'Stories',
    'reels':            'Reels',
    'direct':           'Direct Messages',
    'profile':          'Profile',
    'recently_deleted': 'Recently Deleted',
}


def categorize_path(path):
    """Match only the direct parent folder name, not subfolders like 201803."""
    norm = path.replace('\\', '/')
    parts = norm.rstrip('/').split('/')
    # Check direct folder and its parent (to handle dated subfolders like posts/201811)
    for part in reversed(parts):
        part_lower = part.lower()
        if part_lower in CATEGORY_MAP:
            return CATEGORY_MAP[part_lower]
    return 'Other'


def parse_media_stats(folder):

    stats = {
        'photos': 0,
        'videos': 0,
        'total_size_bytes': 0,
        'by_year': {},
        'by_category': {},   # {'Posts': {'photos':10,'videos':3}, 'Stories': {...}}
        'largest_files': [],
        'total': 0,
        'total_size_mb': 0,
    }

    # Find media/ root folder
    media_root = None
    for root, dirs, files in os.walk(folder):
        norm = root.replace('\\', '/').lower()
        if norm.endswith('/media') or '/media/' in norm + '/':
            # Make sure it's the top-level media folder
            rel = root.replace(folder, '').replace('\\', '/').strip('/')
            if rel.count('/') <= 1:
                media_root = root
                break

    scan_root = media_root if media_root else folder

    all_files = []

    for root, dirs, files in os.walk(scan_root):
        category = categorize_path(root)
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
                continue
            path = os.path.join(root, f)
            try:
                size = os.path.getsize(path)
            except Exception:
                size = 0
            ftype = 'photo' if ext in IMAGE_EXTS else 'video'

            # Totals
            if ftype == 'photo':
                stats['photos'] += 1
            else:
                stats['videos'] += 1
            stats['total_size_bytes'] += size

            # By category
            if category not in stats['by_category']:
                stats['by_category'][category] = {'photos': 0, 'videos': 0}
            stats['by_category'][category][ftype + 's'] += 1

            # By year
            date = _extract_date(f)
            if date:
                year = date[:4]
                if year not in stats['by_year']:
                    stats['by_year'][year] = {'photos': 0, 'videos': 0}
                stats['by_year'][year][ftype + 's'] += 1

            all_files.append({'name': f, 'size': size, 'type': ftype})

    # Top 5 largest
    all_files.sort(key=lambda x: x['size'], reverse=True)
    stats['largest_files'] = all_files[:5]
    stats['total'] = stats['photos'] + stats['videos']
    stats['total_size_mb'] = round(stats['total_size_bytes'] / (1024 * 1024), 1)

    return stats


def _extract_date(filename):
    m = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
    if m:
        y, mo = m.group(1), m.group(2)
        if 2000 <= int(y) <= 2030 and 1 <= int(mo) <= 12:
            return f"{y}-{mo}"
    return None


def get_media_files(folder, category=None, limit=100):
    """Return list of actual media file paths for display."""
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic'}

    media_root = None
    for root, dirs, files in os.walk(folder):
        norm = root.replace('\\', '/').lower()
        rel = root.replace(folder, '').replace('\\', '/').strip('/')
        if (norm.endswith('/media') or '/media/' in norm + '/') and rel.count('/') <= 1:
            media_root = root
            break

    scan_root = media_root if media_root else folder
    results = []

    for root, dirs, files in os.walk(scan_root):
        cat = categorize_path(root)
        if category and cat != category:
            continue
        for f in sorted(files):
            ext = os.path.splitext(f)[1].lower()
            if ext not in IMAGE_EXTS:
                continue
            results.append({
                'path': os.path.join(root, f),
                'name': f,
                'category': cat,
            })
            if len(results) >= limit:
                return results

    return results