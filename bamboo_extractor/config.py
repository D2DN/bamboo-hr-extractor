import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    api_key: str = field(default_factory=lambda: os.getenv("BAMBOO_API_KEY", ""))
    company_domain: str = field(default_factory=lambda: os.getenv("BAMBOO_COMPANY_DOMAIN", ""))
    application_status: str = field(default_factory=lambda: os.getenv("BAMBOO_APPLICATION_STATUS", "ALL"))
    job_id: str | None = field(default_factory=lambda: os.getenv("BAMBOO_JOB_ID"))
    job_title: str | None = field(default_factory=lambda: os.getenv("BAMBOO_JOB_TITLE"))
    new_since: str | None = field(default_factory=lambda: os.getenv("BAMBOO_NEW_SINCE"))
    output_format: str = field(default_factory=lambda: os.getenv("BAMBOO_OUTPUT_FORMAT", "csv").lower())
    output_file: str = field(default_factory=lambda: os.getenv("BAMBOO_OUTPUT_FILE", "candidates_export"))
    resumes_dir: str | None = field(default_factory=lambda: os.getenv("BAMBOO_RESUMES_DIR"))

    @property
    def base_url(self) -> str:
        return f"https://api.bamboohr.com/api/gateway.php/{self.company_domain}/v1"

    @property
    def web_base_url(self) -> str:
        return f"https://{self.company_domain}.bamboohr.com"

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("BAMBOO_API_KEY is required")
        if not self.company_domain:
            raise ValueError("BAMBOO_COMPANY_DOMAIN is required")
        if self.output_format not in ("csv", "json"):
            raise ValueError("BAMBOO_OUTPUT_FORMAT must be 'csv' or 'json'")
