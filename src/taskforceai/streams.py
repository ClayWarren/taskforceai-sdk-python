from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, AsyncGenerator, AsyncIterator, Iterator, Optional

from .exceptions import TaskForceAIError
from .models import TaskId, TaskStatusResponse
from .types import TaskStatusCallback

if TYPE_CHECKING:
    from .client import AsyncTaskForceAIClient, TaskForceAIClient


class TaskStatusStream(Iterator[TaskStatusResponse]):
    def __init__(
        self,
        client: "TaskForceAIClient",
        task_id: TaskId,
        *,
        poll_interval: float,
        max_attempts: int,
        on_status: Optional[TaskStatusCallback] = None,
    ) -> None:
        self._client = client
        self._task_id = task_id
        self._poll_interval = poll_interval
        self._max_attempts = max_attempts
        self._on_status = on_status
        self._cancelled = False
        self._iterator = self._generator()
        self.task_id = task_id

    def cancel(self) -> None:
        self._cancelled = True

    def __iter__(self) -> "TaskStatusStream":
        return self

    def __next__(self) -> TaskStatusResponse:
        return next(self._iterator)

    def _generator(self) -> Iterator[TaskStatusResponse]:
        attempts = 0
        while attempts < self._max_attempts:
            if self._cancelled:
                raise TaskForceAIError("Task stream cancelled")

            status = self._client.get_task_status(self._task_id)
            if self._on_status:
                self._on_status(status)

            yield status

            if status.status in {"completed", "failed"}:
                return

            attempts += 1
            time.sleep(self._poll_interval)

        raise TaskForceAIError("Task did not complete within the expected time")


class AsyncTaskStatusStream(AsyncIterator[TaskStatusResponse]):
    def __init__(
        self,
        client: "AsyncTaskForceAIClient",
        task_id: TaskId,
        *,
        poll_interval: float,
        max_attempts: int,
        on_status: Optional[TaskStatusCallback] = None,
    ) -> None:
        self._client = client
        self._task_id = task_id
        self._poll_interval = poll_interval
        self._max_attempts = max_attempts
        self._on_status = on_status
        self._cancelled = False
        self._iterator = self._generator()
        self.task_id = task_id

    def cancel(self) -> None:
        self._cancelled = True

    def __aiter__(self) -> "AsyncTaskStatusStream":
        return self

    async def __anext__(self) -> TaskStatusResponse:
        return await self._iterator.__anext__()

    async def _generator(self) -> AsyncGenerator[TaskStatusResponse, None]:
        attempts = 0
        while attempts < self._max_attempts:
            if self._cancelled:
                raise TaskForceAIError("Task stream cancelled")

            status = await self._client.get_task_status(self._task_id)
            if self._on_status:
                self._on_status(status)

            yield status

            if status.status in {"completed", "failed"}:
                return

            attempts += 1
            await asyncio.sleep(self._poll_interval)

        raise TaskForceAIError("Task did not complete within the expected time")
