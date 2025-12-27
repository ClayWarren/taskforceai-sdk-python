from __future__ import annotations

import time
from types import TracebackType
from typing import Any, Dict, Optional

import httpx

from .exceptions import TaskForceAIError
from .models import TaskId, TaskSubmissionRequest
from .streams import TaskStatusStream
from .types import ResponseHook, TaskStatusCallback, TaskSubmissionOptions
from .utils import extract_error_message, merge_options, validate_task_status

DEFAULT_BASE_URL = "https://taskforceai.chat/api/developer"


def _headers(api_key: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-api-key": api_key,
    }


class TaskForceAIClient:
    """Synchronous TaskForceAI client."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
        response_hook: Optional[ResponseHook] = None,
    ) -> None:
        if not api_key.strip():
            raise TaskForceAIError("API key must be a non-empty string")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._response_hook = response_hook

    def __enter__(self) -> "TaskForceAIClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self._base_url}{endpoint}"
        try:
            response = self._client.request(
                method=method,
                url=url,
                json=json,
                headers=_headers(self._api_key),
                timeout=self._timeout,
            )
            if self._response_hook:
                self._response_hook(response)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise TaskForceAIError("Request timeout") from exc
        except httpx.HTTPStatusError as exc:
            message = extract_error_message(exc.response)
            raise TaskForceAIError(message, status_code=exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise TaskForceAIError(f"Network error: {exc}") from exc

    def submit_task(
        self,
        prompt: str,
        *,
        options: Optional[TaskSubmissionOptions] = None,
        silent: Optional[bool] = None,
        mock: Optional[bool] = None,
        vercel_ai_key: Optional[str] = None,
    ) -> TaskId:
        if not prompt.strip():
            raise TaskForceAIError("Prompt must be a non-empty string")

        request_model = TaskSubmissionRequest(
            prompt=prompt,
            options=merge_options(options, silent=silent, mock=mock),
            vercel_ai_key=vercel_ai_key,
        )

        payload = request_model.model_dump(by_alias=True, exclude_none=True)
        data = self._request("POST", "/run", json=payload)
        return validate_task_status(data).task_id

    def get_task_status(self, task_id: TaskId) -> Any:
        if not str(task_id).strip():
            raise TaskForceAIError("Task ID must be a non-empty string")
        data = self._request("GET", f"/status/{task_id}")
        return validate_task_status(data)

    def get_task_result(self, task_id: TaskId) -> Any:
        if not str(task_id).strip():
            raise TaskForceAIError("Task ID must be a non-empty string")
        data = self._request("GET", f"/results/{task_id}")
        return validate_task_status(data)

    def wait_for_completion(
        self,
        task_id: TaskId,
        *,
        poll_interval: float = 2.0,
        max_attempts: int = 150,
        on_status: Optional[TaskStatusCallback] = None,
    ) -> Any:
        for _ in range(max_attempts):
            status = self.get_task_status(task_id)
            if on_status:
                on_status(status)
            if status.status == "completed":
                return status
            if status.status == "failed":
                raise TaskForceAIError(getattr(status, "error", "Task failed"))
            time.sleep(poll_interval)

        raise TaskForceAIError("Task did not complete within the expected time")

    def run_task(
        self,
        prompt: str,
        *,
        options: Optional[TaskSubmissionOptions] = None,
        silent: Optional[bool] = None,
        mock: Optional[bool] = None,
        vercel_ai_key: Optional[str] = None,
        poll_interval: float = 2.0,
        max_attempts: int = 150,
        on_status: Optional[TaskStatusCallback] = None,
    ) -> Any:
        task_id = self.submit_task(
            prompt,
            options=options,
            silent=silent,
            mock=mock,
            vercel_ai_key=vercel_ai_key,
        )
        return self.wait_for_completion(
            task_id,
            poll_interval=poll_interval,
            max_attempts=max_attempts,
            on_status=on_status,
        )

    def stream_task_status(
        self,
        task_id: TaskId,
        *,
        poll_interval: float = 2.0,
        max_attempts: int = 150,
        on_status: Optional[TaskStatusCallback] = None,
    ) -> TaskStatusStream:
        if not str(task_id).strip():
            raise TaskForceAIError("Task ID must be a non-empty string")
        return TaskStatusStream(
            self,
            task_id,
            poll_interval=poll_interval,
            max_attempts=max_attempts,
            on_status=on_status,
        )

    def run_task_stream(
        self,
        prompt: str,
        *,
        options: Optional[TaskSubmissionOptions] = None,
        silent: Optional[bool] = None,
        mock: Optional[bool] = None,
        vercel_ai_key: Optional[str] = None,
        poll_interval: float = 2.0,
        max_attempts: int = 150,
        on_status: Optional[TaskStatusCallback] = None,
    ) -> TaskStatusStream:
        task_id = self.submit_task(
            prompt,
            options=options,
            silent=silent,
            mock=mock,
            vercel_ai_key=vercel_ai_key,
        )
        return TaskStatusStream(
            self,
            task_id,
            poll_interval=poll_interval,
            max_attempts=max_attempts,
            on_status=on_status,
        )
