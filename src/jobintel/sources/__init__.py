from __future__ import annotations

from jobintel.config import AppConfig, CompanyConfig
from jobintel.domain.models import SourceType
from jobintel.sources.base import BaseSourceAdapter
from jobintel.sources.greenhouse import GreenhouseAdapter
from jobintel.sources.lever import LeverAdapter


def build_adapter(company: CompanyConfig, config: AppConfig, logger) -> BaseSourceAdapter:
    if company.source_type == SourceType.GREENHOUSE:
        return GreenhouseAdapter(company=company, config=config, logger=logger)
    if company.source_type == SourceType.LEVER:
        return LeverAdapter(company=company, config=config, logger=logger)
    raise ValueError(f"Unsupported source type: {company.source_type}")
