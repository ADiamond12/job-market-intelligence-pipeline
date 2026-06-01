from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from typing import Any

from jobintel.domain.models import AIReportInsight


def render_market_summary_markdown(
    run_id: str,
    metrics: dict[str, Any],
    quality_report: dict[str, Any],
    ai_insight: AIReportInsight,
    delta_summary: dict[str, Any] | None = None,
) -> str:
    lines = [
        "# Job Market Intelligence Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Published jobs: **{metrics.get('total_jobs', 0)}**",
        f"- Companies tracked: **{metrics.get('companies_tracked', 0)}**",
        "",
        "## Run Summary",
        ai_insight.summary,
        "",
    ]

    if delta_summary:
        lines.extend(
            [
                "## Movement Since Previous Run",
                f"- Baseline run: {delta_summary.get('baseline_run_id') or 'n/a'}",
                f"- New jobs: {delta_summary.get('new_jobs', 0)}",
                f"- Removed jobs: {delta_summary.get('removed_jobs', 0)}",
                f"- Changed jobs: {delta_summary.get('changed_jobs', 0)}",
                f"- Net change: {delta_summary.get('net_change', 0)}",
                "",
            ]
        )

    lines.append("## Skills Appearing Most Often")
    for item in metrics.get("top_skills", [])[:8]:
        lines.append(f"- {item['skill']}: {item['count']} postings")

    lines.extend(
        [
            "",
            "## Hiring Shape",
            f"- Role families: {_distribution_text(metrics.get('role_family_distribution', {}))}",
            f"- Seniority: {_distribution_text(metrics.get('seniority_distribution', {}))}",
            f"- Workplace mix: {_distribution_text(metrics.get('workplace_distribution', {}))}",
            "",
            "## Source And Data Quality",
            f"- Collected jobs: {quality_report.get('collected_jobs', 0)}",
            f"- Published jobs: {quality_report.get('published_jobs', 0)}",
            f"- Quarantined jobs: {quality_report.get('quarantined_jobs', 0)}",
            f"- Duplicates removed: {quality_report.get('duplicates_removed', 0)}",
            "",
            "## Optional Narrative Signals",
        ]
    )
    for signal in ai_insight.emerging_signals:
        lines.append(f"- {signal}")

    lines.extend(["", "## Evidence Notes"])
    for item in ai_insight.evidence:
        lines.append(f"- {item}")

    return "\n".join(lines).strip() + "\n"


def render_market_summary(
    run_id: str,
    metrics: dict[str, Any],
    quality_report: dict[str, Any],
    ai_insight: AIReportInsight,
    delta_summary: dict[str, Any] | None = None,
) -> str:
    title = "Job Market Intelligence Report"
    sections = [
        _render_header(title, run_id, metrics, quality_report),
        _render_decision_view(),
        _render_overview(metrics, quality_report, ai_insight),
    ]

    if delta_summary:
        sections.append(_render_delta_summary(delta_summary))

    sections.extend(
        [
            _render_skill_trends(metrics),
            _render_hiring_shape(metrics),
            _render_quality(metrics, quality_report),
            _render_ai_signals(ai_insight),
            _render_evidence(ai_insight),
        ]
    )

    body = "\n".join(section for section in sections if section)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{escape(title)}</title>\n"
        f"  <style>{_styles()}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def _render_header(title: str, run_id: str, metrics: dict[str, Any], quality_report: dict[str, Any]) -> str:
    return "\n".join(
        [
            '<header class="hero">',
            f"  <p class=\"eyebrow\">Run {escape(str(run_id))}</p>",
            f"  <h1>{escape(title)}</h1>",
            "  <p class=\"lede\">An ATS watchlist report that turns collection, validation, enrichment, and history into one reviewable market artifact.</p>",
            '  <div class="hero-grid">',
            _stat_card("Published jobs", _format_number(metrics.get("total_jobs", 0))),
            _stat_card("Companies tracked", _format_number(metrics.get("companies_tracked", 0))),
            _stat_card("Collected jobs", _format_number(quality_report.get("collected_jobs", 0))),
            _stat_card("Duplicates removed", _format_number(quality_report.get("duplicates_removed", 0))),
            "  </div>",
            "</header>",
        ]
    )


