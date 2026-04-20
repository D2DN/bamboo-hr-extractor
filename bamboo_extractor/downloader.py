import csv
import re
from datetime import datetime
from pathlib import Path

import click

from .client import BambooHRClient

_CONTENT_TYPE_EXT = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/rtf": ".rtf",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def _safe_name(name: str) -> str:
    return re.sub(r'[^\w\-.]', '_', name).strip('_') or "unknown"


def _ext_from_headers(headers: dict, fallback: str = ".pdf") -> str:
    cd = headers.get("Content-Disposition", "")
    match = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^"\';\r\n]+)', cd, re.IGNORECASE)
    if match:
        ext = Path(match.group(1).strip()).suffix
        if ext:
            return ext.lower()

    ct = headers.get("Content-Type", "").split(";")[0].strip().lower()
    if ct in _CONTENT_TYPE_EXT:
        return _CONTENT_TYPE_EXT[ct]

    return fallback


def _get_names(app: dict, details: dict) -> tuple[str, str]:
    """Extract first/last name from applicant sub-object or root."""
    applicant = details.get("applicant") or app.get("applicant") or {}
    first = applicant.get("firstName") or details.get("firstName") or app.get("firstName") or "unknown"
    last = applicant.get("lastName") or details.get("lastName") or app.get("lastName") or "unknown"
    return _safe_name(first), _safe_name(last)


def _build_filename(app: dict, details: dict, file_type: str, ext: str) -> str:
    first, last = _get_names(app, details)
    app_id = app.get("id", details.get("id", ""))
    return f"{last}_{first}_{app_id}_{file_type}{ext}"


def download_resumes(
    client: BambooHRClient,
    applications: list[dict],
    resumes_dir: str,
) -> tuple[dict[str, int], dict[str | int, dict]]:
    """Download CVs and return (stats, file_map).

    file_map: { application_id -> {"resume_path": "..."} }
    Errors are written to download_errors.csv in resumes_dir.
    """
    output_dir = Path(resumes_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    error_log_path = output_dir / "download_errors.csv"
    error_rows: list[dict] = []

    stats = {"downloaded": 0, "skipped": 0, "errors": 0}
    file_map: dict[str | int, dict] = {}

    for app in applications:
        app_id = app.get("id")
        if not app_id:
            continue

        # Applications are already enriched with details — no extra API call needed.
        details = app

        file_map.setdefault(app_id, {})

        resume_file_id = details.get("resumeFileId") or app.get("resumeFileId")
        if not resume_file_id:
            continue

        existing = list(output_dir.glob(f"*_{app_id}_resume.*"))
        if existing:
            click.echo(f"  [SKIP] {existing[0].name} already exists")
            stats["skipped"] += 1
            file_map[app_id]["resume_path"] = str(existing[0])
            continue

        try:
            content, headers = client.download_file(app_id, resume_file_id)
            ext = _ext_from_headers(headers)
            filename = _build_filename(app, details, "resume", ext)
            dest = output_dir / filename
            dest.write_bytes(content)
            click.echo(f"  [OK]   {filename}")
            stats["downloaded"] += 1
            file_map[app_id]["resume_path"] = str(dest)
        except Exception as e:
            msg = str(e)
            click.echo(f"  [ERR]  application {app_id} resume: {msg}")
            first, last = _get_names(app, details)
            stats["errors"] += 1
            error_rows.append({"application_id": app_id, "first_name": first, "last_name": last, "file_type": "resume", "error": msg})

    if error_rows:
        with error_log_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["application_id", "last_name", "first_name", "file_type", "error", "timestamp"])
            writer.writeheader()
            ts = datetime.now().isoformat(timespec="seconds")
            for row in error_rows:
                writer.writerow({**row, "timestamp": ts})
        click.echo(f"  Error log written → {error_log_path}")

    return stats, file_map


def enrich_with_file_paths(applications: list[dict], file_map: dict) -> list[dict]:
    """Inject resume_path / cover_letter_path into each application dict."""
    enriched = []
    for app in applications:
        app_id = app.get("id")
        paths = file_map.get(app_id, {})
        enriched.append({**app, **paths})
    return enriched
