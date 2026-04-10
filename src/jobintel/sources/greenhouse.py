from __future__ import annotations

from datetime import datetime
from typing import Any

from jobintel.domain.models import JobPosting, SourceType
from jobintel.sources.base import BaseSourceAdapter


class GreenhouseAdapter(BaseSourceAdapter):
    vendor = "greenhouse"

    def get_endpoint(self) -> str:
        return f"https://boards-api.greenhouse.io/v1/boards/{self.company.identifier}/jobs?content=true"

    def parse_payload(
        self,
        payload: dict[str, Any] | list[dict[str, Any]],
        fetched_at: datetime,
    ) -> list[JobPosting]:
        jobs_payload = payload.get("jobs", []) if isinstance(payload, dict) else payload
        parsed_jobs: list[JobPosting] = []
        for item in jobs_payload:
            source_job_id = str(item.get("id"))
            location = item.get("location") or {}
            location_name = location.get("name") if isinstance(location, dict) else str(location or "")
            department = None
            departments = item.get("departments") or []
            if departments and isinstance(departments[0], dict):
                department = departments[0].get("name")
            metadata = item.get("metadata") or []
            salary_raw = self._metadata_value(metadata, "salary")
            employment_hint = self._metadata_value(metadata, "employment")
            description_html = item.get("content") or ""
            canonical_url = item.get("absolute_url") or item.get("url") or self.get_endpoint()

            parsed_jobs.append(
                JobPosting(
                    job_id=f"{self.vendor}:{self.company.identifier}:{source_job_id}",
                    source_type=SourceType.GREENHOUSE,
                    vendor=self.vendor,
                    company_name=self.company.name,
                    company_slug=self.company.identifier,
                    source_job_id=source_job_id,
                    source_url=self.get_endpoint(),
                    canonical_url=canonical_url,
                    apply_url=canonical_url,
                    title_raw=item.get("title") or "Unknown title",
                    department=department,
                    location_raw=location_name or None,
                    posted_at=self._parse_datetime(item.get("updated_at") or item.get("created_at")),
                    first_seen_at=fetched_at,
                    last_seen_at=fetched_at,
                    description_html=description_html,
                    description_text=self.html_to_text(description_html),
                    salary_raw=salary_raw,
                    metadata={"employment_hint": employment_hint},
                )
            )
        return parsed_jobs

    @staticmethod
    def _metadata_value(metadata: list[dict[str, Any]], key_fragment: str) -> str | None:
        for entry in metadata:
            name = str(entry.get("name", "")).lower()
            if key_fragment.lower() in name:
                value = entry.get("value")
                if isinstance(value, list):
                    return ", ".join(str(item) for item in value if item)
                if value:
                    return str(value)
        return None

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
