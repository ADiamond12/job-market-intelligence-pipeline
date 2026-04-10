"""History trend report rendering helpers.

This module keeps the rendering logic pure and deterministic so the CLI or an
agent can wire it in later without depending on any transport or storage layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Sequence


SUCCESS_STATUSES = {
    "ok",
    "pass",
    "passed",
    "succeeded",
    "success",
}

FAILURE_STATUSES = {
    "error",
    "failed",
    "failure",
    "fatal",
}

COMMON_MANIFEST_KEYS = {
    "completed_at",
    "duration",
    "duration_sec",
    "duration_seconds",
    "elapsed",
    "elapsed_seconds",
    "end_time",
    "finished_at",
    "id",
    "metrics",
    "name",
    "result",
    "started",
    "started_at",
    "start_time",
    "state",
    "status",
    "summary",
    "timestamp",
    "run_id",
}


@dataclass(frozen=True)
class HistoryTrendReport:
    """Container for both the rendered markdown and a JSON-friendly payload."""

    markdown: str
    payload: dict[str, Any]


def build_history_trend_report(
    recent_run_manifests: Iterable[Mapping[str, Any]],
    delta_summaries: Optional[Sequence[Mapping[str, Any]] | Mapping[Any, Any]] = None,
    title: str = "History Trend Report",
) -> HistoryTrendReport:
    """Build a deterministic history trend report.

    Args:
        recent_run_manifests: Ordered run manifests, newest-first or oldest-first.
        delta_summaries: Optional per-run delta data. A sequence is aligned by
            index. A mapping is resolved by run id first, then by index.
        title: Markdown title for the report.

    Returns:
        HistoryTrendReport with markdown text and a JSON-friendly payload.
    """

    normalized_runs = [
        _normalize_manifest(manifest, index)
        for index, manifest in enumerate(recent_run_manifests)
    ]

    normalized_deltas = [
        _normalize_delta(delta_summaries, run["run_id"], run["index"])
        for run in normalized_runs
    ]

    for run, delta in zip(normalized_runs, normalized_deltas):
        run["delta_summary"] = delta

    payload = _build_payload(title, normalized_runs)
    markdown = _build_markdown(title, payload)
    return HistoryTrendReport(markdown=markdown, payload=payload)


def render_history_trend_markdown(
    recent_run_manifests: Iterable[Mapping[str, Any]],
    delta_summaries: Optional[Sequence[Mapping[str, Any]] | Mapping[Any, Any]] = None,
    title: str = "History Trend Report",
) -> str:
    """Return only the markdown representation."""

    return build_history_trend_report(
        recent_run_manifests=recent_run_manifests,
        delta_summaries=delta_summaries,
        title=title,
    ).markdown


def build_history_trend_payload(
    recent_run_manifests: Iterable[Mapping[str, Any]],
    delta_summaries: Optional[Sequence[Mapping[str, Any]] | Mapping[Any, Any]] = None,
    title: str = "History Trend Report",
) -> dict[str, Any]:
    """Return only the JSON-friendly payload."""

    return build_history_trend_report(
        recent_run_manifests=recent_run_manifests,
        delta_summaries=delta_summaries,
        title=title,
    ).payload


def _normalize_manifest(manifest: Mapping[str, Any], index: int) -> dict[str, Any]:
    run_id = _first_present(manifest, ("run_id", "id", "name"))
    if run_id is None or run_id == "":
        run_id = f"run-{index + 1}"

    status = _first_present(manifest, ("status", "state", "result"))
    status = _normalize_status(status)

    duration_seconds = _coerce_float(
        _first_present(
            manifest,
            ("duration_seconds", "duration_sec", "elapsed_seconds", "elapsed", "duration"),
        )
    )

    metrics = _sanitize_mapping(manifest.get("metrics"))
    details = _extract_details(manifest)

    return {
        "index": index,
        "run_id": _stringify(run_id),
        "status": status,
        "started_at": _json_safe(
            _first_present(manifest, ("started_at", "start_time", "started", "timestamp"))
        ),
        "finished_at": _json_safe(
            _first_present(manifest, ("finished_at", "end_time", "completed_at"))
        ),
        "duration_seconds": duration_seconds,
        "metrics": metrics,
        "details": details,
    }


def _normalize_delta(
    delta_summaries: Optional[Sequence[Mapping[str, Any]] | Mapping[Any, Any]],
    run_id: str,
    index: int,
) -> Any:
    if delta_summaries is None:
        return None

    candidate: Any = None
    if isinstance(delta_summaries, Mapping):
        if run_id in delta_summaries:
            candidate = delta_summaries[run_id]
        elif index in delta_summaries:
            candidate = delta_summaries[index]
        elif str(index) in delta_summaries:
            candidate = delta_summaries[str(index)]
    else:
        if 0 <= index < len(delta_summaries):
            candidate = delta_summaries[index]

    return _sanitize_value(candidate)


def _build_payload(title: str, runs: Sequence[MutableMapping[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    total_duration = 0.0
    duration_count = 0
    success_count = 0
    failure_count = 0

    payload_runs: list[dict[str, Any]] = []
    for run in runs:
        status = run["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

        duration = run["duration_seconds"]
        if isinstance(duration, (int, float)):
            total_duration += float(duration)
            duration_count += 1

        if status in SUCCESS_STATUSES:
            success_count += 1
        if status in FAILURE_STATUSES:
            failure_count += 1

        payload_runs.append(
            {
                "index": run["index"],
                "run_id": run["run_id"],
                "status": status,
                "started_at": run["started_at"],
                "finished_at": run["finished_at"],
                "duration_seconds": duration,
                "metrics": run["metrics"],
                "details": run["details"],
                "delta_summary": run["delta_summary"],
            }
        )

    average_duration = None
    if duration_count:
        average_duration = total_duration / duration_count

    return {
        "title": title,
        "total_runs": len(payload_runs),
        "status_counts": dict(sorted(status_counts.items(), key=lambda item: item[0])),
        "successful_runs": success_count,
        "failed_runs": failure_count,
        "average_duration_seconds": average_duration,
        "runs": payload_runs,
    }


def _build_markdown(title: str, payload: Mapping[str, Any]) -> str:
    lines = [f"# {title}", ""]
    lines.append(f"Runs analyzed: {payload['total_runs']}")
    lines.append(f"Status counts: {_format_counts(payload['status_counts'])}")

    average_duration = payload["average_duration_seconds"]
    lines.append(f"Average duration: {_format_duration(average_duration)}")
    lines.append("")
    lines.append("| Run | Status | Duration | Delta | Details |")
    lines.append("| --- | --- | --- | --- | --- |")

    for run in payload["runs"]:
        lines.append(
            "| {run_id} | {status} | {duration} | {delta} | {details} |".format(
                run_id=_escape_table_cell(run["run_id"]),
                status=_escape_table_cell(run["status"]),
                duration=_escape_table_cell(_format_duration(run["duration_seconds"])),
                delta=_escape_table_cell(_format_delta_cell(run["delta_summary"])),
                details=_escape_table_cell(_format_details_cell(run["details"], run["metrics"])),
            )
        )

    return "\n".join(lines)


def _extract_details(manifest: Mapping[str, Any]) -> dict[str, Any]:
    details: dict[str, Any] = {}

    for key in sorted(manifest.keys(), key=str):
        if key in COMMON_MANIFEST_KEYS:
            continue
        value = manifest[key]
        if _is_scalar(value):
            details[str(key)] = _json_safe(value)

    return details


def _format_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts.keys(), key=str))


def _format_details_cell(details: Mapping[str, Any], metrics: Optional[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for key in sorted(details.keys(), key=str):
        parts.append(f"{key}={_format_inline_value(details[key])}")
    if isinstance(metrics, Mapping):
        for key in sorted(metrics.keys(), key=str):
            parts.append(f"metrics.{key}={_format_inline_value(metrics[key])}")
    return "; ".join(parts) if parts else "-"


def _format_delta_cell(delta: Any) -> str:
    if delta is None:
        return "-"
    if isinstance(delta, Mapping):
        summary = delta.get("summary")
        text = delta.get("text")
        if summary is not None:
            return _format_inline_value(summary)
        if text is not None:
            return _format_inline_value(text)

        numeric_bits: list[str] = []
        for key in ("added", "removed", "changed", "improved", "regressed"):
            value = delta.get(key)
            if isinstance(value, (int, float)) and value:
                sign = "+" if value > 0 and key in {"added", "changed", "improved"} else ""
                numeric_bits.append(f"{sign}{_format_number(value)} {key}")
        if numeric_bits:
            return ", ".join(numeric_bits)

        return ", ".join(
            f"{key}={_format_inline_value(delta[key])}" for key in sorted(delta.keys(), key=str)
        )

    return _format_inline_value(delta)


def _format_inline_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return _format_number(value)
    return str(value)


def _format_duration(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "n/a"
    if isinstance(value, int):
        return f"{value}s"
    if isinstance(value, float):
        return f"{_format_number(value)}s"
    return str(value)


def _format_number(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _normalize_status(value: Any) -> str:
    if value is None:
        return "unknown"
    status = str(value).strip().lower()
    return status or "unknown"


def _escape_table_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _first_present(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _sanitize_mapping(value: Any) -> Optional[dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    return {str(key): _json_safe(value[key]) for key in sorted(value.keys(), key=str)}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _sanitize_value(value[key]) for key in sorted(value.keys(), key=str)}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value]
    return _json_safe(value)


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return str(value)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _stringify(value: Any) -> str:
    return "" if value is None else str(value)


__all__ = [
    "HistoryTrendReport",
    "build_history_trend_payload",
    "build_history_trend_report",
    "render_history_trend_markdown",
]
