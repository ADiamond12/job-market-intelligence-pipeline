from jobintel.reporting.history_report import build_history_trend_report


def test_build_history_trend_report_renders_deterministic_markdown_and_payload():
    manifests = [
        {
            "run_id": "build-001",
            "status": "passed",
            "duration_seconds": 12,
            "branch": "main",
            "owner": "team-a",
            "metrics": {"coverage": 0.91, "score": 7},
        },
        {
            "id": "build-002",
            "state": "failed",
            "elapsed": "18",
            "owner": "team-b",
            "branch": "main",
            "metrics": {"score": 3, "coverage": 0.82},
        },
    ]
    deltas = [
        {"summary": "improved coverage", "added": 2, "removed": 1},
        {"text": "regressed throughput"},
    ]

    report = build_history_trend_report(manifests, deltas)

    expected_markdown = (
        "# History Trend Report\n\n"
        "Runs analyzed: 2\n"
        "Status counts: failed=1, passed=1\n"
        "Average duration: 15s\n\n"
        "| Run | Status | Duration | Delta | Details |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| build-001 | passed | 12s | improved coverage | branch=main; owner=team-a; metrics.coverage=0.91; metrics.score=7 |\n"
        "| build-002 | failed | 18s | regressed throughput | branch=main; owner=team-b; metrics.coverage=0.82; metrics.score=3 |"
    )

    assert report.markdown == expected_markdown
    assert report.payload == {
        "title": "History Trend Report",
        "total_runs": 2,
        "status_counts": {"failed": 1, "passed": 1},
        "successful_runs": 1,
        "failed_runs": 1,
        "average_duration_seconds": 15.0,
        "runs": [
            {
                "index": 0,
                "run_id": "build-001",
                "status": "passed",
                "started_at": None,
                "finished_at": None,
                "duration_seconds": 12.0,
                "metrics": {"coverage": 0.91, "score": 7},
                "details": {"branch": "main", "owner": "team-a"},
                "delta_summary": {
                    "added": 2,
                    "removed": 1,
                    "summary": "improved coverage",
                },
            },
            {
                "index": 1,
                "run_id": "build-002",
                "status": "failed",
                "started_at": None,
                "finished_at": None,
                "duration_seconds": 18.0,
                "metrics": {"coverage": 0.82, "score": 3},
                "details": {"branch": "main", "owner": "team-b"},
                "delta_summary": {"text": "regressed throughput"},
            },
        ],
    }


def test_build_history_trend_report_is_stable_across_manifest_key_order():
    manifest_a = {
        "run_id": "run-stable",
        "status": "success",
        "duration": 9,
        "z_field": "last",
        "a_field": "first",
        "metrics": {"b": 2, "a": 1},
    }
    manifest_b = {
        "metrics": {"a": 1, "b": 2},
        "a_field": "first",
        "z_field": "last",
        "duration": 9,
        "status": "success",
        "run_id": "run-stable",
    }

    report_a = build_history_trend_report([manifest_a])
    report_b = build_history_trend_report([manifest_b])

    assert report_a.markdown == report_b.markdown
    assert report_a.payload == report_b.payload
    assert "a_field=first; z_field=last; metrics.a=1; metrics.b=2" in report_a.markdown
