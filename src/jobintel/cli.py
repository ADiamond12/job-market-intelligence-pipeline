from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

from jobintel.config import AppConfig, load_config
from jobintel.domain.models import RunManifest, utc_now
from jobintel.observability.logging import setup_logging
from jobintel.pipeline.collect import run_collection
from jobintel.pipeline.enrich import run_enrichment
from jobintel.pipeline.report import run_reporting
from jobintel.pipeline.validate import run_validation
from jobintel.reporting.history_report import build_history_trend_report
from jobintel.reporting.report_index import render_report_index_html, render_report_index_markdown
from jobintel.storage.artifacts import build_artifact_paths, ensure_directories, snapshot_run_artifacts
from jobintel.storage.history import HistoryStore
from jobintel.storage.manifests import write_manifest
from jobintel.storage.run_lock import RunLock, RunLockError

app = typer.Typer(help="Job market intelligence pipeline CLI.")


def _build_run_id(value: str | None) -> str:
    return value or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _bootstrap(config_path: Path, run_id: str | None, verbose: bool):
    config = load_config(config_path)
    resolved_run_id = _build_run_id(run_id)
    paths = build_artifact_paths(config, resolved_run_id)
    ensure_directories(paths)
    logger = setup_logging(paths.logs_dir, resolved_run_id, verbose=verbose)
    return config, resolved_run_id, paths, logger


