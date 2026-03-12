import os
from utils.hash_utils import file_hashes, perceptual_hash
from parser.media_metadata import extract_metadata


def analyze_media(path):

    report = {}

    report["filename"] = os.path.basename(path)

    report["hashes"] = file_hashes(path)

    report["perceptual_hash"] = perceptual_hash(path)

    report["metadata"] = extract_metadata(path)

    return report