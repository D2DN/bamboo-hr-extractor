import re
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

    file_map: { application_id -> {"resume_path": "...", "cover_letter_path": "..."} }
    """
    output_dir = Path(resumes_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = {"downloaded": 0, "skipped": 0, "errors": 0}
    file_map: dict[str | int, dict] = {}

    for app in applications:
        app_id = app.get("id")
        if not app_id:
            continue

        try:
            details = client.get_application_details(app_id)
        except Exception as e:
            click.echo(f"  [WARN] Could not fetch details for application {app_id}: {e}")
            stats["errors"] += 1
            continue

        file_map.setdefault(app_id, {})

        files_to_download = []

        resume_file_id = details.get("resumeFileId") or app.get("resumeFileId")
        if resume_file_id:
            files_to_download.append(("resume", resume_file_id))

        for file_type, file_id in files_to_download:
            path_key = f"{file_type}_path"

            existing = list(output_dir.glob(f"*_{app_id}_{file_type}.*"))
            if existing:
                click.echo(f"  [SKIP] {existing[0].name} already exists")
                stats["skipped"] += 1
                file_map[app_id][path_key] = str(existing[0])
                continue

            try:
                content, headers = client.download_file(app_id, file_id)
                ext = _ext_from_headers(headers)
                filename = _build_filename(app, details, file_type, ext)
                dest = output_dir / filename
                dest.write_bytes(content)
                click.echo(f"  [OK]   {filename}")
                stats["downloaded"] += 1
                file_map[app_id][path_key] = str(dest)
            except Exception as e:
                click.echo(f"  [ERR]  application {app_id} {file_type}: {e}")
                stats["errors"] += 1

    return stats, file_map


def enrich_with_file_paths(applications: list[dict], file_map: dict) -> list[dict]:
    """Inject resume_path / cover_letter_path into each application dict."""
    enriched = []
    for app in applications:
        app_id = app.get("id")
        paths = file_map.get(app_id, {})
        enriched.append({**app, **paths})
    return enriched
