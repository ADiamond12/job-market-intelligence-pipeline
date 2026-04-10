from __future__ import annotations

import logging

from jobintel.config import AppConfig
from jobintel.domain.models import JobPosting
from jobintel.enrichment.classification import enrich_jobs
from jobintel.storage.artifacts import ArtifactPaths, read_jobs, write_jobs, write_jobs_csv


def run_enrichment(
    config: AppConfig,
    paths: ArtifactPaths,
    logger: logging.Logger,
    jobs: list[JobPosting] | None = None,
) -> list[JobPosting]:
    validated_jobs = jobs or read_jobs(paths.validated_jobs_path)
    logger.info("Enriching %s validated jobs", len(validated_jobs))
    enriched = enrich_jobs(validated_jobs, config.ai, logger)
    write_jobs(paths.curated_jobs_json_path, enriched)
    write_jobs_csv(paths.curated_jobs_csv_path, enriched)
    return enriched
