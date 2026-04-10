from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

import pandas as pd

from jobintel.domain.models import JobPosting


def jobs_to_frame(jobs: list[JobPosting]) -> pd.DataFrame:
    return pd.DataFrame([job.to_record() for job in jobs])


def compute_market_metrics(jobs: list[JobPosting]) -> dict[str, Any]:
    frame = jobs_to_frame(jobs)
    if frame.empty:
        return {
            "total_jobs": 0,
            "companies_tracked": 0,
            "top_skills": [],
            "role_family_distribution": {},
            "seniority_distribution": {},
            "workplace_distribution": {},
            "top_companies": {},
            "top_titles": {},
            "sample_titles": [],
            "salary_coverage": {},
        }

    skills_counter = Counter()
    for skills in frame["extracted_skills"].tolist():
        for skill in skills or []:
            skills_counter[skill] += 1

    salary_frame = frame[frame["salary_min"].notna()]
    salary_coverage = {
        "jobs_with_salary": int(salary_frame.shape[0]),
        "median_salary_min": float(median(salary_frame["salary_min"])) if not salary_frame.empty else None,
        "median_salary_max": float(median(salary_frame["salary_max"].dropna())) if salary_frame["salary_max"].notna().any() else None,
    }

    return {
        "total_jobs": int(frame.shape[0]),
        "companies_tracked": int(frame["company_name"].nunique()),
        "top_skills": [{"skill": skill, "count": count} for skill, count in skills_counter.most_common(10)],
        "role_family_distribution": frame["job_family"].fillna("unknown").value_counts().to_dict(),
        "seniority_distribution": frame["seniority"].fillna("unknown").value_counts().to_dict(),
        "workplace_distribution": frame["workplace_type"].fillna("unknown").value_counts().to_dict(),
        "top_companies": frame["company_name"].value_counts().head(10).to_dict(),
        "top_titles": frame["title_normalized"].fillna(frame["title_raw"]).value_counts().head(10).to_dict(),
        "sample_titles": frame["title_normalized"].fillna(frame["title_raw"]).head(5).tolist(),
        "salary_coverage": salary_coverage,
    }
