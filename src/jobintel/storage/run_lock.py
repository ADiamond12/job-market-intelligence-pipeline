from __future__ import annotations

from pathlib import Path
from typing import Self


class RunLockError(RuntimeError):
    """Raised when a run lock cannot be acquired."""


class RunLock:
    """Simple file-based lock for sequential CLI runs."""

    def __init__(self, lock_path: str | Path):
        self.path = Path(lock_path)
        self._file = None
        self._acquired = False

    def acquire(self) -> Self:
        if self._acquired:
            return self

        self.path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._file = self.path.open("x", encoding="utf-8")
        except FileExistsError as exc:
            raise RunLockError(f"Run lock is already held: {self.path}") from exc

        self._file.write("jobintel run lock\n")
        self._file.flush()
        self._acquired = True
        return self

    def release(self) -> None:
        if not self._acquired:
            return

        file_obj = self._file
        self._file = None
        self._acquired = False

        if file_obj is not None:
            file_obj.close()

        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self) -> Self:
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

