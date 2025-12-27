from __future__ import annotations

from typing import Optional


class TaskForceAIError(Exception):
    """Base exception for TaskForceAI SDK errors."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code

    def __repr__(self) -> str:
        details = f", status_code={self.status_code}" if self.status_code is not None else ""
        return f"{self.__class__.__name__}({self.args[0]!r}{details})"
