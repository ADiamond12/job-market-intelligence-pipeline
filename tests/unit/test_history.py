from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jobintel.domain.models import JobPosting, RunManifest, SourceType
from jobintel.storage.history import HistoryStore


def _job(job_id: str, title_raw: str, canonical_url: str, description: str) -> JobPosting:
    return JobPosting(
        job_id=job_id,
        source_type=SourceType.GREENHOUSE,
        vendor="greenhouse",
        company_name="Acme",
        company_slug="acme",
        source_job_id=job_id,
        source_url="https://example.com/careers",
        canonical_url=canonical_url,
        title_raw=title_raw,
        location_raw="Remote, United States",
        description_html=f"<p>{description}</p>",
    )


def _manifest(
    run_id: str,
    started_at: datetime,
    completed_at: datetime,
    config_path: Path,
    comparison_scope: str | None = None,
) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        config_path=str(config_path),
        comparison_scope=comparison_scope,
        started_at=started_at,
        completed_at=completed_at,
        totals={"published_jobs": 2},
        artifacts={"jobs_json": "data/processed/jobs.json"},
    )


def test_history_store_creates_schema_and_persists_round_trips(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.duckdb")
    config_path = tmp_path / "config-a.yaml"
    config_path.write_text("companies: []\n", encoding="utf-8")
    store.ensure_schema()

    with store._connect() as conn:  # type: ignore[attr-defined]
        tables = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name IN ('history_runs', 'history_jobs')
            """
        ).fetchone()[0]

    assert tables == 2
    assert store.db_path.exists()

    started_at = datetime(2026, 3, 26, 10, 0, tzinfo=timezone.utc)
    completed_at = started_at + timedelta(minutes=1)
    manifest = _manifest("run-1", started_at, completed_at, config_path, comparison_scope="watch:acme")
    jobs = [
        _job("1", "Data Engineer", "https://example.com/jobs/1", "Build pipelines."),
        _job("2", "Analytics Engineer", "https://example.com/jobs/2", "Model data."),
    ]

    store.save_run(manifest)
    saved_jobs = store.save_jobs(manifest.run_id, jobs)

    assert saved_jobs == 2
    assert store.get_previous_run(manifest.run_id) is None
    with store._connect() as conn:  # type: ignore[attr-defined]
        fingerprint, comparison_scope = conn.execute(
            """
            SELECT config_fingerprint, comparison_scope
            FROM history_runs
            WHERE run_id = ?
            """,
            [manifest.run_id],
        ).fetchone()
    assert fingerprint == hashlib.sha256(config_path.read_bytes()).hexdigest()
    assert comparison_scope == "watch:acme"
    assert [run.run_id for run in store.load_recent_manifests()] == ["run-1"]
    assert [run.run_id for run in store.load_recent_manifests(comparison_scope="watch:acme")] == ["run-1"]
    loaded_manifest = store.load_manifest("run-1")
    assert loaded_manifest is not None
    assert Path(loaded_manifest.config_path) == config_path
    loaded_jobs = store.load_jobs(manifest.run_id)
    assert [job.job_id for job in loaded_jobs] == ["1", "2"]
    assert loaded_jobs[0].title_raw == "Data Engineer"


def test_history_store_scopes_previous_run_to_matching_config(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.duckdb")
    config_a = tmp_path / "config-a.yaml"
    config_b = tmp_path / "config-b.yaml"
    config_a.write_text("companies:\n  - acme\n", encoding="utf-8")
    config_b.write_text("companies:\n  - beta\n", encoding="utf-8")

    run_1_started = datetime(2026, 3, 26, 10, 0, tzinfo=timezone.utc)
    run_2_started = run_1_started + timedelta(hours=1)
    run_3_started = run_2_started + timedelta(hours=1)

    manifest_1 = _manifest("run-1", run_1_started, run_1_started + timedelta(minutes=1), config_a, comparison_scope="watch:data")
    manifest_2 = _manifest("run-2", run_2_started, run_2_started + timedelta(minutes=1), config_b, comparison_scope="watch:support")
    manifest_3 = _manifest("run-3", run_3_started, run_3_started + timedelta(minutes=1), config_a, comparison_scope="watch:data")

    job_1_prev = _job("1", "Data Engineer", "https://example.com/jobs/1", "Build pipelines.")
    job_2_prev = _job("2", "Analytics Engineer", "https://example.com/jobs/2", "Model data.")
    job_9_other = _job("9", "Support Engineer", "https://example.com/jobs/9", "Help customers.")
    job_10_other = _job("10", "DevOps Engineer", "https://example.com/jobs/10", "Run infra.")
    job_1_new = _job("1", "Senior Data Engineer", "https://example.com/jobs/1", "Build pipelines and platform tooling.")
    job_3_new = _job("3", "Machine Learning Engineer", "https://example.com/jobs/3", "Ship ML systems.")

    store.save_run(manifest_1)
    store.save_jobs(manifest_1.run_id, [job_1_prev, job_2_prev])
    store.save_run(manifest_2)
    store.save_jobs(manifest_2.run_id, [job_9_other, job_10_other])
    store.save_run(manifest_3)
    store.save_jobs(manifest_3.run_id, [job_1_new, job_3_new])

    previous = store.get_previous_run("run-2")
    assert previous is None

    previous_same_config = store.get_previous_run("run-3")
    assert previous_same_config is not None
    assert previous_same_config.run_id == "run-1"

    recent_runs = store.load_recent_manifests(limit=3)
    assert [run.run_id for run in recent_runs] == ["run-3", "run-2", "run-1"]

    recent_same_scope = store.load_recent_manifests(limit=5, comparison_scope="watch:data")
    assert [run.run_id for run in recent_same_scope] == ["run-3", "run-1"]

    delta = store.compute_delta("run-3", sample_size=5)

    assert delta.current_run_id == "run-3"
    assert delta.previous_run_id == "run-1"
    assert delta.new_jobs == 1
    assert delta.removed_jobs == 1
    assert delta.changed_jobs == 1
    assert [sample.job_id for sample in delta.new_samples] == ["3"]
    assert [sample.job_id for sample in delta.removed_samples] == ["2"]
    assert [sample.job_id for sample in delta.changed_samples] == ["1"]
    assert delta.changed_samples[0].before.title_raw == "Data Engineer"
    assert delta.changed_samples[0].after.title_raw == "Senior Data Engineer"
