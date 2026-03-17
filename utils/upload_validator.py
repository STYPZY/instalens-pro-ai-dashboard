import os
import zipfile
import logging

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 1024 * 1024 * 1024  # 1GB
MAX_UNCOMPRESSED_SIZE = 5 * 1024 * 1024 * 1024  # 5GB


def validate_upload(file):
    """Check that a file object was actually submitted."""
    if not file or not file.filename:
        raise ValueError("No file uploaded")


def validate_file_size(path):
    """Check saved file size against the 1GB limit."""
    try:
        size = os.path.getsize(path)
    except OSError as e:
        raise ValueError(f"Could not read file size: {str(e)}")
    
    if size == 0:
        raise ValueError("Uploaded file is empty.")
    
    if size > MAX_UPLOAD_SIZE:
        size_mb = size / (1024 * 1024)
        raise ValueError(f"Upload exceeds 1GB limit (file is {size_mb:.1f} MB).")


def validate_zip(zip_path):
    """Validate that the file is a proper ZIP archive."""
    if not os.path.exists(zip_path):
        raise ValueError("Uploaded file not found on server.")
    
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("Invalid ZIP archive — please upload your Instagram or Snapchat export ZIP.")


def check_zip_safety(zip_path):
    """Prevent ZIP bomb attacks and validate contents."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            total_uncompressed = 0
            file_count = 0

            for info in z.infolist():
                file_count += 1
                total_uncompressed += info.file_size

                # Check compression ratio for suspicious files
                if info.compress_size > 0:
                    ratio = info.file_size / info.compress_size
                    if ratio > 100:
                        logger.warning(f"Suspicious compression ratio: {ratio} for {info.filename}")
                        raise ValueError(f"Possible ZIP bomb detected in file: {info.filename}")

            # Check total uncompressed size
            if total_uncompressed > MAX_UNCOMPRESSED_SIZE:
                size_gb = total_uncompressed / (1024 * 1024 * 1024)
                raise ValueError(f"ZIP expands too large ({size_gb:.1f} GB). Maximum is 5GB.")
            
            if file_count == 0:
                raise ValueError("ZIP file is empty.")
            
            logger.info(f"ZIP validation passed: {file_count} files, {total_uncompressed / (1024*1024):.1f} MB uncompressed")
            
    except zipfile.BadZipFile as e:
        raise ValueError(f"Corrupted ZIP file: {str(e)}")
    except Exception as e:
        raise ValueError(f"ZIP validation error: {str(e)}")