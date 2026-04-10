from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator

from jobintel.domain.models import SourceType


class DirectoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    reports_dir: Path = Path("reports")
    manifests_dir: Path = Path("artifacts/manifests")
    history_dir: Path = Path("artifacts/history")
    logs_dir: Path = Path("logs")


class RetryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempts: int = 3
    backoff_seconds: float = 1.5
    timeout_seconds: int = 30


class DedupeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    similarity_threshold: float = 0.82


class AIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    endpoint: str = "https://api.openai.com/v1/responses"
    timeout_seconds: int = 45
    max_jobs_for_enrichment: int = 25
    temperature: float = 0.1
    max_description_chars: int = 2500
    narrative_top_n: int = 8


class CompanyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source_type: SourceType
    identifier: str
    careers_url: str | None = None
    fixture_path: Path | None = None
    enabled: bool = True


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str = "Job Market Intelligence Pipeline"
    user_agent: str = (
        "job-market-intel/0.1.0 "
        "(+https://github.com/ADiamond27/job-market-intelligence-pipeline)"
    )
    directories: DirectoryConfig = Field(default_factory=DirectoryConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    dedupe: DedupeConfig = Field(default_factory=DedupeConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    companies: list[CompanyConfig]
    history_scope: str | None = None
    config_path: Path | None = None

    @model_validator(mode="after")
    def validate_companies(self) -> "AppConfig":
        enabled_companies = [company for company in self.companies if company.enabled]
        if not enabled_companies:
            raise ValueError("At least one enabled company must be configured.")
        return self

    @property
    def comparison_scope(self) -> str:
        if self.history_scope:
            return f"named:{self.history_scope}"

        enabled_companies = [
            {
                "identifier": company.identifier,
                "source_type": str(company.source_type),
            }
            for company in self.companies
            if company.enabled
        ]
        enabled_companies.sort(key=lambda item: (item["source_type"], item["identifier"]))
        digest = hashlib.sha256(json.dumps(enabled_companies, sort_keys=True).encode("utf-8")).hexdigest()
        return f"companies:{digest}"


def _resolve_path(base_dir: Path, value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _resolve_paths(payload: dict[str, Any], config_dir: Path) -> dict[str, Any]:
    directories = payload.get("directories", {})
    for key in ("raw_dir", "processed_dir", "reports_dir", "manifests_dir", "history_dir", "logs_dir"):
        if key in directories:
            directories[key] = str(_resolve_path(config_dir, directories[key]))
    payload["directories"] = directories

    resolved_companies = []
    for company in payload.get("companies", []):
        company_payload = dict(company)
        if company_payload.get("fixture_path"):
            company_payload["fixture_path"] = str(
                _resolve_path(config_dir, company_payload["fixture_path"])
            )
        resolved_companies.append(company_payload)
    payload["companies"] = resolved_companies
    payload["config_path"] = str((config_dir / Path(payload.get("_config_filename", ""))).resolve())
    return payload


def load_config(config_path: str | Path) -> AppConfig:
    load_dotenv()

    path = Path(config_path).resolve()
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    payload["_config_filename"] = path.name
    resolved_payload = _resolve_paths(payload, path.parent)
    resolved_payload.pop("_config_filename", None)
    return AppConfig.model_validate(resolved_payload)
