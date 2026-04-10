from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from jobintel.domain.models import JobPosting, ValidationIssue


def build_quality_report(
    collected_jobs: list[JobPosting],
    curated_jobs: list[JobPosting],
    quarantined_jobs: list[JobPosting],
    validation_issues: list[ValidationIssue],
    duplicates_removed: int,
) -> dict[str, Any]:
    severity_counts = Counter(issue.severity for issue in validation_issues)
    rule_counts = Counter(issue.rule_id for issue in validation_issues)
    source_counts = Counter(job.vendor for job in curated_jobs)

    completeness = {
        "description_text_pct": _pct(curated_jobs, lambda job: bool(job.description_text)),
        "posted_at_pct": _pct(curated_jobs, lambda job: job.posted_at is not None),
        "location_pct": _pct(curated_jobs, lambda job: bool(job.location_raw)),
        "salary_pct": _pct(curated_jobs, lambda job: job.salary_min is not None),
    }

    return {
        "collected_jobs": len(collected_jobs),
        "published_jobs": len(curated_jobs),
        "quarantined_jobs": len(quarantined_jobs),
        "duplicates_removed": duplicates_removed,
        "issue_counts_by_severity": dict(severity_counts),
        "issue_counts_by_rule": dict(rule_counts),
        "completeness": completeness,
        "source_coverage": dict(source_counts),
    }


def _pct(jobs: list[JobPosting], predicate: Callable[[JobPosting], bool]) -> float:
    if not jobs:
        return 0.0
    matching = sum(1 for job in jobs if predicate(job))
    return round((matching / len(jobs)) * 100, 1)
