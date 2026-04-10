from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from jobintel.cli import app


def test_cli_run_pipeline_with_fixtures(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = Path.cwd()
    raw_dir = (tmp_path / "data" / "raw").as_posix()
    processed_dir = (tmp_path / "data" / "processed").as_posix()
    reports_dir = (tmp_path / "reports").as_posix()
    manifests_dir = (tmp_path / "artifacts" / "manifests").as_posix()
    history_dir = (tmp_path / "artifacts" / "history").as_posix()
    logs_dir = (tmp_path / "logs").as_posix()
    greenhouse_fixture = (repo_root / "tests" / "fixtures" / "greenhouse_fixture.json").as_posix()
    lever_fixture = (repo_root / "tests" / "fixtures" / "lever_fixture.json").as_posix()
    greenhouse_fixture_run2 = (repo_root / "tests" / "fixtures" / "greenhouse_fixture_run2.json").as_posix()
    lever_fixture_run2 = (repo_root / "tests" / "fixtures" / "lever_fixture_run2.json").as_posix()

    config_path = tmp_path / "fixture-config.yaml"
    config_path.write_text(
        f"""
project_name: Job Market Intelligence Pipeline
user_agent: job-market-intel/test
directories:
  raw_dir: {raw_dir}
  processed_dir: {processed_dir}
  reports_dir: {reports_dir}
  manifests_dir: {manifests_dir}
  history_dir: {history_dir}
  logs_dir: {logs_dir}
retry:
  attempts: 1
  backoff_seconds: 1
  timeout_seconds: 5
dedupe:
  enabled: true
  similarity_threshold: 0.82
ai:
  enabled: false
companies:
  - name: Acme Analytics
    source_type: greenhouse
    identifier: acme-analytics
    fixture_path: {greenhouse_fixture}
  - name: BrightOps
    source_type: lever
    identifier: brightops
    fixture_path: {lever_fixture}
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["run", "--config", str(config_path), "--run-id", "fixture-run-1"])

    assert result.exit_code == 0, result.stdout

    jobs_path = tmp_path / "data" / "processed" / "jobs.json"
    report_path = tmp_path / "reports" / "market_summary.md"
    html_report_path = tmp_path / "reports" / "market_summary.html"
    data_report_path = tmp_path / "reports" / "market_summary.data.json"
    quality_path = tmp_path / "reports" / "data_quality_report.json"
    delta_path = tmp_path / "reports" / "delta_report.json"
    history_report_md = tmp_path / "reports" / "history_trend_report.md"
    history_report_json = tmp_path / "reports" / "history_trend_report.json"
    manifest_path = tmp_path / "artifacts" / "manifests" / "fixture-run-1.json"
    history_db_path = tmp_path / "artifacts" / "history" / "jobintel.duckdb"

    assert jobs_path.exists()
    assert report_path.exists()
    assert html_report_path.exists()
    assert data_report_path.exists()
    assert quality_path.exists()
    assert delta_path.exists()
    assert history_report_md.exists()
    assert history_report_json.exists()
    assert manifest_path.exists()
    assert history_db_path.exists()

    jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    delta = json.loads(delta_path.read_text(encoding="utf-8"))

    assert len(jobs) == 4
    assert quality["published_jobs"] == 4
    assert delta["has_baseline"] is False
    assert "Skill Trends" in report_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_report_path.read_text(encoding="utf-8")
    assert "delta_report" in json.dumps(json.loads(manifest_path.read_text(encoding="utf-8")))
    assert "fixture-run-1" in history_report_md.read_text(encoding="utf-8")

    config_path_run2 = tmp_path / "fixture-config-run2.yaml"
    config_path_run2.write_text(
        f"""
project_name: Job Market Intelligence Pipeline
user_agent: job-market-intel/test
directories:
  raw_dir: {raw_dir}
  processed_dir: {processed_dir}
  reports_dir: {reports_dir}
  manifests_dir: {manifests_dir}
  history_dir: {history_dir}
  logs_dir: {logs_dir}
retry:
  attempts: 1
  backoff_seconds: 1
  timeout_seconds: 5
dedupe:
  enabled: true
  similarity_threshold: 0.82
ai:
  enabled: false
companies:
  - name: Acme Analytics
    source_type: greenhouse
    identifier: acme-analytics
    fixture_path: {greenhouse_fixture_run2}
  - name: BrightOps
    source_type: lever
    identifier: brightops
    fixture_path: {lever_fixture_run2}
""".strip(),
        encoding="utf-8",
    )

    result_run2 = runner.invoke(app, ["run", "--config", str(config_path_run2), "--run-id", "fixture-run-2"])

    assert result_run2.exit_code == 0, result_run2.stdout

    delta_run2 = json.loads(delta_path.read_text(encoding="utf-8"))
    manifest_run2 = json.loads((tmp_path / "artifacts" / "manifests" / "fixture-run-2.json").read_text(encoding="utf-8"))
    history_payload = json.loads(history_report_json.read_text(encoding="utf-8"))

    assert delta_run2["has_baseline"] is True
    assert delta_run2["baseline_run_id"] == "fixture-run-1"
    assert delta_run2["summary"]["new_jobs"] == 2
    assert delta_run2["summary"]["removed_jobs"] == 2
    assert delta_run2["summary"]["changed_jobs"] == 2
    assert manifest_run2["artifacts"]["history_db"].endswith("jobintel.duckdb")
    archived_delta_path = manifest_run2["artifacts"]["delta_report"].replace("\\", "/")
    assert "runs/" in archived_delta_path
    assert archived_delta_path.endswith("runs/fixture-run-2/reports/delta_report.json")
    assert manifest_run2["comparison_scope"].startswith("companies:")
    assert history_payload["total_runs"] == 2
    assert [run["run_id"] for run in history_payload["runs"]] == ["fixture-run-2", "fixture-run-1"]
    assert history_payload["runs"][0]["delta_summary"]["baseline_run_id"] == "fixture-run-1"
    assert history_payload["runs"][0]["delta_summary"]["has_baseline"] is True
    assert history_payload["runs"][1]["delta_summary"]["has_baseline"] is False
