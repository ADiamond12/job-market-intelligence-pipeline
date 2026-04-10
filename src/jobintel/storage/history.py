from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import duckdb

from jobintel.domain.models import JobPosting, RunManifest

_RUN_TABLE = "history_runs"
_JOB_TABLE = "history_jobs"
_VOLATILE_FIELDS = {"first_seen_at", "last_seen_at", "raw_snapshot_path"}
_RUN_SORT_SQL = "coalesce(completed_at, started_at) DESC, run_id DESC"


@dataclass(slots=True)
class JobSample:
    job_id: str
    company_slug: str
    company_name: str
    title_raw: str
    canonical_url: str | None
    source_type: str
    content_hash: str | None


@dataclass(slots=True)
class ChangedJobSample:
    job_id: str
    before: JobSample
    after: JobSample


@dataclass(slots=True)
class HistoryDelta:
    current_run_id: str
    previous_run_id: str | None
    new_jobs: int
    removed_jobs: int
    changed_jobs: int
    new_samples: list[JobSample] = field(default_factory=list)
    removed_samples: list[JobSample] = field(default_factory=list)
    changed_samples: list[ChangedJobSample] = field(default_factory=list)


@dataclass(slots=True)
class _StoredRun:
    run_id: str
    started_at: datetime | None
    completed_at: datetime | None
    config_path: str | None
    config_fingerprint: str | None
    comparison_scope: str | None
    manifest_json: str

    def to_manifest(self) -> RunManifest:
        return RunManifest.model_validate(json.loads(self.manifest_json))


def _dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _dt_from_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _manifest_payload(manifest: RunManifest) -> str:
    return json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False)


def _job_payload(job: JobPosting) -> str:
    return json.dumps(job.model_dump(mode="json"), ensure_ascii=False)


def _job_signature(job: JobPosting) -> dict[str, Any]:
    payload = job.model_dump(mode="json")
    for key in _VOLATILE_FIELDS:
        payload.pop(key, None)
    return payload


def _job_sample(job: JobPosting) -> JobSample:
    return JobSample(
        job_id=job.job_id,
        company_slug=job.company_slug,
        company_name=job.company_name,
        title_raw=job.title_raw,
        canonical_url=job.canonical_url,
        source_type=str(job.source_type),
        content_hash=job.content_hash,
    )


def _sort_samples(jobs: Iterable[JobPosting]) -> list[JobPosting]:
    return sorted(jobs, key=lambda item: (item.company_slug, item.title_raw, item.job_id))


