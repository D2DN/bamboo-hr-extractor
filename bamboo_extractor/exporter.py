import csv
import json
import sys
from datetime import datetime
from pathlib import Path


def _flatten(data: dict, prefix: str = "") -> dict:
    """Recursively flatten a nested dict."""
    result = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten(value, full_key))
        elif isinstance(value, list):
            result[full_key] = json.dumps(value)
        else:
            result[full_key] = value
    return result


def export_to_csv(applications: list[dict], output_file: str) -> Path:
    if not applications:
        print("No applications to export.")
        return Path(output_file)

    flat_apps = [_flatten(app) for app in applications]
    fieldnames = sorted({key for app in flat_apps for key in app.keys()})

    path = Path(f"{output_file}.csv")
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flat_apps)

    return path


def export_to_json(applications: list[dict], output_file: str) -> Path:
    path = Path(f"{output_file}.json")
    with path.open("w", encoding="utf-8") as f:
        json.dump(applications, f, ensure_ascii=False, indent=2)
    return path


def export(applications: list[dict], output_format: str, output_file: str) -> Path:
    if output_format == "json":
        return export_to_json(applications, output_file)
    return export_to_csv(applications, output_file)
