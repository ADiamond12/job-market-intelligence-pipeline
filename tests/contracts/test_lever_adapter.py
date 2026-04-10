from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jobintel.config import AppConfig, CompanyConfig
from jobintel.domain.models import SourceType
from jobintel.observability.logging import setup_logging
from jobintel.sources.lever import LeverAdapter


def test_lever_adapter_parses_fixture(tmp_path: Path) -> None:
    payload = json.loads(Path("tests/fixtures/lever_fixture.json").read_text(encoding="utf-8"))
    config = AppConfig(
        companies=[CompanyConfig(name="BrightOps", source_type=SourceType.LEVER, identifier="brightops")],
    )
    adapter = LeverAdapter(
        company=config.companies[0],
        config=config,
        logger=setup_logging(tmp_path / "logs", "lever-contract"),
    )

    jobs = adapter.parse_payload(payload, fetched_at=datetime.now(timezone.utc))

    assert len(jobs) == 2
    assert jobs[0].title_raw == "Machine Learning Engineer"
    assert jobs[0].department == "Machine Learning"
    assert "FastAPI" in jobs[0].description_text
    assert jobs[1].location_raw == "London, England, United Kingdom / Hybrid"