def _config_fingerprint(config_path: str | Path | None) -> str | None:
    if config_path is None:
        return None
    path = Path(config_path)
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HistoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(self.db_path))

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_RUN_TABLE} (
                    run_id VARCHAR PRIMARY KEY,
                    started_at VARCHAR NOT NULL,
                    completed_at VARCHAR,
                    config_path VARCHAR,
                    config_fingerprint VARCHAR,
                    comparison_scope VARCHAR,
                    manifest_json VARCHAR NOT NULL
                )
                """
            )
            self._ensure_column(conn, _RUN_TABLE, "config_fingerprint", "VARCHAR")
            self._ensure_column(conn, _RUN_TABLE, "comparison_scope", "VARCHAR")
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_JOB_TABLE} (
                    run_id VARCHAR NOT NULL,
                    job_id VARCHAR NOT NULL,
                    company_slug VARCHAR NOT NULL,
                    company_name VARCHAR NOT NULL,
                    title_raw VARCHAR NOT NULL,
                    canonical_url VARCHAR,
                    content_hash VARCHAR,
                    source_type VARCHAR NOT NULL,
                    payload_json VARCHAR NOT NULL,
                    PRIMARY KEY (run_id, job_id)
                )
                """
            )

    @staticmethod
    def _ensure_column(conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str, ddl: str) -> None:
        exists = conn.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = ? AND column_name = ?
            LIMIT 1
            """,
            [table_name, column_name],
        ).fetchone()
        if exists is None:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    def _load_run_row(
        self,
        conn: duckdb.DuckDBPyConnection,
        run_id: str,
    ) -> _StoredRun | None:
        row = conn.execute(
            f"""
            SELECT run_id, started_at, completed_at, config_path, config_fingerprint, comparison_scope, manifest_json
            FROM {_RUN_TABLE}
            WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()
        if row is None:
            return None
        return _StoredRun(
            run_id=row[0],
            started_at=_dt_from_iso(row[1]),
            completed_at=_dt_from_iso(row[2]),
            config_path=row[3],
            config_fingerprint=row[4],
            comparison_scope=row[5],
            manifest_json=row[6],
        )

    def _select_runs(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        limit: int,
        comparison_scope: str | None = None,
        config_fingerprint: str | None = None,
        config_path: str | None = None,
        before: datetime | None = None,
        exclude_run_id: str | None = None,
    ) -> list[_StoredRun]:
        filters: list[str] = []
        params: list[Any] = []
        if comparison_scope is not None:
            filters.append("comparison_scope = ?")
            params.append(comparison_scope)
        elif config_fingerprint is not None:
            if config_path is not None:
                filters.append("(config_fingerprint = ? OR (config_fingerprint IS NULL AND config_path = ?))")
                params.extend([config_fingerprint, config_path])
            else:
                filters.append("config_fingerprint = ?")
                params.append(config_fingerprint)
        elif config_path is not None:
            filters.append("config_path = ?")
            params.append(config_path)
        if before is not None:
            filters.append(f"coalesce(completed_at, started_at) < ?")
            params.append(_dt_to_iso(before))
        if exclude_run_id is not None:
            filters.append("run_id <> ?")
            params.append(exclude_run_id)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = conn.execute(
            f"""
            SELECT run_id, started_at, completed_at, config_path, config_fingerprint, comparison_scope, manifest_json
            FROM {_RUN_TABLE}
            {where_clause}
            ORDER BY {_RUN_SORT_SQL}
            LIMIT ?
            """,
            params + [limit],
        ).fetchall()
        return [
            _StoredRun(
                run_id=row[0],
                started_at=_dt_from_iso(row[1]),
                completed_at=_dt_from_iso(row[2]),
                config_path=row[3],
                config_fingerprint=row[4],
                comparison_scope=row[5],
                manifest_json=row[6],
            )
            for row in rows
        ]

    def save_run(self, manifest: RunManifest) -> None:
        self.ensure_schema()
        config_fingerprint = _config_fingerprint(manifest.config_path)
        comparison_scope = manifest.comparison_scope or config_fingerprint or manifest.config_path
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {_RUN_TABLE} WHERE run_id = ?", [manifest.run_id])
            conn.execute(
                f"""
                INSERT INTO {_RUN_TABLE} (
                    run_id, started_at, completed_at, config_path, config_fingerprint, comparison_scope, manifest_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    manifest.run_id,
                    _dt_to_iso(manifest.started_at),
                    _dt_to_iso(manifest.completed_at),
                    manifest.config_path,
                    config_fingerprint,
                    comparison_scope,
                    _manifest_payload(manifest),
                ],
            )

    def save_jobs(self, run_id: str, jobs: list[JobPosting]) -> int:
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {_JOB_TABLE} WHERE run_id = ?", [run_id])
            rows = [
                (
                    run_id,
                    job.job_id,
                    job.company_slug,
                    job.company_name,
                    job.title_raw,
                    job.canonical_url,
                    job.content_hash,
                    str(job.source_type),
                    _job_payload(job),
                )
                for job in jobs
            ]
            if rows:
                conn.executemany(
                    f"""
                    INSERT INTO {_JOB_TABLE} (
                        run_id,
                        job_id,
                        company_slug,
                        company_name,
                        title_raw,
                        canonical_url,
                        content_hash,
                        source_type,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            return len(rows)

    def load_jobs(self, run_id: str) -> list[JobPosting]:
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT payload_json
                FROM {_JOB_TABLE}
                WHERE run_id = ?
                ORDER BY job_id
                """,
                [run_id],
            ).fetchall()
        return [JobPosting.model_validate(json.loads(row[0])) for row in rows]

    def load_manifest(self, run_id: str) -> RunManifest | None:
        self.ensure_schema()
        with self._connect() as conn:
            stored = self._load_run_row(conn, run_id)
        if stored is None:
            return None
        return stored.to_manifest()

    def list_runs(
        self,
        limit: int = 10,
        *,
        comparison_scope: str | None = None,
        config_fingerprint: str | None = None,
        config_path: str | None = None,
    ) -> list[RunManifest]:
        self.ensure_schema()
        with self._connect() as conn:
            stored_runs = self._select_runs(
                conn,
                limit=limit,
                comparison_scope=comparison_scope,
                config_fingerprint=config_fingerprint,
                config_path=config_path,
            )
        return [stored.to_manifest() for stored in stored_runs]

    def load_recent_manifests(
        self,
        limit: int = 10,
        *,
        comparison_scope: str | None = None,
        config_fingerprint: str | None = None,
        config_path: str | None = None,
    ) -> list[RunManifest]:
        return self.list_runs(
            limit=limit,
            comparison_scope=comparison_scope,
            config_fingerprint=config_fingerprint,
            config_path=config_path,
        )

    def get_previous_run(
        self,
        run_id: str | None = None,
        *,
        comparison_scope: str | None = None,
        config_fingerprint: str | None = None,
        config_path: str | None = None,
    ) -> RunManifest | None:
        self.ensure_schema()
        with self._connect() as conn:
            if run_id is None:
                stored_runs = self._select_runs(
                    conn,
                    limit=2 if not comparison_scope and not config_fingerprint and not config_path else 1,
                    comparison_scope=comparison_scope,
                    config_fingerprint=config_fingerprint,
                    config_path=config_path,
                )
                if not comparison_scope and not config_fingerprint and not config_path:
                    stored = stored_runs[1] if len(stored_runs) > 1 else None
                else:
                    stored = stored_runs[0] if stored_runs else None
            else:
                current = self._load_run_row(conn, run_id)
                if current is None:
                    stored_runs = self._select_runs(
                        conn,
                        limit=2 if not comparison_scope and not config_fingerprint and not config_path else 1,
                        comparison_scope=comparison_scope,
                        config_fingerprint=config_fingerprint,
                        config_path=config_path,
                    )
                    if not comparison_scope and not config_fingerprint and not config_path:
                        stored = stored_runs[1] if len(stored_runs) > 1 else None
                    else:
                        stored = stored_runs[0] if stored_runs else None
                else:
                    current_scope = comparison_scope or current.comparison_scope
                    current_fingerprint = config_fingerprint or current.config_fingerprint or _config_fingerprint(
                        current.config_path
                    )
                    current_config_path = config_path or current.config_path
                    stored_runs = self._select_runs(
                        conn,
                        limit=1,
                        comparison_scope=current_scope,
                        config_fingerprint=None if current_scope is not None else current_fingerprint,
                        config_path=None
                        if current_scope is not None or current_fingerprint is not None
                        else current_config_path,
                        before=current.completed_at or current.started_at,
                        exclude_run_id=run_id,
                    )
                    stored = stored_runs[0] if stored_runs else None
        if stored is None:
            return None
        return stored.to_manifest()

    def compute_delta(self, run_id: str, sample_size: int = 5) -> HistoryDelta:
        current_jobs = self.load_jobs(run_id)
        current_run = self.load_manifest(run_id)
        if current_run is None:
            return HistoryDelta(
                current_run_id=run_id,
                previous_run_id=None,
                new_jobs=len(current_jobs),
                removed_jobs=0,
                changed_jobs=0,
                new_samples=[_job_sample(job) for job in _sort_samples(current_jobs)[:sample_size]],
            )

        previous_run = self.get_previous_run(
            run_id,
            comparison_scope=current_run.comparison_scope or _config_fingerprint(current_run.config_path) or current_run.config_path,
            config_fingerprint=_config_fingerprint(current_run.config_path),
            config_path=current_run.config_path,
        )
        if previous_run is None:
            return HistoryDelta(
                current_run_id=run_id,
                previous_run_id=None,
                new_jobs=len(current_jobs),
                removed_jobs=0,
                changed_jobs=0,
                new_samples=[_job_sample(job) for job in _sort_samples(current_jobs)[:sample_size]],
            )

        previous_jobs = self.load_jobs(previous_run.run_id)
        current_by_id = {job.job_id: job for job in current_jobs}
        previous_by_id = {job.job_id: job for job in previous_jobs}

        new_jobs = [current_by_id[job_id] for job_id in current_by_id.keys() - previous_by_id.keys()]
        removed_jobs = [previous_by_id[job_id] for job_id in previous_by_id.keys() - current_by_id.keys()]
        changed_jobs = [
            (previous_by_id[job_id], current_by_id[job_id])
            for job_id in current_by_id.keys() & previous_by_id.keys()
            if _job_signature(current_by_id[job_id]) != _job_signature(previous_by_id[job_id])
        ]

        return HistoryDelta(
            current_run_id=run_id,
            previous_run_id=previous_run.run_id,
            new_jobs=len(new_jobs),
            removed_jobs=len(removed_jobs),
            changed_jobs=len(changed_jobs),
            new_samples=[_job_sample(job) for job in _sort_samples(new_jobs)[:sample_size]],
            removed_samples=[_job_sample(job) for job in _sort_samples(removed_jobs)[:sample_size]],
            changed_samples=[
                ChangedJobSample(
                    job_id=before.job_id,
                    before=_job_sample(before),
                    after=_job_sample(after),
                )
                for before, after in sorted(
                    changed_jobs,
                    key=lambda pair: (pair[1].company_slug, pair[1].title_raw, pair[1].job_id),
                )[:sample_size]
            ],
        )
