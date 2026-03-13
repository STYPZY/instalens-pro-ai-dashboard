import hashlib
import subprocess
import json


def file_hash(path, algo):

    h = hashlib.new(algo)

    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


def extract_metadata(path):

    try:

        result = subprocess.run(
            ["exiftool", "-json", path],
            capture_output=True,
            text=True
        )

        data = json.loads(result.stdout)

        if data:
            return data[0]

    except Exception:
        pass

    return {}


def analyze_metadata(path):

    report = {}

    report["md5"] = file_hash(path, "md5")
    report["sha1"] = file_hash(path, "sha1")
    report["sha256"] = file_hash(path, "sha256")

    report["metadata"] = extract_metadata(path)

    return report