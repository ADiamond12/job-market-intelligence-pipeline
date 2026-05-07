from __future__ import annotations

from jobintel.domain.models import AIReportInsight
from jobintel.reporting.render import render_market_summary


def test_render_market_summary_produces_standalone_html_and_escapes_content() -> None:
    metrics = {
        "total_jobs": 12,
        "companies_tracked": 4,
        "top_skills": [
            {"skill": "Python & SQL", "count": 8},
            {"skill": "dbt", "count": 5},
        ],
        "role_family_distribution": {"data_platform": 7, "analytics": 5},
        "seniority_distribution": {"senior": 6, "mid": 6},
        "workplace_distribution": {"remote": 9, "hybrid": 3},
        "top_companies": {"Bright <Ops>": 3, "Acme": 2},
        "top_titles": {"Data Engineer": 4, "Analytics Engineer": 3},
        "salary_coverage": {
            "jobs_with_salary": 9,
            "median_salary_min": 120000,
            "median_salary_max": 155000,
        },
    }
    quality_report = {
        "collected_jobs": 15,
        "published_jobs": 12,
        "quarantined_jobs": 2,
        "duplicates_removed": 1,
        "issue_counts_by_severity": {"warning": 3, "error": 1},
        "issue_counts_by_rule": {"salary": 2},
        "completeness": {
            "description_text_pct": 91.7,
            "posted_at_pct": 100.0,
            "location_pct": 83.3,
            "salary_pct": 75.0,
        },
        "source_coverage": {"greenhouse": 8, "lever": 4},
    }
    ai_insight = AIReportInsight(
        summary="Signals point to <script>alert(1)</script> and steady hiring.",
        emerging_signals=["Rising demand for platform work", "More SQL-heavy roles"],
        confidence=0.91,
        evidence=["Bright <Ops>: Data Engineer", "Acme: Analytics Engineer"],
    )
    delta_summary = {
        "jobs_added": 3,
        "jobs_removed": -1,
        "note": "net change <stable>",
    }

    html = render_market_summary("run<&>1", metrics, quality_report, ai_insight, delta_summary)

    assert html.startswith("<!DOCTYPE html>")
    assert "<html lang=\"en\">" in html
    assert "Run-to-run Movement" in html
    assert "Skills Appearing Most Often" in html
    assert "Data Quality" in html
    assert "style=\"width:" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Bright &lt;Ops&gt;" in html
    assert "run&lt;&amp;&gt;1" in html
    assert "<script>" not in html
    assert render_market_summary("run<&>1", metrics, quality_report, ai_insight, delta_summary) == html


def test_render_market_summary_handles_empty_inputs() -> None:
    ai_insight = AIReportInsight(summary="No signal yet.", emerging_signals=[], confidence=0.0, evidence=[])

    html = render_market_summary("empty-run", {}, {}, ai_insight)

    assert "No skill data" in html
    assert "No validation issues" in html
    assert "No emerging signals." in html
    assert "Delta Summary" not in html
    assert html.endswith("</html>\n")