def _render_decision_view() -> str:
    return _section(
        "Decision View",
        [
            '<div class="panel-grid">',
            _overview_card("Open first", "Run-to-run movement and source quality"),
            _overview_card("Use for", "A repeatable watchlist review, not a one-off scrape"),
            _overview_card("Evidence", "Fixture-backed inputs, manifests, DuckDB history, and report outputs"),
            "</div>",
        ],
    )


def _render_overview(metrics: dict[str, Any], quality_report: dict[str, Any], ai_insight: AIReportInsight) -> str:
    salary_coverage = metrics.get("salary_coverage", {})
    completeness = quality_report.get("completeness", {})
    top_company = _first_item(metrics.get("top_companies", {}))
    top_title = _first_item(metrics.get("top_titles", {}))

    items = [
        ("Top company", top_company or "No data"),
        ("Top title", top_title or "No data"),
        ("Salary coverage", _format_salary_coverage(salary_coverage)),
        ("Description completeness", _format_pct(completeness.get("description_text_pct"))),
        (
            "Narrative confidence",
            _format_pct(ai_insight.confidence * 100 if ai_insight.confidence is not None else None),
        ),
    ]
    return _section(
        "Run Snapshot",
        [
            '<div class="panel-grid">',
            *(_overview_card(label, value) for label, value in items),
            "</div>",
        ],
    )


def _render_delta_summary(delta_summary: Mapping[str, Any]) -> str:
    preferred_order = (
        "baseline_run_id",
        "new_jobs",
        "removed_jobs",
        "changed_jobs",
        "unchanged_jobs",
        "net_change",
    )
    items = [
        (key, delta_summary[key])
        for key in preferred_order
        if key in delta_summary
    ]
    items.extend(
        (key, value)
        for key, value in sorted(delta_summary.items(), key=lambda item: item[0])
        if key not in preferred_order
    )
    numeric_values = [abs(value) for _, value in items if isinstance(value, (int, float))]
    scale = max(numeric_values) if numeric_values else 0

    cards = []
    for key, value in items:
        if isinstance(value, (int, float)):
            cards.append(_delta_card(key, value, scale))
        else:
            cards.append(
                '<article class="delta-card">'
                f"  <h3>{escape(_humanize_label(str(key)))}</h3>"
                f"  <p>{escape(_stringify_value(value))}</p>"
                "</article>"
            )

    return _section("Run-to-run Movement", ['<div class="delta-grid">', *cards, "</div>"])


def _render_skill_trends(metrics: dict[str, Any]) -> str:
    return _section(
        "Skills Appearing Most Often",
        [_render_ranked_bars(metrics.get("top_skills", []), "skill", "count", empty_label="No skill data")],
    )


def _render_hiring_shape(metrics: dict[str, Any]) -> str:
    role_family = metrics.get("role_family_distribution", {})
    seniority = metrics.get("seniority_distribution", {})
    workplace = metrics.get("workplace_distribution", {})

    return _section(
        "Hiring Shape",
        [
            '<div class="shape-grid">',
            _distribution_card("Role families", role_family),
            _distribution_card("Seniority", seniority),
            _distribution_card("Workplace mix", workplace),
            "</div>",
        ],
    )


def _render_quality(metrics: dict[str, Any], quality_report: dict[str, Any]) -> str:
    issue_counts = quality_report.get("issue_counts_by_severity", {})
    source_coverage = quality_report.get("source_coverage", {})
    completeness = quality_report.get("completeness", {})
    salary_coverage = metrics.get("salary_coverage", {})

    return _section(
        "Source And Data Quality",
        [
            '<div class="shape-grid">',
            _distribution_card(
                "Issue severity",
                issue_counts,
                empty_label="No validation issues",
            ),
            _distribution_card(
                "Source coverage",
                source_coverage,
                empty_label="No source coverage data",
            ),
            _distribution_card(
                "Completeness",
                {
                    "description": completeness.get("description_text_pct", 0.0),
                    "posted_at": completeness.get("posted_at_pct", 0.0),
                    "location": completeness.get("location_pct", 0.0),
                    "salary": completeness.get("salary_pct", 0.0),
                },
                empty_label="No completeness data",
                value_is_percent=True,
            ),
            "</div>",
            _key_value_table(
                [
                    ("Published jobs", quality_report.get("published_jobs", 0)),
                    ("Quarantined jobs", quality_report.get("quarantined_jobs", 0)),
                    ("Duplicates removed", quality_report.get("duplicates_removed", 0)),
                    ("Jobs with salary", salary_coverage.get("jobs_with_salary", 0)),
                ]
            ),
        ],
    )


