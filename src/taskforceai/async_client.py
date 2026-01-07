from __future__ import annotations

import asyncio
import uuid
from types import TracebackType
from typing import Any, Dict, Optional

import httpx

from .exceptions import TaskForceAIError
from .models import TaskId, TaskSubmissionRequest
from .streams import AsyncTaskStatusStream
from .sync_client import DEFAULT_BASE_URL, MOCK_RESULT, _headers
from .types import ResponseHook, TaskStatusCallback, TaskSubmissionOptions
from .utils import extract_error_message, merge_options, validate_task_status


class AsyncTaskForceAIClient:
    """Asynchronous TaskForceAI client."""

    def __init__(
        self,
        api_key: str = "",
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        response_hook: Optional[ResponseHook] = None,
        mock_mode: bool = False,
    ) -> None:
        self._mock_mode = mock_mode
        self._mock_call_count: Dict[str, int] = {}

        if not mock_mode and not api_key.strip():
            raise TaskForceAIError("API key must be a non-empty string")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = (
            httpx.AsyncClient(timeout=timeout, transport=transport) if not mock_mode else None
        )
        self._response_hook = response_hook

    async def __aenter__(self) -> "AsyncTaskForceAIClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    def _mock_response(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Generate mock responses for development without an API key."""
        if method == "POST" and endpoint == "/run":
            task_id = f"mock-{uuid.uuid4().hex[:8]}"
            self._mock_call_count[task_id] = 0
            return {"taskId": task_id, "status": "processing"}

        if endpoint.startswith("/status/"):
            task_id = endpoint.split("/")[-1]
            count = self._mock_call_count.get(task_id, 0)
            self._mock_call_count[task_id] = count + 1
            if count < 1:
                return {
                    "taskId": task_id,
                    "status": "processing",
                    "message": "Mock task processing...",
                }
            return {"taskId": task_id, "status": "completed", "result": MOCK_RESULT}

        if endpoint.startswith("/results/"):
            task_id = endpoint.split("/")[-1]
            return {"taskId": task_id, "status": "completed", "result": MOCK_RESULT}

        return {"status": "ok"}

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if self._mock_mode:
            return self._mock_response(method, endpoint, json)

        url = f"{self._base_url}{endpoint}"
        try:
            response = await self._client.request(
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

    async def submit_task(
        self,
        prompt: str,
        *,
        options: Optional[TaskSubmissionOptions] = None,
        silent: Optional[bool] = None,
        mock: Optional[bool] = None,
        model_id: Optional[str] = None,
        vercel_ai_key: Optional[str] = None,
    ) -> TaskId:
        if not prompt.strip():
            raise TaskForceAIError("Prompt must be a non-empty string")

        request_model = TaskSubmissionRequest(
            prompt=prompt,
            options=merge_options(options, silent=silent, mock=mock),
            model_id=model_id,
            vercel_ai_key=vercel_ai_key,
        )
        payload = request_model.model_dump(by_alias=True, exclude_none=True)

        data = await self._request("POST", "/run", json=payload)
        return validate_task_status(data).task_id

    async def get_task_status(self, task_id: TaskId) -> Any:
        if not str(task_id).strip():
            raise TaskForceAIError("Task ID must be a non-empty string")
        data = await self._request("GET", f"/status/{task_id}")
        return validate_task_status(data)

    async def get_task_result(self, task_id: TaskId) -> Any:
        if not str(task_id).strip():
            raise TaskForceAIError("Task ID must be a non-empty string")
        data = await self._request("GET", f"/results/{task_id}")
        return validate_task_status(data)

    async def wait_for_completion(
        self,
        task_id: TaskId,
        *,
        poll_interval: float = 2.0,
        max_attempts: int = 150,
        on_status: Optional[TaskStatusCallback] = None,
    ) -> Any:
        for _ in range(max_attempts):
            status = await self.get_task_status(task_id)
            if on_status:
                on_status(status)
            if status.status == "completed":
                return status
            if status.status == "failed":
                raise TaskForceAIError(getattr(status, "error", "Task failed"))
            await asyncio.sleep(poll_interval)

        raise TaskForceAIError("Task did not complete within the expected time")

    async def run_task(
        self,
        prompt: str,
        *,
        options: Optional[TaskSubmissionOptions] = None,
        silent: Optional[bool] = None,
        mock: Optional[bool] = None,
        model_id: Optional[str] = None,
        vercel_ai_key: Optional[str] = None,
        poll_interval: float = 2.0,
        max_attempts: int = 150,
        on_status: Optional[TaskStatusCallback] = None,
    ) -> Any:
        task_id = await self.submit_task(
            prompt,
            options=options,
            silent=silent,
            mock=mock,
            model_id=model_id,
            vercel_ai_key=vercel_ai_key,
        )
        return await self.wait_for_completion(
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
    ) -> AsyncTaskStatusStream:
        if not str(task_id).strip():
            raise TaskForceAIError("Task ID must be a non-empty string")
        return AsyncTaskStatusStream(
            self,
            task_id,
            poll_interval=poll_interval,
            max_attempts=max_attempts,
            on_status=on_status,
        )

    async def run_task_stream(
        self,
        prompt: str,
        *,
        options: Optional[TaskSubmissionOptions] = None,
        silent: Optional[bool] = None,
        mock: Optional[bool] = None,
        model_id: Optional[str] = None,
        vercel_ai_key: Optional[str] = None,
        poll_interval: float = 2.0,
        max_attempts: int = 150,
        on_status: Optional[TaskStatusCallback] = None,
    ) -> AsyncTaskStatusStream:
        task_id = await self.submit_task(
            prompt,
            options=options,
            silent=silent,
            mock=mock,
            model_id=model_id,
            vercel_ai_key=vercel_ai_key,
        )
        return AsyncTaskStatusStream(
            self,
            task_id,
            poll_interval=poll_interval,
            max_attempts=max_attempts,
            on_status=on_status,
        )
