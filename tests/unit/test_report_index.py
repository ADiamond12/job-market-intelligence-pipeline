from datetime import datetime, timezone

from jobintel.domain.models import RunManifest
from jobintel.reporting.report_index import render_report_index_html, render_report_index_markdown


def build_manifest() -> RunManifest:
    return RunManifest(
        run_id="fixture-run-2",
        config_path="config/verification/companies.fixtures.run2.yaml",
        started_at=datetime(2026, 3, 26, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 26, 0, 1, tzinfo=timezone.utc),
        status="success",
        totals={
            "published_jobs": 4,
            "new_jobs": 2,
            "removed_jobs": 2,
            "changed_jobs": 2,
        },
        artifacts={
            "market_summary_html": "artifacts/verification/20260326/runs/fixture-run-2/reports/market_summary.html",
            "history_trend_report_markdown": "artifacts/verification/20260326/runs/fixture-run-2/reports/history_trend_report.md",
            "run_manifest": "artifacts/verification/20260326/manifests/fixture-run-2.json",
            "delta_report": "artifacts/verification/20260326/runs/fixture-run-2/reports/delta_report.json",
        },
    )


def test_report_index_markdown_points_reviewer_to_first_artifacts() -> None:
    markdown = render_report_index_markdown(build_manifest(), {"total_runs": 2})

    assert "# Job Market Intelligence Report Index" in markdown
    assert "Open First" in markdown
    assert "market_summary.html" in markdown
    assert "History runs included: 2" in markdown
    assert "New jobs: 2" in markdown


def test_report_index_html_is_standalone_and_escapes_paths() -> None:
    manifest = build_manifest()
    manifest.artifacts["market_summary_html"] = "reports/<market_summary>.html"

    html = render_report_index_html(manifest, {"total_runs": 2})

    assert html.startswith("<!DOCTYPE html>")
    assert "Open this first" in html
    assert "reports/&lt;market_summary&gt;.html" in html
    assert "<market_summary>" not in html
