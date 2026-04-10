from __future__ import annotations

from collections import Counter
from typing import Any

from jobintel.domain.models import JobPosting


def build_delta_report(
    current_jobs: list[JobPosting],
    baseline_jobs: list[JobPosting] | None,
    baseline_run_id: str | None,
) -> dict[str, Any]:
    if not baseline_jobs or not baseline_run_id:
        return {
            "baseline_run_id": None,
            "has_baseline": False,
            "summary": {
                "new_jobs": 0,
                "removed_jobs": 0,
                "changed_jobs": 0,
                "unchanged_jobs": 0,
                "net_change": 0,
            },
            "samples": {"new_jobs": [], "removed_jobs": [], "changed_jobs": []},
            "skill_movers": [],
            "company_movers": [],
        }

    current_map = {_job_key(job): job for job in current_jobs}
    baseline_map = {_job_key(job): job for job in baseline_jobs}

    current_keys = set(current_map)
    baseline_keys = set(baseline_map)

    new_keys = sorted(current_keys - baseline_keys)
    removed_keys = sorted(baseline_keys - current_keys)
    shared_keys = sorted(current_keys & baseline_keys)

    changed_keys = [
        key
        for key in shared_keys
        if _job_changed(current_map[key], baseline_map[key])
    ]
    unchanged_keys = [key for key in shared_keys if key not in changed_keys]

    return {
        "baseline_run_id": baseline_run_id,
        "has_baseline": True,
        "summary": {
            "new_jobs": len(new_keys),
            "removed_jobs": len(removed_keys),
            "changed_jobs": len(changed_keys),
            "unchanged_jobs": len(unchanged_keys),
            "net_change": len(current_jobs) - len(baseline_jobs),
        },
        "samples": {
            "new_jobs": [_job_summary(current_map[key]) for key in new_keys[:5]],
            "removed_jobs": [_job_summary(baseline_map[key]) for key in removed_keys[:5]],
            "changed_jobs": [
                {
                    "job_id": current_map[key].job_id,
                    "company_name": current_map[key].company_name,
                    "title": current_map[key].title_normalized or current_map[key].title_raw,
                }
                for key in changed_keys[:5]
            ],
        },
        "skill_movers": _skill_movers(current_jobs, baseline_jobs),
        "company_movers": _company_movers(current_jobs, baseline_jobs),
    }


def _job_key(job: JobPosting) -> tuple[str, str]:
    return (job.company_slug, job.source_job_id)


def _job_changed(current: JobPosting, baseline: JobPosting) -> bool:
    return any(
        [
            current.content_hash != baseline.content_hash,
            current.title_normalized != baseline.title_normalized,
            current.workplace_type != baseline.workplace_type,
            current.salary_min != baseline.salary_min,
            current.salary_max != baseline.salary_max,
        ]
    )


def _job_summary(job: JobPosting) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "company_name": job.company_name,
        "title": job.title_normalized or job.title_raw,
        "job_family": job.job_family,
    }


def _skill_movers(current_jobs: list[JobPosting], baseline_jobs: list[JobPosting]) -> list[dict[str, Any]]:
    current_counter = Counter(skill for job in current_jobs for skill in job.extracted_skills)
    baseline_counter = Counter(skill for job in baseline_jobs for skill in job.extracted_skills)
    skills = sorted(set(current_counter) | set(baseline_counter))
    movers = [
        {
            "skill": skill,
            "current": current_counter.get(skill, 0),
            "baseline": baseline_counter.get(skill, 0),
            "delta": current_counter.get(skill, 0) - baseline_counter.get(skill, 0),
        }
        for skill in skills
        if current_counter.get(skill, 0) != baseline_counter.get(skill, 0)
    ]
    return sorted(movers, key=lambda item: (-abs(item["delta"]), item["skill"]))[:10]


def _company_movers(current_jobs: list[JobPosting], baseline_jobs: list[JobPosting]) -> list[dict[str, Any]]:
    current_counter = Counter(job.company_name for job in current_jobs)
    baseline_counter = Counter(job.company_name for job in baseline_jobs)
    companies = sorted(set(current_counter) | set(baseline_counter))
    movers = [
        {
            "company_name": company,
            "current": current_counter.get(company, 0),
            "baseline": baseline_counter.get(company, 0),
            "delta": current_counter.get(company, 0) - baseline_counter.get(company, 0),
        }
        for company in companies
        if current_counter.get(company, 0) != baseline_counter.get(company, 0)
    ]
    return sorted(movers, key=lambda item: (-abs(item["delta"]), item["company_name"]))[:10]
