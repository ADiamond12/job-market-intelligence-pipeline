from __future__ import annotations

import logging
import re

from jobintel.config import AIConfig
from jobintel.domain.models import JobPosting
from jobintel.enrichment.llm_client import OpenAIResponsesClient
from jobintel.enrichment.skills import extract_skills

ROLE_FAMILY_RULES = [
    ("machine_learning", (r"\bmachine learning\b", r"\bml engineer\b", r"\bllm\b", r"\bai engineer\b", r"\bnlp\b")),
    ("data_engineering", (r"\bdata engineer\b", r"\betl\b", r"\bpipeline(s)?\b", r"\bwarehouse\b", r"\bairflow\b", r"\bdbt\b")),
    ("analytics", (r"\banalytics\b", r"\bbusiness intelligence\b", r"\bbi\b", r"\banalyst\b", r"\btableau\b", r"\bpower bi\b")),
    ("data_science", (r"\bdata scientist\b", r"\bexperimentation\b", r"\bstatistics\b", r"\bpredictive\b")),
    ("backend", (r"\bbackend\b", r"\bapi\b", r"\bplatform engineer\b", r"\bsoftware engineer\b")),
    ("devops", (r"\bdevops\b", r"\bsite reliability\b", r"\bsre\b", r"\binfrastructure\b")),
    ("security", (r"\bsecurity\b", r"\bapplication security\b")),
    ("product", (r"\bproduct manager\b", r"\bproduct management\b")),
    ("operations", (r"\boperations\b", r"\bprogram manager\b")),
]
SENIORITY_RULES = [
    ("intern", (r"\bintern(ship)?\b",)),
    ("junior", (r"\bjunior\b", r"\bassociate\b", r"\bentry\b")),
    ("mid", (r"\bmid\b",)),
    ("senior", (r"\bsenior\b", r"\bsr\.?\b", r"\blead\b")),
    ("staff", (r"\bstaff\b",)),
    ("principal", (r"\bprincipal\b",)),
    ("manager", (r"\bmanager\b", r"\bhead of\b", r"\bdirector\b", r"\bvp\b")),
]


def enrich_jobs(
    jobs: list[JobPosting],
    ai_config: AIConfig,
    logger: logging.Logger,
) -> list[JobPosting]:
    llm_client = OpenAIResponsesClient(ai_config)
    enriched_jobs: list[JobPosting] = []
    ai_budget_remaining = ai_config.max_jobs_for_enrichment

    for job in jobs:
        deterministic_family = infer_role_family(job.title_normalized or job.title_raw, job.description_text or "")
        deterministic_seniority = infer_seniority(job.title_normalized or job.title_raw, job.description_text or "")
        skills = extract_skills(job.description_text or "")

        candidate = job.model_copy(
            update={
                "job_family": deterministic_family,
                "seniority": deterministic_seniority,
                "extracted_skills": skills,
                "extraction_method": "taxonomy" if skills else None,
            }
        )

        needs_ai = (not deterministic_family or deterministic_family == "other") or not deterministic_seniority
        if needs_ai and llm_client.available and ai_budget_remaining > 0:
            try:
                result = llm_client.classify_job(candidate)
            except Exception as exc:  # noqa: BLE001
                logger.warning("AI job classification failed for %s: %s", candidate.job_id, exc)
                result = None
            if result:
                ai_budget_remaining -= 1
                candidate = candidate.model_copy(
                    update={
                        "job_family": candidate.job_family if candidate.job_family and candidate.job_family != "other" else result.role_family,
                        "seniority": candidate.seniority or result.seniority,
                        "ai_role_family": result.role_family,
                        "ai_seniority": result.seniority,
                        "ai_confidence": result.confidence,
                        "evidence_snippets": result.evidence_snippets,
                    }
                )
        enriched_jobs.append(candidate)
    return enriched_jobs


def infer_role_family(title: str, description: str) -> str:
    title_text = title.lower()
    for family, patterns in ROLE_FAMILY_RULES:
        if any(re.search(pattern, title_text) for pattern in patterns):
            return family

    text = f"{title} {description[:300]}".lower()
    for family, patterns in ROLE_FAMILY_RULES:
        if any(re.search(pattern, text) for pattern in patterns):
            return family
    return "other"


def infer_seniority(title: str, description: str) -> str | None:
    text = f"{title} {description[:150]}".lower()
    for level, patterns in SENIORITY_RULES:
        if any(re.search(pattern, text) for pattern in patterns):
            return level
    return None
