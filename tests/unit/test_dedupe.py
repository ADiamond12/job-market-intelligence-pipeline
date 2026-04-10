from __future__ import annotations

from datetime import datetime, timezone

from jobintel.domain.models import JobPosting, SourceType
from jobintel.validation.dedupe import dedupe_jobs
from jobintel.validation.normalize import normalize_job


def _job(job_id: str, url: str, description: str) -> JobPosting:
    return normalize_job(
        JobPosting(
            job_id=job_id,
            source_type=SourceType.GREENHOUSE,
            vendor="greenhouse",
            company_name="Acme",
            company_slug="acme",
            source_job_id=job_id,
            source_url="https://example.com/jobs",
            canonical_url=url,
            title_raw="Data Engineer",
            location_raw="Remote, United States",
            posted_at=datetime.now(timezone.utc),
            description_html=f"<p>{description}</p>",
        )
    )


def test_dedupe_jobs_removes_similar_duplicates() -> None:
    jobs = [
        _job("1", "https://example.com/jobs/1", "Build Python pipelines and SQL models with Airflow."),
        _job("2", "https://example.com/jobs/2", "Build Python pipelines and SQL models with Airflow."),
    ]

    curated, issues, duplicates_removed = dedupe_jobs(jobs, similarity_threshold=0.8)

    assert len(curated) == 1
    assert duplicates_removed == 1
    assert issues[0].rule_id == "duplicate_detected"
