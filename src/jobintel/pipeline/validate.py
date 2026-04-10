from __future__ import annotations

import logging

from jobintel.config import AppConfig
from jobintel.domain.models import JobPosting, ValidationIssue
from jobintel.storage.artifacts import (
    ArtifactPaths,
    read_jobs,
    write_jobs,
    write_json,
    write_validation_issues,
)
from jobintel.validation.dedupe import dedupe_jobs
from jobintel.validation.normalize import normalize_job
from jobintel.validation.rules import validate_jobs


def run_validation(
    config: AppConfig,
    paths: ArtifactPaths,
    logger: logging.Logger,
    jobs: list[JobPosting] | None = None,
) -> tuple[list[JobPosting], list[JobPosting], list[ValidationIssue], int]:
    collected_jobs = jobs or read_jobs(paths.collected_jobs_path)
    logger.info("Normalizing %s collected jobs", len(collected_jobs))
    normalized_jobs = [normalize_job(job) for job in collected_jobs]
    valid_jobs, quarantined_jobs, issues = validate_jobs(normalized_jobs)

    duplicates_removed = 0
    if config.dedupe.enabled:
        valid_jobs, dedupe_issues, duplicates_removed = dedupe_jobs(
            valid_jobs,
            similarity_threshold=config.dedupe.similarity_threshold,
        )
        issues.extend(dedupe_issues)

    write_jobs(paths.validated_jobs_path, valid_jobs)
    write_jobs(paths.quarantined_jobs_path, quarantined_jobs)
    write_validation_issues(paths.validation_issues_path, issues)
    write_json(
        paths.validation_summary_path,
        {
            "collected_jobs": len(collected_jobs),
            "valid_jobs": len(valid_jobs),
            "quarantined_jobs": len(quarantined_jobs),
            "duplicates_removed": duplicates_removed,
        },
    )
    return valid_jobs, quarantined_jobs, issues, duplicates_removed