def _write_history_trend_report(config: AppConfig, paths, history_store: HistoryStore, limit: int = 10) -> dict:
    manifests = history_store.load_recent_manifests(
        limit=limit,
        comparison_scope=config.comparison_scope,
        config_path=str(config.config_path) if config.config_path else None,
    )
    delta_summaries: dict[str, dict] = {}
    manifest_payloads: list[dict] = []

    for manifest in manifests:
        manifest_payloads.append(
            {
                "run_id": manifest.run_id,
                "status": manifest.status,
                "started_at": manifest.started_at,
                "completed_at": manifest.completed_at,
                "metrics": manifest.totals,
                "config_path": manifest.config_path,
            }
        )
        delta_path = manifest.artifacts.get("delta_report")
        if delta_path and Path(delta_path).exists():
            import json

            delta_summaries[manifest.run_id] = json.loads(Path(delta_path).read_text(encoding="utf-8"))

    trend_report = build_history_trend_report(
        recent_run_manifests=manifest_payloads,
        delta_summaries=delta_summaries,
        title="JobIntel History Trend Report",
    )
    paths.history_report_markdown_path.write_text(trend_report.markdown + "\n", encoding="utf-8")
    import json

    paths.history_report_json_path.write_text(
        json.dumps(trend_report.payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return trend_report.payload


def _manifest_artifacts(paths, archived_paths: dict[str, Path] | None = None) -> dict[str, str]:
    archive = archived_paths or {}
    return {
        "collected_jobs": str(archive.get("collected_jobs", paths.collected_jobs_path)),
        "validated_jobs": str(archive.get("validated_jobs", paths.validated_jobs_path)),
        "quarantined_jobs": str(archive.get("quarantined_jobs", paths.quarantined_jobs_path)),
        "jobs_json": str(archive.get("jobs_json", paths.curated_jobs_json_path)),
        "jobs_csv": str(archive.get("jobs_csv", paths.curated_jobs_csv_path)),
        "validation_issues": str(archive.get("validation_issues", paths.validation_issues_path)),
        "validation_summary": str(archive.get("validation_summary", paths.validation_summary_path)),
        "quality_report": str(archive.get("quality_report", paths.data_quality_path)),
        "delta_report": str(archive.get("delta_report", paths.delta_report_path)),
        "market_summary": str(archive.get("market_summary", paths.market_summary_path)),
        "market_summary_html": str(archive.get("market_summary_html", paths.market_summary_html_path)),
        "market_summary_data": str(archive.get("market_summary_data", paths.market_summary_data_path)),
        "history_trend_report_json": str(
            archive.get("history_trend_report_json", paths.history_report_json_path)
        ),
        "history_trend_report_markdown": str(
            archive.get("history_trend_report_markdown", paths.history_report_markdown_path)
        ),
        "report_index": str(archive.get("report_index", paths.report_index_path)),
        "report_index_html": str(archive.get("report_index_html", paths.report_index_html_path)),
        "ai_insights": str(archive.get("ai_insights", paths.ai_insights_path)),
        "history_db": str(paths.history_db_path),
        "run_manifest": str(paths.run_manifest_path),
    }


def _write_report_index(paths, manifest: RunManifest, history_payload: dict) -> None:
    paths.report_index_path.write_text(
        render_report_index_markdown(manifest, history_payload),
        encoding="utf-8",
    )
    paths.report_index_html_path.write_text(
        render_report_index_html(manifest, history_payload),
        encoding="utf-8",
    )


@app.command()
def collect(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("config/companies.example.yaml"),
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    config, resolved_run_id, paths, logger = _bootstrap(config_path, run_id, verbose)
    jobs, _ = run_collection(config, paths, logger)
    typer.echo(f"[{resolved_run_id}] collected {len(jobs)} jobs -> {paths.collected_jobs_path}")


@app.command()
def validate(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("config/companies.example.yaml"),
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    config, resolved_run_id, paths, logger = _bootstrap(config_path, run_id, verbose)
    valid_jobs, quarantined_jobs, issues, duplicates_removed = run_validation(config, paths, logger)
    typer.echo(
        f"[{resolved_run_id}] validated {len(valid_jobs)} jobs, quarantined {len(quarantined_jobs)}, "
        f"issues {len(issues)}, duplicates removed {duplicates_removed}"
    )


@app.command()
def enrich(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("config/companies.example.yaml"),
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    config, resolved_run_id, paths, logger = _bootstrap(config_path, run_id, verbose)
    jobs = run_enrichment(config, paths, logger)
    typer.echo(f"[{resolved_run_id}] enriched {len(jobs)} jobs -> {paths.curated_jobs_csv_path}")


@app.command()
def report(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("config/companies.example.yaml"),
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    config, resolved_run_id, paths, logger = _bootstrap(config_path, run_id, verbose)
    history_store = HistoryStore(paths.history_db_path)
    history_store.ensure_schema()
    metrics, _, _, delta_report = run_reporting(config, paths, logger, history_store=history_store)
    history_payload = _write_history_trend_report(config, paths, history_store)
    manifest = RunManifest(
        run_id=resolved_run_id,
        config_path=str(config.config_path or config_path),
        comparison_scope=config.comparison_scope,
        started_at=utc_now(),
        completed_at=utc_now(),
        status="success",
        source_stats=[],
        totals={
            "published_jobs": metrics.get("total_jobs", 0),
            "new_jobs": delta_report.get("summary", {}).get("new_jobs", 0),
            "removed_jobs": delta_report.get("summary", {}).get("removed_jobs", 0),
            "changed_jobs": delta_report.get("summary", {}).get("changed_jobs", 0),
        },
        artifacts=_manifest_artifacts(paths),
    )
    _write_report_index(paths, manifest, history_payload)
    typer.echo(
        f"[{resolved_run_id}] report created with {metrics['total_jobs']} published jobs "
        f"-> {paths.market_summary_path} and {paths.market_summary_html_path}; "
        f"baseline={delta_report.get('baseline_run_id') or 'none'}; "
        f"history runs={history_payload['total_runs']}"
    )


@app.command()
def history(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("config/companies.example.yaml"),
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    limit: Annotated[int, typer.Option("--limit")] = 10,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    config, resolved_run_id, paths, logger = _bootstrap(config_path, run_id, verbose)
    lock_path = paths.history_dir / "run.lock"
    try:
        with RunLock(lock_path):
            history_store = HistoryStore(paths.history_db_path)
            history_store.ensure_schema()
            payload = _write_history_trend_report(config, paths, history_store, limit=limit)
    except RunLockError as exc:
        logger.error(str(exc))
        typer.echo(f"[{resolved_run_id}] {exc}")
        raise typer.Exit(code=1) from exc

    typer.echo(
        f"[{resolved_run_id}] history report created for {payload['total_runs']} runs "
        f"-> {paths.history_report_markdown_path}"
    )


@app.command()
def run(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("config/companies.example.yaml"),
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    config, resolved_run_id, paths, logger = _bootstrap(config_path, run_id, verbose)
    started_at = utc_now()
    history_store = HistoryStore(paths.history_db_path)
    lock_path = paths.history_dir / "run.lock"

    try:
        with RunLock(lock_path):
            history_store.ensure_schema()
            history_store.save_run(
                RunManifest(
                    run_id=resolved_run_id,
                    config_path=str(config.config_path or config_path),
                    comparison_scope=config.comparison_scope,
                    started_at=started_at,
                    completed_at=None,
                    status="running",
                    source_stats=[],
                    totals={},
                    artifacts={},
                )
            )

            collected_jobs, source_stats = run_collection(config, paths, logger)
            validated_jobs, quarantined_jobs, issues, _ = run_validation(config, paths, logger, jobs=collected_jobs)
            curated_jobs = run_enrichment(config, paths, logger, jobs=validated_jobs)
            history_store.save_jobs(resolved_run_id, curated_jobs)
            metrics, _, ai_insight, delta_report = run_reporting(
                config,
                paths,
                logger,
                jobs=curated_jobs,
                validation_issues=issues,
                quarantined_jobs=quarantined_jobs,
                history_store=history_store,
            )

            manifest = RunManifest(
                run_id=resolved_run_id,
                config_path=str(config.config_path or config_path),
                comparison_scope=config.comparison_scope,
                started_at=started_at,
                completed_at=utc_now(),
                status="success",
                source_stats=source_stats,
                totals={
                    "collected_jobs": len(collected_jobs),
                    "published_jobs": len(curated_jobs),
                    "quarantined_jobs": len(quarantined_jobs),
                    "new_jobs": delta_report.get("summary", {}).get("new_jobs", 0),
                    "removed_jobs": delta_report.get("summary", {}).get("removed_jobs", 0),
                    "changed_jobs": delta_report.get("summary", {}).get("changed_jobs", 0),
                },
                artifacts=_manifest_artifacts(paths),
            )
            write_manifest(paths.run_manifest_path, manifest)
            history_store.save_run(manifest)
            history_payload = _write_history_trend_report(config, paths, history_store)
            _write_report_index(paths, manifest, history_payload)
            archived_paths = snapshot_run_artifacts(paths)
            manifest = RunManifest(
                run_id=resolved_run_id,
                config_path=str(config.config_path or config_path),
                comparison_scope=config.comparison_scope,
                started_at=started_at,
                completed_at=manifest.completed_at,
                status="success",
                source_stats=source_stats,
                totals=manifest.totals,
                artifacts=_manifest_artifacts(paths, archived_paths),
            )
            write_manifest(paths.run_manifest_path, manifest)
            history_store.save_run(manifest)
            _write_report_index(paths, manifest, history_payload)
    except RunLockError as exc:
        logger.error(str(exc))
        typer.echo(f"[{resolved_run_id}] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception:
        failure_manifest = RunManifest(
            run_id=resolved_run_id,
            config_path=str(config.config_path or config_path),
            comparison_scope=config.comparison_scope,
            started_at=started_at,
            completed_at=utc_now(),
            status="failed",
            source_stats=[],
            totals={},
            artifacts={"history_db": str(paths.history_db_path)},
        )
        write_manifest(paths.run_manifest_path, failure_manifest)
        history_store.save_run(failure_manifest)
        raise

    typer.echo(
        f"[{resolved_run_id}] pipeline complete: {metrics['total_jobs']} jobs published, "
        f"delta new={delta_report.get('summary', {}).get('new_jobs', 0)}, "
        f"removed={delta_report.get('summary', {}).get('removed_jobs', 0)}, "
        f"changed={delta_report.get('summary', {}).get('changed_jobs', 0)}; "
        f"reports -> {paths.market_summary_path}, {paths.market_summary_html_path}, "
        f"{paths.report_index_html_path}, {paths.history_report_markdown_path} ({history_payload['total_runs']} runs)"
    )


if __name__ == "__main__":
    app()
