from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from pydantic import TypeAdapter, ValidationError

from .exceptions import TaskForceAIError
from .models import TaskStatusResponse
from .types import TaskSubmissionOptions


def merge_options(
    base_options: Optional[TaskSubmissionOptions],
    *,
    silent: Optional[bool],
    mock: Optional[bool],
) -> Dict[str, Any]:
    options: Dict[str, Any] = {"silent": False, "mock": False}
    if base_options:
        options.update(dict(base_options))
    if silent is not None:
        options["silent"] = silent
    if mock is not None:
        options["mock"] = mock
    return options


def extract_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"

    if isinstance(data, dict):
        error_value = data.get("error")
        if isinstance(error_value, str):
            return error_value
        if error_value is not None:
            return str(error_value)

    return response.text or f"HTTP {response.status_code}"


def validate_task_status(data: Any) -> TaskStatusResponse:
    try:
        return TypeAdapter(TaskStatusResponse).validate_python(data)
    except ValidationError as exc:
        raise TaskForceAIError(f"Invalid API response: {exc}") from exc
