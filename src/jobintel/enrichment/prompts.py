from __future__ import annotations

import json
from typing import Any

from jobintel.domain.models import JobPosting

CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "role_family": {"type": "string"},
        "seniority": {"type": "string"},
        "confidence": {"type": "number"},
        "evidence_snippets": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
    },
    "required": ["role_family", "seniority", "confidence", "evidence_snippets"],
    "additionalProperties": False,
}

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "emerging_signals": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
        "confidence": {"type": "number"},
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
    },
    "required": ["summary", "emerging_signals", "confidence", "evidence"],
    "additionalProperties": False,
}


def build_classification_prompt(job: JobPosting, max_description_chars: int) -> str:
    description_excerpt = (job.description_text or "")[:max_description_chars]
    return (
        "Classify this job posting into a compact role family and seniority. "
        "Prefer categories like data_engineering, data_science, analytics, backend, machine_learning, "
        "platform, devops, product, security, or operations. "
        "Return evidence snippets copied from the posting text.\n\n"
        f"Title: {job.title_normalized or job.title_raw}\n"
        f"Department: {job.department or 'unknown'}\n"
        f"Location: {job.location_raw or 'unknown'}\n"
        f"Description:\n{description_excerpt}"
    )


def build_report_prompt(report_context: dict[str, Any]) -> str:
    payload = json.dumps(report_context, ensure_ascii=False, indent=2)
    return (
        "Write a concise market intelligence summary for a hiring trend report. "
        "Use only the provided metrics, include 2-5 emerging signals, and do not invent facts.\n\n"
        f"{payload}"
    )
