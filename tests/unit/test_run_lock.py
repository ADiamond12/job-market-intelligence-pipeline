from __future__ import annotations

import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from jobintel.storage.run_lock import RunLock, RunLockError


def test_run_lock_acquire_and_release(tmp_path: Path) -> None:
    lock_path = tmp_path / "run.lock"

    with RunLock(lock_path):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_run_lock_raises_when_already_held(tmp_path: Path) -> None:
    lock_path = tmp_path / "run.lock"

    with RunLock(lock_path):
        with pytest.raises(RunLockError, match="already held"):
            RunLock(lock_path).acquire()

