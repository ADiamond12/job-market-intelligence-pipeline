from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobIntelModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class SourceType(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"


class WorkplaceType(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    APPRENTICESHIP = "apprenticeship"
    UNKNOWN = "unknown"


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationIssue(JobIntelModel):
    job_id: str
    rule_id: str
    severity: ValidationSeverity
    field_name: str
    message: str
    detected_at: datetime = Field(default_factory=utc_now)


class JobPosting(JobIntelModel):
    job_id: str
    source_type: SourceType
    vendor: str
    company_name: str
    company_slug: str
    source_job_id: str
    source_url: str
    canonical_url: str
    apply_url: str | None = None
    title_raw: str
    title_normalized: str | None = None
    job_family: str | None = None
    seniority: str | None = None
    department: str | None = None
    workplace_type: WorkplaceType = WorkplaceType.UNKNOWN
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    location_raw: str | None = None
    location_city: str | None = None
    location_region: str | None = None
    location_country: str | None = None
    is_remote: bool = False
    posted_at: datetime | None = None
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)
    closed_at: datetime | None = None
    description_html: str | None = None
    description_text: str | None = None
    salary_raw: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    content_hash: str | None = None
    raw_snapshot_path: str | None = None
    validation_status: str = "pending"
    quality_score: float | None = None
    extracted_skills: list[str] = Field(default_factory=list)
    extraction_method: str | None = None
    ai_role_family: str | None = None
    ai_seniority: str | None = None
    ai_summary: str | None = None
    ai_confidence: float | None = None
    evidence_snippets: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AIClassification(JobIntelModel):
    role_family: str
    seniority: str
    confidence: float
    evidence_snippets: list[str] = Field(default_factory=list)


class AIReportInsight(JobIntelModel):
    summary: str
    emerging_signals: list[str] = Field(default_factory=list)
    confidence: float
    evidence: list[str] = Field(default_factory=list)
    model: str | None = None


class CollectionStats(JobIntelModel):
    company_name: str
    source_type: SourceType
    fetched_jobs: int
    source_url: str
    used_fixture: bool = False


class RunManifest(JobIntelModel):
    run_id: str
    config_path: str
    comparison_scope: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "success"
    source_stats: list[CollectionStats] = Field(default_factory=list)
    totals: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
