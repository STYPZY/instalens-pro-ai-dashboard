import hashlib
from PIL import Image
import imagehash


def file_hashes(path):

    md5 = hashlib.md5()
    sha256 = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            data = f.read(8192)
            if not data:
                break
            md5.update(data)
            sha256.update(data)

    return {
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest()
    }


def perceptual_hash(path):

    try:
        img = Image.open(path)
        phash = imagehash.phash(img)
        return str(phash)
    except Exception:
        return None