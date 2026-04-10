from __future__ import annotations

from difflib import SequenceMatcher

from jobintel.domain.models import JobPosting, ValidationIssue, ValidationSeverity


def dedupe_jobs(
    jobs: list[JobPosting],
    similarity_threshold: float,
) -> tuple[list[JobPosting], list[ValidationIssue], int]:
    curated_jobs: list[JobPosting] = []
    issues: list[ValidationIssue] = []
    duplicates_removed = 0

    for candidate in jobs:
        duplicate_of = _find_duplicate(candidate, curated_jobs, similarity_threshold)
        if duplicate_of:
            duplicates_removed += 1
            issues.append(
                ValidationIssue(
                    job_id=candidate.job_id,
                    rule_id="duplicate_detected",
                    severity=ValidationSeverity.INFO,
                    field_name="job_id",
                    message=f"Removed as duplicate of {duplicate_of.job_id}.",
                )
            )
            continue
        curated_jobs.append(candidate)

    return curated_jobs, issues, duplicates_removed


def _find_duplicate(
    candidate: JobPosting,
    existing_jobs: list[JobPosting],
    similarity_threshold: float,
) -> JobPosting | None:
    for existing in existing_jobs:
        if candidate.canonical_url == existing.canonical_url:
            return existing
        if candidate.content_hash and candidate.content_hash == existing.content_hash:
            return existing
        if candidate.company_slug != existing.company_slug:
            continue
        if candidate.title_normalized != existing.title_normalized:
            continue
        similarity = _description_similarity(candidate.description_text or "", existing.description_text or "")
        if similarity >= similarity_threshold:
            return existing
    return None


def _description_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(a=left[:750], b=right[:750]).ratio()
