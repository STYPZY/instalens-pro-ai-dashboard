import json
import os


def debug_snapchat_export(folder):
    report = []

    report.append(f"=== FOLDER SCAN: {folder} ===")

    for root, dirs, files in os.walk(folder):
        rel = root.replace(folder, "").strip("/\\") or "ROOT"
        for f in files:
            report.append(f"  [{rel}] {f}")

    report.append("\n=== JSON FILE CONTENTS (top-level keys) ===")

    for root, dirs, files in os.walk(folder):
        for f in files:
            if not f.endswith(".json"):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    keys = list(data.keys())
                    sample = {}
                    for k in keys[:3]:
                        v = data[k]
                        if isinstance(v, list) and v:
                            sample[k] = f"list[{len(v)}] first_item_keys={list(v[0].keys()) if isinstance(v[0], dict) else type(v[0]).__name__}"
                        elif isinstance(v, dict):
                            sample[k] = f"dict keys={list(v.keys())[:5]}"
                        else:
                            sample[k] = repr(v)[:80]
                    report.append(f"\n  FILE: {f}")
                    report.append(f"  TOP KEYS: {keys}")
                    report.append(f"  SAMPLE: {sample}")
                elif isinstance(data, list):
                    report.append(f"\n  FILE: {f}")
                    report.append(f"  TYPE: list[{len(data)}]")
                    if data and isinstance(data[0], dict):
                        report.append(f"  FIRST ITEM KEYS: {list(data[0].keys())}")
            except Exception as e:
                report.append(f"\n  FILE: {f} — ERROR: {e}")

    return "\n".join(report)