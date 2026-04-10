from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from jobintel.config import AppConfig, CompanyConfig
from jobintel.domain.models import JobPosting


@dataclass(slots=True)
class FetchBundle:
    company_name: str
    source_url: str
    payload: dict[str, Any] | list[dict[str, Any]]
    jobs: list[JobPosting]
    used_fixture: bool


class BaseSourceAdapter(ABC):
    vendor: str

    def __init__(self, company: CompanyConfig, config: AppConfig, logger: logging.Logger) -> None:
        self.company = company
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

    @abstractmethod
    def get_endpoint(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def parse_payload(
        self,
        payload: dict[str, Any] | list[dict[str, Any]],
        fetched_at: datetime,
    ) -> list[JobPosting]:
        raise NotImplementedError

    def fetch_payload(self) -> tuple[dict[str, Any] | list[dict[str, Any]], bool]:
        if self.company.fixture_path:
            self.logger.info("Loading fixture for %s from %s", self.company.name, self.company.fixture_path)
            with Path(self.company.fixture_path).open("r", encoding="utf-8") as handle:
                return json.load(handle), True

        url = self.get_endpoint()
        retryer = Retrying(
            stop=stop_after_attempt(self.config.retry.attempts),
            wait=wait_exponential(multiplier=self.config.retry.backoff_seconds, min=1, max=10),
            retry=retry_if_exception_type((requests.RequestException, ValueError)),
            reraise=True,
        )
        for attempt in retryer:
            with attempt:
                response = self.session.get(url, timeout=self.config.retry.timeout_seconds)
                response.raise_for_status()
                return response.json(), False

        raise RuntimeError("Unreachable retry loop.")

    def collect(self, fetched_at: datetime) -> FetchBundle:
        payload, used_fixture = self.fetch_payload()
        jobs = self.parse_payload(payload, fetched_at=fetched_at)
        return FetchBundle(
            company_name=self.company.name,
            source_url=self.get_endpoint(),
            payload=payload,
            jobs=jobs,
            used_fixture=used_fixture,
        )

    @staticmethod
    def html_to_text(value: str | None) -> str:
        if not value:
            return ""
        soup = BeautifulSoup(value, "html.parser")
        for element in soup(["script", "style"]):
            element.decompose()
        return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
