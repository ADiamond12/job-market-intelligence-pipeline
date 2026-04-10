from __future__ import annotations

from jobintel.enrichment.classification import infer_role_family, infer_seniority
from jobintel.validation.normalize import parse_location


def test_infer_role_family_prefers_machine_learning() -> None:
    family = infer_role_family(
        "Machine Learning Engineer",
        "Build NLP systems, LLM evaluations, and Python services.",
    )

    assert family == "machine_learning"


def test_infer_role_family_prefers_title_signal_for_data_engineer() -> None:
    family = infer_role_family(
        "Senior Data Engineer, Platform",
        "Build analytics datasets and stakeholder reporting flows.",
    )

    assert family == "data_engineering"


def test_infer_seniority_does_not_treat_internal_as_intern() -> None:
    seniority = infer_seniority(
        "Platform Specialist",
        "Own internal automation and internal developer workflows.",
    )

    assert seniority is None


def test_parse_location_strips_hybrid_suffix() -> None:
    location = parse_location("London, England, United Kingdom / Hybrid")

    assert location["location_city"] == "London"
    assert location["location_region"] == "England"
    assert location["location_country"] == "United Kingdom"
