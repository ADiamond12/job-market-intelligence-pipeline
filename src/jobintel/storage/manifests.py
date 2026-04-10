from __future__ import annotations

from pathlib import Path

from jobintel.domain.models import RunManifest
from jobintel.storage.artifacts import write_json


def write_manifest(path: Path, manifest: RunManifest) -> None:
    write_json(path, manifest.model_dump(mode="json"))
