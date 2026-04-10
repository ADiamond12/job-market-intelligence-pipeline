from __future__ import annotations

from dataclasses import asdict
import logging

from jobintel.config import AppConfig
from jobintel.domain.models import AIReportInsight, JobPosting, ValidationIssue
from jobintel.enrichment.llm_client import OpenAIResponsesClient
from jobintel.reporting.deltas import build_delta_report
from jobintel.reporting.metrics import compute_market_metrics
from jobintel.reporting.quality import build_quality_report
from jobintel.reporting.render import render_market_summary, render_market_summary_markdown
from jobintel.storage.artifacts import (
    ArtifactPaths,
    read_jobs,
    read_json,
    read_validation_issues,
    write_json,
)
from jobintel.storage.history import HistoryStore


def run_reporting(
    config: AppConfig,
    paths: ArtifactPaths,
    logger: logging.Logger,
    jobs: list[JobPosting] | None = None,
    validation_issues: list[ValidationIssue] | None = None,
    quarantined_jobs: list[JobPosting] | None = None,
    history_store: HistoryStore | None = None,
) -> tuple[dict, dict, AIReportInsight, dict]:
    curated_jobs = jobs or read_jobs(paths.curated_jobs_json_path)
    collected_jobs = read_jobs(paths.collected_jobs_path)
    quarantined = quarantined_jobs or read_jobs(paths.quarantined_jobs_path)
    issues = validation_issues or read_validation_issues(paths.validation_issues_path)
    validation_summary = read_json(paths.validation_summary_path)

    metrics = compute_market_metrics(curated_jobs)
    quality_report = build_quality_report(
        collected_jobs=collected_jobs,
        curated_jobs=curated_jobs,
        quarantined_jobs=quarantined,
        validation_issues=issues,
        duplicates_removed=validation_summary.get("duplicates_removed", 0),
    )

    ai_client = OpenAIResponsesClient(config.ai)
    ai_insight = _generate_ai_insight(curated_jobs, metrics, quality_report, ai_client, logger)
    delta_report = _build_delta_report(paths.run_id, curated_jobs, history_store)

    markdown = render_market_summary_markdown(
        paths.run_id,
        metrics,
        quality_report,
        ai_insight,
        delta_summary=_flat_delta_summary_markdown(delta_report),
    )
    html = render_market_summary(
        paths.run_id,
        metrics,
        quality_report,
        ai_insight,
        delta_summary=_flat_delta_summary_html(delta_report),
    )
    report_payload = {
        "run_id": paths.run_id,
        "metrics": metrics,
        "quality_report": quality_report,
        "delta_report": delta_report,
        "ai_insight": ai_insight.model_dump(mode="json"),
    }
    write_json(paths.data_quality_path, quality_report)
    write_json(paths.ai_insights_path, ai_insight.model_dump(mode="json"))
    write_json(paths.delta_report_path, delta_report)
    write_json(paths.market_summary_data_path, report_payload)
    paths.market_summary_path.parent.mkdir(parents=True, exist_ok=True)
    paths.market_summary_path.write_text(markdown, encoding="utf-8")
    paths.market_summary_html_path.write_text(html, encoding="utf-8")

    return metrics, quality_report, ai_insight, delta_report


def _generate_ai_insight(
    curated_jobs: list[JobPosting],
    metrics: dict,
    quality_report: dict,
    ai_client: OpenAIResponsesClient,
    logger: logging.Logger,
) -> AIReportInsight:
    context = {
        "metrics": metrics,
        "quality_report": quality_report,
        "example_jobs": [
            {
                "company": job.company_name,
                "title": job.title_normalized or job.title_raw,
                "skills": job.extracted_skills[:5],
            }
            for job in curated_jobs[:8]
        ],
    }

    if ai_client.available:
        try:
            result = ai_client.summarize_market(context)
            if result:
                return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI report summarization failed: %s", exc)

    top_skills = ", ".join(item["skill"] for item in metrics["top_skills"][:5]) or "no dominant skills yet"
    top_role_family = next(iter(metrics["role_family_distribution"]), "unknown")
    summary = (
        f"The latest run published {metrics['total_jobs']} jobs across {metrics['companies_tracked']} companies. "
        f"Skill demand clusters around {top_skills}, while the most common role family is {top_role_family}."
    )
    signals = [f"{skill['skill']} appears in {skill['count']} postings." for skill in metrics["top_skills"][:3]]
    evidence = [f"{job.company_name}: {job.title_normalized or job.title_raw}" for job in curated_jobs[:3]]
    return AIReportInsight(summary=summary, emerging_signals=signals, confidence=0.45, evidence=evidence, model=None)


def _build_delta_report(
    run_id: str,
    curated_jobs: list[JobPosting],
    history_store: HistoryStore | None,
) -> dict:
    if history_store is None:
        return build_delta_report(curated_jobs, baseline_jobs=None, baseline_run_id=None)

    previous_run = history_store.get_previous_run(run_id)
    baseline_jobs = history_store.load_jobs(previous_run.run_id) if previous_run else None
    delta_report = build_delta_report(
        curated_jobs,
        baseline_jobs=baseline_jobs,
        baseline_run_id=previous_run.run_id if previous_run else None,
    )

    if previous_run:
        history_delta = history_store.compute_delta(run_id)
        delta_report["summary"].update(
            {
                "new_jobs": history_delta.new_jobs,
                "removed_jobs": history_delta.removed_jobs,
                "changed_jobs": history_delta.changed_jobs,
            }
        )
        delta_report["samples"].update(
            {
                "new_jobs": [asdict(sample) for sample in history_delta.new_samples],
                "removed_jobs": [asdict(sample) for sample in history_delta.removed_samples],
                "changed_jobs": [asdict(sample) for sample in history_delta.changed_samples],
            }
        )

    return delta_report


def _flat_delta_summary_markdown(delta_report: dict) -> dict | None:
    if not delta_report.get("has_baseline"):
        return None
    summary = dict(delta_report.get("summary", {}))
    summary["baseline_run_id"] = delta_report.get("baseline_run_id")
    return summary


def _flat_delta_summary_html(delta_report: dict) -> dict | None:
    if not delta_report.get("has_baseline"):
        return None
    summary = dict(delta_report.get("summary", {}))
    summary["baseline_run_id"] = delta_report.get("baseline_run_id")
    if "removed_jobs" in summary:
        summary["removed_jobs"] = -abs(summary["removed_jobs"])
    return summary
