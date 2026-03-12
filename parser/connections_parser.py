from parser.json_parser import parse_json_export
from parser.html_parser import parse_html_export
from parser.data_normalizer import normalize_data


def detect_export_type(folder):

    import os

    json_files = []
    html_files = []

    for root, dirs, files in os.walk(folder):
        for f in files:

            if f.endswith(".json"):
                json_files.append(f)

            if f.endswith(".html"):
                html_files.append(f)

    if json_files:
        return "json"

    if html_files:
        return "html"

    return "unknown"


def parse_connections(folder):

    export_type = detect_export_type(folder)

    if export_type == "json":
        parsed = parse_json_export(folder)

    elif export_type == "html":
        parsed = parse_html_export(folder)

    else:
        parsed = {}

    normalized = normalize_data(parsed)

    return normalized, export_type