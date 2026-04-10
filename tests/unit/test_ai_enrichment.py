from __future__ import annotations

import json
from datetime import datetime, timezone

from jobintel.config import AIConfig
from jobintel.domain.models import JobPosting, SourceType
from jobintel.enrichment.classification import enrich_jobs
from jobintel.enrichment.llm_client import OpenAIResponsesClient
from jobintel.observability.logging import setup_logging


def _ambiguous_job() -> JobPosting:
    return JobPosting(
        job_id="job-1",
        source_type=SourceType.LEVER,
        vendor="lever",
        company_name="BrightOps",
        company_slug="brightops",
        source_job_id="job-1",
        source_url="https://example.com/jobs",
        canonical_url="https://example.com/jobs/1",
        title_raw="Platform Specialist",
        location_raw="Remote, United States",
        posted_at=datetime.now(timezone.utc),
        description_html="<p>Own internal tools, automate workflows, and build Python APIs for data teams.</p>",
    )


def test_openai_client_parses_mocked_classification(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = OpenAIResponsesClient(AIConfig(enabled=True))
    monkeypatch.setattr(
        client,
        "_post",
        lambda payload: {
            "output_text": json.dumps(
                {
                    "role_family": "backend",
                    "seniority": "senior",
                    "confidence": 0.91,
                    "evidence_snippets": ["build Python APIs"],
                }
            )
        },
    )

    result = client.classify_job(_ambiguous_job())

    assert result is not None
    assert result.role_family == "backend"
    assert result.confidence == 0.91


def test_enrich_jobs_falls_back_when_ai_fails(monkeypatch, tmp_path) -> None:
    class FailingClient:
        def __init__(self, settings):
            self.available = True

        def classify_job(self, job):
            raise RuntimeError("boom")

    monkeypatch.setattr("jobintel.enrichment.classification.OpenAIResponsesClient", FailingClient)
    enriched = enrich_jobs(
        [_ambiguous_job()],
        AIConfig(enabled=True),
        setup_logging(tmp_path / "logs", "ai-fallback"),
    )

    assert enriched[0].job_family == "other"
    assert enriched[0].ai_role_family is None
