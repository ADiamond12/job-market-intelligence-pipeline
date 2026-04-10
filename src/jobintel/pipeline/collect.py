from __future__ import annotations

import logging
from datetime import datetime, timezone

from jobintel.config import AppConfig
from jobintel.domain.models import CollectionStats, JobPosting
from jobintel.sources import build_adapter
from jobintel.storage.artifacts import ArtifactPaths, write_jobs, write_json


def run_collection(
    config: AppConfig,
    paths: ArtifactPaths,
    logger: logging.Logger,
) -> tuple[list[JobPosting], list[CollectionStats]]:
    collected_jobs: list[JobPosting] = []
    source_stats: list[CollectionStats] = []
    fetched_at = datetime.now(timezone.utc)

    for company in config.companies:
        if not company.enabled:
            continue
        adapter = build_adapter(company, config, logger)
        logger.info("Collecting jobs for %s via %s", company.name, company.source_type)
        try:
            result = adapter.collect(fetched_at=fetched_at)
        except Exception as exc:  # noqa: BLE001
            logger.error("Collection failed for %s: %s", company.name, exc)
            continue

        raw_snapshot_path = paths.raw_run_dir / f"{company.identifier}.json"
        write_json(raw_snapshot_path, result.payload)
        for job in result.jobs:
            collected_jobs.append(job.model_copy(update={"raw_snapshot_path": str(raw_snapshot_path)}))

        source_stats.append(
            CollectionStats(
                company_name=company.name,
                source_type=company.source_type,
                fetched_jobs=len(result.jobs),
                source_url=result.source_url,
                used_fixture=result.used_fixture,
            )
        )

    if not collected_jobs:
        raise RuntimeError("No jobs were collected. Check source identifiers or fixtures.")

    write_jobs(paths.collected_jobs_path, collected_jobs)
    return collected_jobs, source_stats
