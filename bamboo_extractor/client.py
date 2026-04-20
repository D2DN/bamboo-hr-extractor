import requests
from requests.auth import HTTPBasicAuth
from typing import Any

from .config import Config


class BambooHRClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(config.api_key, "x")
        self.session.headers.update({"Accept": "application/json"})

    def _get(self, path: str, params: dict | None = None) -> Any:
        url = f"{self.config.base_url}{path}"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def _get_binary(self, url: str) -> tuple[bytes, dict]:
        response = self.session.get(url, headers={"Accept": "*/*"})
        response.raise_for_status()
        return response.content, dict(response.headers)

    def get_applications(
        self,
        page: int = 1,
        job_id: int | None = None,
        application_status: str = "ALL",
        new_since: str | None = None,
        sort_by: str = "created_date",
        sort_order: str = "DESC",
    ) -> dict:
        params: dict = {
            "page": page,
            "applicationStatus": application_status,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        if job_id:
            params["jobId"] = job_id
        if new_since:
            params["newSince"] = new_since

        return self._get("/applicant_tracking/applications", params)

    def get_all_applications(self) -> list[dict]:
        applications: list[dict] = []
        page = 1

        while True:
            data = self.get_applications(
                page=page,
                job_id=int(self.config.job_id) if self.config.job_id else None,
                application_status=self.config.application_status,
                new_since=self.config.new_since,
            )

            results = data.get("applications", [])
            applications.extend(results)

            if data.get("paginationComplete", False) or not results:
                break

            page += 1

        return applications

    def get_application_details(self, application_id: int | str) -> dict:
        return self._get(f"/applicant_tracking/applications/{application_id}")

    def get_application_comments(self, application_id: int | str) -> list[dict]:
        try:
            result = self._get(f"/applicant_tracking/applications/{application_id}/comments")
            if isinstance(result, list):
                return result
            return result.get("comments", [])
        except Exception:
            return []

    def enrich_with_details(self, applications: list[dict]) -> list[dict]:
        """Merge full application details into each application dict."""
        enriched = []
        for app in applications:
            app_id = app.get("id")
            try:
                details = self.get_application_details(app_id)
                enriched.append({**app, **details})
            except Exception:
                enriched.append(app)
        return enriched

    def download_file(self, application_id: int | str, file_id: int | str) -> tuple[bytes, dict]:
        """Download a file by application ID and file ID. Returns (content, headers)."""
        url = f"{self.config.base_url}/applicant_tracking/applications/{application_id}/files/{file_id}"
        return self._get_binary(url)

    def get_job_ids_by_title(self, title_fragment: str) -> list[int]:
        """Return IDs of jobs whose title contains title_fragment (case-insensitive)."""
        jobs = self.get_jobs()
        fragment = title_fragment.lower()
        matched = []
        for j in jobs:
            t = j.get("title", {})
            label = (t.get("label") if isinstance(t, dict) else t) or ""
            if fragment in label.lower():
                matched.append(j["id"])
        return matched

    def get_jobs(self) -> list[dict]:
        return self._get("/applicant_tracking/jobs")
