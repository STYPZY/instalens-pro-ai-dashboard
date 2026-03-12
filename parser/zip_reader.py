import zipfile
import tempfile
import os


def read_instagram_zip(zip_path):

    if not zipfile.is_zipfile(zip_path):
        raise ValueError("Invalid ZIP file")

    temp_dir = tempfile.mkdtemp()

    with zipfile.ZipFile(zip_path, 'r') as z:
        for member in z.infolist():
            name = member.filename
            if ".." in name or name.startswith("/"):
                continue
            try:
                z.extract(member, temp_dir)
            except Exception:
                continue

    # Print file tree to console for debugging
    print("\n=== EXTRACTED ZIP FILE TREE ===")
    for root, dirs, files in os.walk(temp_dir):
        level = root.replace(temp_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for f in files:
            print(f"{subindent}{f}")
    print("=== END FILE TREE ===\n")

    return temp_dir