def _render_ai_signals(ai_insight: AIReportInsight) -> str:
    signals = ai_insight.emerging_signals or []
    signal_items = "".join(f"<li>{escape(signal)}</li>" for signal in signals) or "<li>No emerging signals.</li>"
    return _section(
        "Optional Narrative Signals",
        [
            f'<div class="quote">{escape(ai_insight.summary)}</div>',
            f'<div class="pill-row"><span class="pill">Confidence {escape(_format_pct(ai_insight.confidence * 100 if ai_insight.confidence is not None else None))}</span>{_model_pill(ai_insight.model)}</div>',
            f"<ul class=\"bullets\">{signal_items}</ul>",
        ],
    )


def _render_evidence(ai_insight: AIReportInsight) -> str:
    evidence = ai_insight.evidence or []
    items = "".join(f"<li>{escape(item)}</li>" for item in evidence) or "<li>No evidence provided.</li>"
    return _section("Evidence Notes", [f"<ul class=\"bullets\">{items}</ul>"])


def _render_ranked_bars(
    items: Sequence[Any],
    label_key: str,
    value_key: str,
    *,
    empty_label: str,
) -> str:
    normalized = []
    for item in items:
        if isinstance(item, Mapping):
            label = item.get(label_key)
            value = item.get(value_key, 0)
            normalized.append((str(label), value))
    if not normalized:
        return f'<div class="empty">{escape(empty_label)}</div>'

    max_value = max((float(value) for _, value in normalized), default=0.0)
    rows = []
    for label, value in normalized:
        rows.append(_bar_row(label, value, max_value))
    return '<div class="bars">' + "".join(rows) + "</div>"


def _distribution_card(
    title: str,
    distribution: Mapping[str, Any],
    *,
    empty_label: str = "No data",
    value_is_percent: bool = False,
) -> str:
    normalized = _sorted_distribution(distribution)
    if not normalized:
        return (
            '<article class="card">'
            f"  <h3>{escape(title)}</h3>"
            f"  <div class=\"empty\">{escape(empty_label)}</div>"
            "</article>"
        )

    max_value = max((float(value) for _, value in normalized), default=0.0)
    rows = []
    for label, value in normalized:
        display_value = _format_value(value, percent=value_is_percent)
        rows.append(_bar_row(label, display_value, max_value, raw_value=value))

    return (
        '<article class="card">'
        f"  <h3>{escape(title)}</h3>"
        f"  <div class=\"bars\">{''.join(rows)}</div>"
        "</article>"
    )


def _bar_row(
    label: str,
    display_value: Any,
    max_value: float,
    *,
    raw_value: Any | None = None,
) -> str:
    actual_value = raw_value if raw_value is not None else display_value
    numeric = float(actual_value) if isinstance(actual_value, (int, float)) else 0.0
    width = 0 if max_value <= 0 else max(4, round((numeric / max_value) * 100))
    return (
        '<div class="bar-row">'
        f"  <div class=\"bar-row__label\">{escape(str(label))}</div>"
        f"  <div class=\"bar-row__track\"><div class=\"bar-row__fill\" style=\"width:{width}%\"></div></div>"
        f"  <div class=\"bar-row__value\">{escape(str(display_value))}</div>"
        "</div>"
    )


