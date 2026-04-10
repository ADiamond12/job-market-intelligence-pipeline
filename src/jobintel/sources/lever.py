from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from jobintel.domain.models import JobPosting, SourceType
from jobintel.sources.base import BaseSourceAdapter


class LeverAdapter(BaseSourceAdapter):
    vendor = "lever"

    def get_endpoint(self) -> str:
        return f"https://api.lever.co/v0/postings/{self.company.identifier}?mode=json"

    def parse_payload(
        self,
        payload: dict[str, Any] | list[dict[str, Any]],
        fetched_at: datetime,
    ) -> list[JobPosting]:
        jobs_payload = payload if isinstance(payload, list) else payload.get("postings", [])
        parsed_jobs: list[JobPosting] = []
        for item in jobs_payload:
            source_job_id = str(item.get("id"))
            categories = item.get("categories") or {}
            description_html = self._compose_description_html(item)
            canonical_url = item.get("hostedUrl") or item.get("applyUrl") or self.get_endpoint()
            parsed_jobs.append(
                JobPosting(
                    job_id=f"{self.vendor}:{self.company.identifier}:{source_job_id}",
                    source_type=SourceType.LEVER,
                    vendor=self.vendor,
                    company_name=self.company.name,
                    company_slug=self.company.identifier,
                    source_job_id=source_job_id,
                    source_url=self.get_endpoint(),
                    canonical_url=canonical_url,
                    apply_url=item.get("applyUrl"),
                    title_raw=item.get("text") or "Unknown title",
                    department=(categories.get("department") or categories.get("team")),
                    location_raw=categories.get("location"),
                    posted_at=self._parse_timestamp(item.get("createdAt")),
                    first_seen_at=fetched_at,
                    last_seen_at=fetched_at,
                    description_html=description_html,
                    description_text=self.html_to_text(description_html),
                    salary_raw=item.get("salaryDescription"),
                    metadata={"commitment": categories.get("commitment")},
                )
            )
        return parsed_jobs

    @staticmethod
    def _compose_description_html(item: dict[str, Any]) -> str:
        parts: list[str] = []
        if item.get("description"):
            parts.append(str(item["description"]))
        for block in item.get("lists") or []:
            text_items = "".join(f"<li>{entry}</li>" for entry in block.get("content", []))
            parts.append(f"<section><h3>{block.get('text', 'Section')}</h3><ul>{text_items}</ul></section>")
        if item.get("additional"):
            parts.append(str(item["additional"]))
        return "\n".join(parts)

    @staticmethod
    def _parse_timestamp(value: int | float | str | None) -> datetime | None:
        if value is None:
            return None
        try:
            if isinstance(value, str) and value.isdigit():
                value = int(value)
            if isinstance(value, (int, float)):
                if value > 10_000_000_000:
                    value = value / 1000
                return datetime.fromtimestamp(value, tz=UTC)
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
