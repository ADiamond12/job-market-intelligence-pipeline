from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from jobintel.config import AppConfig
from jobintel.domain.models import JobPosting, ValidationIssue


@dataclass(slots=True)
class ArtifactPaths:
    run_id: str
    raw_run_dir: Path
    processed_dir: Path
    reports_dir: Path
    manifests_dir: Path
    history_dir: Path
    logs_dir: Path
    history_db_path: Path
    collected_jobs_path: Path
    validated_jobs_path: Path
    quarantined_jobs_path: Path
    curated_jobs_json_path: Path
    curated_jobs_csv_path: Path
    validation_issues_path: Path
    validation_summary_path: Path
    delta_report_path: Path
    data_quality_path: Path
    history_report_json_path: Path
    history_report_markdown_path: Path
    market_summary_path: Path
    market_summary_data_path: Path
    market_summary_html_path: Path
    ai_insights_path: Path
    run_manifest_path: Path


def build_artifact_paths(config: AppConfig, run_id: str) -> ArtifactPaths:
    raw_run_dir = config.directories.raw_dir / run_id
    processed_dir = config.directories.processed_dir
    reports_dir = config.directories.reports_dir
    manifests_dir = config.directories.manifests_dir
    history_dir = config.directories.history_dir
    logs_dir = config.directories.logs_dir

    return ArtifactPaths(
        run_id=run_id,
        raw_run_dir=raw_run_dir,
        processed_dir=processed_dir,
        reports_dir=reports_dir,
        manifests_dir=manifests_dir,
        history_dir=history_dir,
        logs_dir=logs_dir,
        history_db_path=history_dir / "jobintel.duckdb",
        collected_jobs_path=processed_dir / "collected_jobs.json",
        validated_jobs_path=processed_dir / "validated_jobs.json",
        quarantined_jobs_path=processed_dir / "quarantined_jobs.json",
        curated_jobs_json_path=processed_dir / "jobs.json",
        curated_jobs_csv_path=processed_dir / "jobs.csv",
        validation_issues_path=processed_dir / "validation_issues.json",
        validation_summary_path=processed_dir / "validation_summary.json",
        delta_report_path=reports_dir / "delta_report.json",
        data_quality_path=reports_dir / "data_quality_report.json",
        history_report_json_path=reports_dir / "history_trend_report.json",
        history_report_markdown_path=reports_dir / "history_trend_report.md",
        market_summary_path=reports_dir / "market_summary.md",
        market_summary_data_path=reports_dir / "market_summary.data.json",
        market_summary_html_path=reports_dir / "market_summary.html",
        ai_insights_path=reports_dir / "ai_insights.json",
        run_manifest_path=manifests_dir / f"{run_id}.json",
    )


def ensure_directories(paths: ArtifactPaths) -> None:
    for directory in (
        paths.raw_run_dir,
        paths.processed_dir,
        paths.reports_dir,
        paths.manifests_dir,
        paths.history_dir,
        paths.logs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_jobs(path: Path, jobs: list[JobPosting]) -> None:
    write_json(path, [job.to_record() for job in jobs])


def read_jobs(path: Path) -> list[JobPosting]:
    payload = read_json(path)
    return [JobPosting.model_validate(item) for item in payload]


def write_validation_issues(path: Path, issues: list[ValidationIssue]) -> None:
    write_json(path, [issue.model_dump(mode="json") for issue in issues])


def read_validation_issues(path: Path) -> list[ValidationIssue]:
    payload = read_json(path)
    return [ValidationIssue.model_validate(item) for item in payload]


def write_jobs_csv(path: Path, jobs: list[JobPosting]) -> None:
    records = [job.to_record() for job in jobs]
    frame = pd.DataFrame(records)
    frame.to_csv(path, index=False)


def snapshot_run_artifacts(paths: ArtifactPaths) -> dict[str, Path]:
    run_dir = paths.manifests_dir.parent / "runs" / paths.run_id
    processed_dir = run_dir / "processed"
    reports_dir = run_dir / "reports"
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    archive_map = {
        "collected_jobs": processed_dir / "collected_jobs.json",
        "validated_jobs": processed_dir / "validated_jobs.json",
        "quarantined_jobs": processed_dir / "quarantined_jobs.json",
        "jobs_json": processed_dir / "jobs.json",
        "jobs_csv": processed_dir / "jobs.csv",
        "validation_issues": processed_dir / "validation_issues.json",
        "validation_summary": processed_dir / "validation_summary.json",
        "quality_report": reports_dir / "data_quality_report.json",
        "delta_report": reports_dir / "delta_report.json",
        "market_summary": reports_dir / "market_summary.md",
        "market_summary_html": reports_dir / "market_summary.html",
        "market_summary_data": reports_dir / "market_summary.data.json",
        "history_trend_report_json": reports_dir / "history_trend_report.json",
        "history_trend_report_markdown": reports_dir / "history_trend_report.md",
        "ai_insights": reports_dir / "ai_insights.json",
    }

    source_map = {
        "collected_jobs": paths.collected_jobs_path,
        "validated_jobs": paths.validated_jobs_path,
        "quarantined_jobs": paths.quarantined_jobs_path,
        "jobs_json": paths.curated_jobs_json_path,
        "jobs_csv": paths.curated_jobs_csv_path,
        "validation_issues": paths.validation_issues_path,
        "validation_summary": paths.validation_summary_path,
        "quality_report": paths.data_quality_path,
        "delta_report": paths.delta_report_path,
        "market_summary": paths.market_summary_path,
        "market_summary_html": paths.market_summary_html_path,
        "market_summary_data": paths.market_summary_data_path,
        "history_trend_report_json": paths.history_report_json_path,
        "history_trend_report_markdown": paths.history_report_markdown_path,
        "ai_insights": paths.ai_insights_path,
    }

    for artifact_name, source_path in source_map.items():
        if source_path.exists():
            shutil.copy2(source_path, archive_map[artifact_name])

    return archive_map