def _delta_card(label: str, value: float, scale: float) -> str:
    if scale <= 0:
        width = 100
    else:
        width = max(4, round((abs(float(value)) / scale) * 100))
    kind = "positive" if value > 0 else "negative" if value < 0 else "neutral"
    return (
        f'<article class="delta-card delta-card--{kind}">'
        f"  <h3>{escape(_humanize_label(str(label)))}</h3>"
        f"  <p class=\"delta-value\">{escape(_format_signed_number(value))}</p>"
        f"  <div class=\"delta-track\"><div class=\"delta-fill\" style=\"width:{width}%\"></div></div>"
        "</article>"
    )


def _humanize_label(value: str) -> str:
    known_labels = {
        "baseline_run_id": "Baseline run",
        "new_jobs": "New jobs",
        "removed_jobs": "Removed jobs",
        "changed_jobs": "Changed jobs",
        "unchanged_jobs": "Unchanged jobs",
        "net_change": "Net change",
    }
    if value in known_labels:
        return known_labels[value]
    return value.replace("_", " ").strip().title()


def _overview_card(label: str, value: Any) -> str:
    return (
        '<article class="card">'
        f"  <h3>{escape(label)}</h3>"
        f"  <p class=\"metric\">{escape(_stringify_value(value))}</p>"
        "</article>"
    )


def _stat_card(label: str, value: str) -> str:
    return (
        '    <article class="stat">'
        f"      <span>{escape(label)}</span>"
        f"      <strong>{escape(value)}</strong>"
        "    </article>"
    )


def _key_value_table(items: Sequence[tuple[str, Any]]) -> str:
    rows = []
    for label, value in items:
        rows.append(
            "<tr>"
            f"<th>{escape(str(label))}</th>"
            f"<td>{escape(_stringify_value(value))}</td>"
            "</tr>"
        )
    return '<table class="kv-table">' + "".join(rows) + "</table>"


def _section(title: str, fragments: Sequence[str]) -> str:
    return (
        '<section class="section">'
        f"  <h2>{escape(title)}</h2>"
        f"  {''.join(fragments)}"
        "</section>"
    )


def _model_pill(model: str | None) -> str:
    if not model:
        return ""
    return f'<span class="pill pill--subtle">{escape(model)}</span>'


def _format_salary_coverage(salary_coverage: Mapping[str, Any]) -> str:
    jobs_with_salary = salary_coverage.get("jobs_with_salary", 0)
    median_min = salary_coverage.get("median_salary_min")
    median_max = salary_coverage.get("median_salary_max")
    if median_min is None and median_max is None:
        return f"{jobs_with_salary} jobs with salary"
    if median_min is None or median_max is None:
        return f"{jobs_with_salary} jobs with salary"
    return f"{jobs_with_salary} jobs with salary, median ${_format_number(median_min)}-${_format_number(median_max)}"


def _format_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{_format_number(value)}%"


def _format_number(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.1f}"
    return str(value)


def _format_signed_number(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{_format_number(value)}"


def _format_value(value: Any, *, suffix: str = "", percent: bool = False) -> str:
    formatted = _format_number(value)
    if percent:
        return f"{formatted}%"
    if suffix:
        return f"{formatted}{suffix}"
    return formatted


def _stringify_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, dict):
        return ", ".join(f"{key}: {_stringify_value(value[key])}" for key in sorted(value))
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_stringify_value(item) for item in value) or "n/a"
    return _format_number(value)


def _sorted_distribution(distribution: Mapping[str, Any]) -> list[tuple[str, Any]]:
    return sorted(
        ((str(label), value) for label, value in distribution.items()),
        key=lambda item: (-float(item[1]), item[0]) if isinstance(item[1], (int, float)) else (0.0, item[0]),
    )


def _first_item(items: Mapping[str, Any]) -> str:
    normalized = _sorted_distribution(items)
    if not normalized:
        return ""
    label, value = normalized[0]
    return f"{label} ({_stringify_value(value)})"


