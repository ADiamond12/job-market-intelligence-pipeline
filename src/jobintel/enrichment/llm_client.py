from __future__ import annotations

import json
import os
from typing import Any

import requests
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from jobintel.config import AIConfig
from jobintel.domain.models import AIClassification, AIReportInsight, JobPosting
from jobintel.enrichment.prompts import (
    CLASSIFICATION_SCHEMA,
    REPORT_SCHEMA,
    build_classification_prompt,
    build_report_prompt,
)


class OpenAIResponsesClient:
    def __init__(self, settings: AIConfig) -> None:
        self.settings = settings
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.session = requests.Session()

    @property
    def available(self) -> bool:
        return self.settings.enabled and bool(self.api_key)

    def classify_job(self, job: JobPosting) -> AIClassification | None:
        if not self.available:
            return None
        response_text = self._create_structured_response(
            prompt=build_classification_prompt(job, self.settings.max_description_chars),
            schema_name="job_classification",
            schema=CLASSIFICATION_SCHEMA,
        )
        if not response_text:
            return None
        return AIClassification.model_validate(json.loads(response_text))

    def summarize_market(self, report_context: dict[str, Any]) -> AIReportInsight | None:
        if not self.available:
            return None
        response_text = self._create_structured_response(
            prompt=build_report_prompt(report_context),
            schema_name="market_report_summary",
            schema=REPORT_SCHEMA,
        )
        if not response_text:
            return None
        payload = json.loads(response_text)
        payload["model"] = self.settings.model
        return AIReportInsight.model_validate(payload)

    def _create_structured_response(self, prompt: str, schema_name: str, schema: dict[str, Any]) -> str | None:
        payload = {
            "model": self.settings.model,
            "input": prompt,
            "temperature": self.settings.temperature,
            "text": {
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        response_json = self._post(payload)
        return response_json.get("output_text") or _extract_output_text(response_json)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        retryer = Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((requests.RequestException, ValueError)),
            reraise=True,
        )
        for attempt in retryer:
            with attempt:
                response = self.session.post(
                    self.settings.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.settings.timeout_seconds,
                )
                response.raise_for_status()
                return response.json()
        raise RuntimeError("Unreachable retry loop.")


def _extract_output_text(response_json: dict[str, Any]) -> str | None:
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text")
    return None
