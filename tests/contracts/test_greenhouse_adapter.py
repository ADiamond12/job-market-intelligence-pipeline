from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jobintel.config import AppConfig, CompanyConfig
from jobintel.domain.models import SourceType
from jobintel.observability.logging import setup_logging
from jobintel.sources.greenhouse import GreenhouseAdapter


def test_greenhouse_adapter_parses_fixture(tmp_path: Path) -> None:
    payload = json.loads(Path("tests/fixtures/greenhouse_fixture.json").read_text(encoding="utf-8"))
    config = AppConfig(
        companies=[CompanyConfig(name="Acme Analytics", source_type=SourceType.GREENHOUSE, identifier="acme")],
    )
    adapter = GreenhouseAdapter(
        company=config.companies[0],
        config=config,
        logger=setup_logging(tmp_path / "logs", "gh-contract"),
    )

    jobs = adapter.parse_payload(payload, fetched_at=datetime.now(timezone.utc))

    assert len(jobs) == 2
    assert jobs[0].company_name == "Acme Analytics"
    assert jobs[0].title_raw == "Senior Data Engineer, Platform"
    assert "Airflow" in jobs[0].description_text
    assert jobs[1].department == "Business Intelligence"
