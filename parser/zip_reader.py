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

    return temp_dir