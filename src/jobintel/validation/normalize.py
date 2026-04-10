from __future__ import annotations

import hashlib
import re
from html import unescape
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from jobintel.domain.models import EmploymentType, JobPosting, WorkplaceType

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gh_jid",
    "gh_src",
    "lever-source",
}
BOILERPLATE_PATTERNS = (
    "equal opportunity employer",
    "eeo statement",
    "privacy notice",
    "accommodation",
    "recruitment fraud",
)
LOCATION_SPLIT_RE = re.compile(r"\s*[|,/]\s*")
SALARY_RE = re.compile(
    r"(?P<currency>[$€£])\s?(?P<min>\d[\d,]*(?:\.\d+)?)\s*(?P<min_suffix>[kKmM]?)"
    r"(?:\s*(?:-|to)\s*(?P<currency2>[$€£])?\s?(?P<max>\d[\d,]*(?:\.\d+)?)\s*(?P<max_suffix>[kKmM]?))?",
    re.IGNORECASE,
)


def canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    split_url = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(split_url.query, keep_blank_values=False)
        if key.lower() not in TRACKING_PARAMS
    ]
    normalized = split_url._replace(query=urlencode(query, doseq=True), fragment="")
    return urlunsplit(normalized)


def normalize_title(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", title).strip()
    cleaned = re.sub(r"\s*[-|/]\s*(remote|hybrid|onsite|on-site)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.title() if cleaned.isupper() else cleaned


def clean_description(html: str | None) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(unescape(html), "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    lines = [line.strip() for line in soup.get_text("\n").splitlines()]
    kept_lines = []
    for line in lines:
        if not line:
            continue
        lowered = line.lower()
        if any(pattern in lowered for pattern in BOILERPLATE_PATTERNS):
            continue
        kept_lines.append(re.sub(r"\s+", " ", line))
    return "\n".join(kept_lines)


def normalize_employment_type(
    hint: str | None,
    title: str,
    description: str,
) -> EmploymentType:
    value = " ".join(filter(None, [hint, title, description[:250]])).lower()
    if re.search(r"\bintern(ship)?\b", value):
        return EmploymentType.INTERNSHIP
    if re.search(r"\bcontract(or)?\b", value) or "consultant" in value:
        return EmploymentType.CONTRACT
    if "part-time" in value or "part time" in value:
        return EmploymentType.PART_TIME
    if "temporary" in value or re.search(r"\btemp\b", value):
        return EmploymentType.TEMPORARY
    if "apprentice" in value:
        return EmploymentType.APPRENTICESHIP
    if "full-time" in value or "full time" in value:
        return EmploymentType.FULL_TIME
    return EmploymentType.UNKNOWN


def parse_workplace(location_raw: str | None, description: str) -> tuple[WorkplaceType, bool]:
    combined = " ".join(filter(None, [location_raw, description[:300]])).lower()
    if "hybrid" in combined:
        return WorkplaceType.HYBRID, False
    if "remote" in combined or "work from home" in combined:
        return WorkplaceType.REMOTE, True
    if combined:
        return WorkplaceType.ONSITE, False
    return WorkplaceType.UNKNOWN, False


def parse_location(location_raw: str | None) -> dict[str, Any]:
    if not location_raw:
        return {"location_city": None, "location_region": None, "location_country": None}
    normalized = re.sub(r"\s+", " ", location_raw).strip()
    normalized = re.sub(r"\b(remote|hybrid|onsite|on-site)\b", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s*[/|-]\s*", ", ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ,")
    parts = [part for part in LOCATION_SPLIT_RE.split(normalized) if part]
    city = parts[0] if parts else None
    region = parts[1] if len(parts) > 1 else None
    country = parts[-1] if len(parts) > 2 else None
    if location_raw.lower().startswith("remote") and len(parts) > 0:
        city = None
        region = None
        country = parts[-1]
    return {
        "location_city": city,
        "location_region": region,
        "location_country": country,
    }


def parse_salary(salary_raw: str | None, description: str) -> dict[str, Any]:
    search_space = salary_raw or description
    if not search_space:
        return _empty_salary(salary_raw)

    match = SALARY_RE.search(search_space)
    if not match:
        return _empty_salary(salary_raw)

    min_value = _parse_number(match.group("min"), match.group("min_suffix"))
    max_value = _parse_number(match.group("max"), match.group("max_suffix")) if match.group("max") else None
    period_match = re.search(r"(year|annual|annually|month|monthly|hour|hourly)", search_space, re.IGNORECASE)
    period = period_match.group(1) if period_match else None
    return {
        "salary_raw": salary_raw or match.group(0),
        "salary_min": min_value,
        "salary_max": max_value,
        "salary_currency": {"$": "USD", "€": "EUR", "£": "GBP"}.get(match.group("currency")),
        "salary_period": _normalize_salary_period(period),
    }


def _empty_salary(salary_raw: str | None) -> dict[str, Any]:
    return {
        "salary_raw": salary_raw,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_period": None,
    }


def _parse_number(value: str | None, suffix: str | None) -> float | None:
    if not value:
        return None
    number = float(value.replace(",", ""))
    if suffix:
        if suffix.lower() == "k":
            return number * 1_000
        if suffix.lower() == "m":
            return number * 1_000_000
    return number


def _normalize_salary_period(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower()
    if "year" in lowered or "annual" in lowered:
        return "year"
    if "month" in lowered:
        return "month"
    if "hour" in lowered:
        return "hour"
    return None


def compute_content_hash(company_slug: str, title: str, description: str) -> str:
    payload = f"{company_slug}|{title.lower()}|{description[:500].lower()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_job(job: JobPosting) -> JobPosting:
    description_text = clean_description(job.description_html or job.description_text)
    workplace_type, is_remote = parse_workplace(job.location_raw, description_text)
    location_fields = parse_location(job.location_raw)
    salary_fields = parse_salary(job.salary_raw, description_text)
    title_normalized = normalize_title(job.title_raw)
    employment_hint = job.metadata.get("employment_hint") or job.metadata.get("commitment")

    return job.model_copy(
        update={
            "canonical_url": canonicalize_url(job.canonical_url) or job.canonical_url,
            "apply_url": canonicalize_url(job.apply_url) if job.apply_url else None,
            "title_normalized": title_normalized,
            "description_text": description_text,
            "employment_type": normalize_employment_type(employment_hint, title_normalized, description_text),
            "workplace_type": workplace_type,
            "is_remote": is_remote,
            "content_hash": compute_content_hash(job.company_slug, title_normalized, description_text),
            **location_fields,
            **salary_fields,
        }
    )
