from __future__ import annotations

from typing import Any, Callable, Mapping

import httpx

from .models import TaskStatusResponse

TaskSubmissionOptions = Mapping[str, Any]
ResponseHook = Callable[[httpx.Response], None]
TaskStatusCallback = Callable[[TaskStatusResponse], None]
