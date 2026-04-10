from __future__ import annotations

import re
from collections import OrderedDict

SKILL_TAXONOMY = OrderedDict(
    {
        "Python": (r"\bpython\b",),
        "Pandas": (r"\bpandas\b",),
        "SQL": (r"\bsql\b", r"\bpostgres\b", r"\bsnowflake\b", r"\bbigquery\b"),
        "FastAPI": (r"\bfastapi\b",),
        "Airflow": (r"\bairflow\b",),
        "dbt": (r"\bdbt\b",),
        "Spark": (r"\bspark\b", r"\bpyspark\b"),
        "Docker": (r"\bdocker\b",),
        "Kubernetes": (r"\bkubernetes\b", r"\bk8s\b"),
        "AWS": (r"\baws\b", r"amazon web services"),
        "GCP": (r"\bgcp\b", r"google cloud"),
        "Azure": (r"\bazure\b",),
        "Machine Learning": (r"machine learning", r"scikit-learn"),
        "LLMs": (r"\bllm(s)?\b", r"large language model", r"\bopenai\b", r"prompt engineering"),
        "NLP": (r"\bnlp\b", r"natural language processing"),
        "Tableau": (r"\btableau\b",),
        "Power BI": (r"power bi",),
        "React": (r"\breact\b",),
        "JavaScript": (r"\bjavascript\b", r"\btypescript\b"),
    }
)


def extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    extracted = []
    for skill, patterns in SKILL_TAXONOMY.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            extracted.append(skill)
    return extracted
