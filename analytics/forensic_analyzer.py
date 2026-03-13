import hashlib
import subprocess
import json
import mimetypes


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


def detect_platform(metadata):

    software = str(metadata.get("Software", "")).lower()
    encoder = str(metadata.get("Encoder", "")).lower()

    if "instagram" in software:
        return "Instagram"

    if "whatsapp" in software:
        return "WhatsApp"

    if "telegram" in software:
        return "Telegram"

    if "tiktok" in software:
        return "TikTok"

    if "obs" in encoder or "screen" in software:
        return "Screen Recording"

    return "Unknown"


def extract_location(metadata):

    lat = metadata.get("GPSLatitude")
    lon = metadata.get("GPSLongitude")

    if lat and lon:

        return {
            "latitude": lat,
            "longitude": lon,
            "map_link": f"https://maps.google.com/?q={lat},{lon}"
        }

    return None


def get_video_metadata(path):

    try:

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                path
            ],
            capture_output=True,
            text=True
        )

        return json.loads(result.stdout)

    except Exception:
        return {}


def analyze_file(path):

    report = {}

    mime = mimetypes.guess_type(path)[0] or ""

    report["type"] = "video" if "video" in mime else "photo"

    report["md5"] = file_hash(path, "md5")
    report["sha1"] = file_hash(path, "sha1")
    report["sha256"] = file_hash(path, "sha256")

    metadata = extract_metadata(path)

    report["metadata"] = metadata

    report["location"] = extract_location(metadata)

    report["platform_guess"] = detect_platform(metadata)

    if report["type"] == "video":
        report["video_info"] = get_video_metadata(path)
    else:
        report["video_info"] = None

    return report