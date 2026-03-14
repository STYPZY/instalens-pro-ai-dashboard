import os
import zipfile

MAX_UPLOAD_SIZE = 1024 * 1024 * 1024  # 1GB


def validate_upload(file):
    """Check that a file object was actually submitted."""
    if not file or not file.filename:
        raise ValueError("No file uploaded")


def validate_file_size(path):
    """Check saved file size against the 1GB limit."""
    size = os.path.getsize(path)
    if size == 0:
        raise ValueError("Uploaded file is empty.")
    if size > MAX_UPLOAD_SIZE:
        raise ValueError("Upload exceeds 1GB limit.")


def validate_zip(zip_path):
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("Invalid ZIP archive — please upload your Instagram export ZIP.")


def check_zip_safety(zip_path):
    """Prevent ZIP bomb attacks."""
    with zipfile.ZipFile(zip_path, 'r') as z:

        total_uncompressed = 0

        for info in z.infolist():

            total_uncompressed += info.file_size

            if info.compress_size == 0:
                continue

            ratio = info.file_size / info.compress_size

            if ratio > 100:
                raise ValueError("Possible ZIP bomb detected.")

        if total_uncompressed > 5 * 1024 * 1024 * 1024:
            raise ValueError("ZIP expands too large.")