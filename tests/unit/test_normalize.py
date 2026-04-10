from __future__ import annotations

from datetime import datetime, timezone

from jobintel.domain.models import JobPosting, SourceType
from jobintel.validation.normalize import (
    canonicalize_url,
    normalize_employment_type,
    normalize_job,
    parse_salary,
)


def test_canonicalize_url_removes_tracking_params() -> None:
    url = "https://example.com/job/1?utm_source=linkedin&ref=homepage#section"
    assert canonicalize_url(url) == "https://example.com/job/1?ref=homepage"


def test_parse_salary_extracts_range() -> None:
    payload = parse_salary(None, "Compensation: $120,000 - $145,000 annually plus bonus.")
    assert payload["salary_min"] == 120000
    assert payload["salary_max"] == 145000
    assert payload["salary_currency"] == "USD"
    assert payload["salary_period"] == "year"


def test_normalize_job_parses_location_and_hash() -> None:
    job = JobPosting(
        job_id="test-1",
        source_type=SourceType.GREENHOUSE,
        vendor="greenhouse",
        company_name="Acme",
        company_slug="acme",
        source_job_id="1",
        source_url="https://example.com/jobs",
        canonical_url="https://example.com/jobs/1?utm_source=x",
        title_raw="SENIOR DATA ENGINEER - REMOTE",
        location_raw="Remote, United States",
        posted_at=datetime.now(timezone.utc),
        description_html="<div><p>Build Python and SQL pipelines with Airflow.</p><p>Equal Opportunity Employer.</p></div>",
    )

    normalized = normalize_job(job)

    assert normalized.canonical_url == "https://example.com/jobs/1"
    assert normalized.title_normalized == "Senior Data Engineer"
    assert normalized.is_remote is True
    assert normalized.location_country == "United States"
    assert "Equal Opportunity Employer" not in (normalized.description_text or "")
    assert normalized.content_hash


def test_normalize_employment_type_ignores_internal_word() -> None:
    employment_type = normalize_employment_type(
        hint=None,
        title="Machine Learning Engineer",
        description="Design internal copilots and internal developer tools.",
    )

    assert employment_type == "unknown"
