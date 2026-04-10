from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from jobintel.domain.models import JobPosting, ValidationIssue, ValidationSeverity


def validate_jobs(jobs: list[JobPosting]) -> tuple[list[JobPosting], list[JobPosting], list[ValidationIssue]]:
    valid_jobs: list[JobPosting] = []
    quarantined_jobs: list[JobPosting] = []
    issues: list[ValidationIssue] = []

    for job in jobs:
        job_issues = _validate_job(job)
        has_error = any(issue.severity == ValidationSeverity.ERROR for issue in job_issues)
        quality_score = _score_quality(job, job_issues)
        updated_job = job.model_copy(
            update={
                "validation_status": "invalid" if has_error else "valid",
                "quality_score": quality_score,
            }
        )
        issues.extend(job_issues)
        if has_error:
            quarantined_jobs.append(updated_job)
        else:
            valid_jobs.append(updated_job)
    return valid_jobs, quarantined_jobs, issues


def _validate_job(job: JobPosting) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if not job.company_name.strip():
        issues.append(_issue(job.job_id, "required_company", ValidationSeverity.ERROR, "company_name", "Company name is missing."))
    if not job.title_raw.strip():
        issues.append(_issue(job.job_id, "required_title", ValidationSeverity.ERROR, "title_raw", "Title is missing."))
    if not _is_valid_url(job.canonical_url):
        issues.append(_issue(job.job_id, "invalid_url", ValidationSeverity.ERROR, "canonical_url", "Canonical URL is missing or malformed."))
    if not job.description_text or len(job.description_text) < 40:
        issues.append(_issue(job.job_id, "thin_description", ValidationSeverity.WARNING, "description_text", "Description is unusually short."))
    if job.posted_at and job.posted_at > datetime.now(timezone.utc) + timedelta(days=1):
        issues.append(_issue(job.job_id, "future_posted_at", ValidationSeverity.ERROR, "posted_at", "Posted date is in the future."))
    if job.salary_min and job.salary_max and job.salary_min > job.salary_max:
        issues.append(_issue(job.job_id, "salary_inverted", ValidationSeverity.ERROR, "salary_min", "Salary range appears inverted."))
    if job.salary_min and job.salary_min > 1_500_000:
        issues.append(_issue(job.job_id, "salary_implausible", ValidationSeverity.WARNING, "salary_min", "Salary value is unusually high."))
    if not job.location_raw:
        issues.append(_issue(job.job_id, "missing_location", ValidationSeverity.WARNING, "location_raw", "Location is missing."))
    return issues


def _score_quality(job: JobPosting, issues: list[ValidationIssue]) -> float:
    score = 1.0
    if not job.description_text:
        score -= 0.15
    if not job.location_raw:
        score -= 0.1
    if not job.posted_at:
        score -= 0.05
    for issue in issues:
        score -= 0.15 if issue.severity == ValidationSeverity.ERROR else 0.05
    return round(max(score, 0.0), 2)


def _is_valid_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _issue(job_id: str, rule_id: str, severity: ValidationSeverity, field_name: str, message: str) -> ValidationIssue:
    return ValidationIssue(
        job_id=job_id,
        rule_id=rule_id,
        severity=severity,
        field_name=field_name,
        message=message,
    )