def _styles() -> str:
    return (
        ":root{color-scheme:light;--bg:#f6f5f1;--panel:#ffffff;--panel-2:#f8f7f3;--text:#1d2328;"
        "--muted:#5e6a72;--accent:#0f766e;--accent-2:#9a5b00;--border:#d9d6cd;--shadow:0 1px 2px rgba(31,41,55,.08);}"
        "*{box-sizing:border-box}body{margin:0;overflow-x:hidden;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;"
        "background:var(--bg);color:var(--text);line-height:1.5;}"
        "html{scroll-behavior:smooth}.hero,.section{width:min(1120px,calc(100vw - 32px));margin:22px auto;padding:24px;background:var(--panel);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);position:relative;z-index:1;}"
        ".hero{padding:30px;border-top:6px solid #17212b}.hero h1,.section h2{margin:0 0 12px;letter-spacing:0;overflow-wrap:anywhere;word-break:break-word}.hero h1{max-width:100%;font-size:clamp(1.85rem,4vw,3.1rem);line-height:1.08}"
        ".eyebrow{margin:0 0 8px;text-transform:uppercase;letter-spacing:.08em;color:var(--accent);font-size:.76rem;font-weight:700}.lede{max-width:70ch;color:var(--muted);margin:0 0 20px;overflow-wrap:anywhere}"
        ".hero-grid,.panel-grid,.shape-grid,.delta-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}.card,.stat,.delta-card{min-width:0;background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px}"
        ".card h3,.delta-card h3{margin:0 0 10px;font-size:.88rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);overflow-wrap:anywhere}.metric{margin:0;font-size:1.1rem;font-weight:700;overflow-wrap:anywhere}.stat span{display:block;color:var(--muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.06em;overflow-wrap:anywhere}.stat strong{display:block;font-size:1.4rem;margin-top:6px}"
        ".bars{display:grid;gap:10px}.bar-row{display:grid;grid-template-columns:1.2fr 2fr auto;gap:12px;align-items:center}.bar-row__label,.bar-row__value{font-size:.95rem}.bar-row__label{color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.bar-row__track,.delta-track{height:12px;background:#ebe8df;border-radius:999px;overflow:hidden;border:1px solid #d9d6cd}.bar-row__fill,.delta-fill{height:100%;border-radius:inherit;background:var(--accent)}.delta-card--negative .delta-fill{background:#b43f2f}.delta-card--positive .delta-fill{background:#0c7b5d}"
        ".delta-value{margin:0 0 10px;font-size:1.6rem;font-weight:800}.quote{padding:16px;border-left:4px solid var(--accent-2);background:var(--panel-2);border-radius:14px;margin-bottom:12px;color:var(--text)}"
        ".pill-row{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}.pill{display:inline-flex;align-items:center;border-radius:999px;padding:4px 10px;background:rgba(15,118,110,.12);color:var(--accent);font-size:.78rem;font-weight:700}.pill--subtle{background:rgba(217,119,6,.12);color:var(--accent-2)}"
        ".bullets{margin:0;padding-left:20px;color:var(--text)}.bullets li{margin:6px 0}.kv-table{width:100%;table-layout:fixed;border-collapse:collapse;margin-top:14px;background:var(--panel);border:1px solid var(--border);border-radius:16px;overflow:hidden}.kv-table th,.kv-table td{padding:12px 14px;border-top:1px solid #ebe3d8;text-align:left;overflow-wrap:anywhere}.kv-table tr:first-child th,.kv-table tr:first-child td{border-top:none}.kv-table th{width:55%;color:var(--muted);font-weight:600}.empty{padding:14px;border:1px dashed var(--border);border-radius:14px;color:var(--muted);background:rgba(255,255,255,.55)}"
        "@media (max-width:720px){.bar-row{grid-template-columns:1fr;}.hero,.section{width:calc(100vw - 20px);padding:18px;border-radius:18px}.hero h1{font-size:clamp(1.5rem,7vw,1.75rem)}.hero-grid,.panel-grid,.shape-grid,.delta-grid{grid-template-columns:1fr}}"
    )


def _distribution_text(distribution: Mapping[str, Any]) -> str:
    if not distribution:
        return "No data"
    items = _sorted_distribution(distribution)
    return ", ".join(f"{label}: {_stringify_value(value)}" for label, value in items)
