from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx
import pytest

from taskforceai import AsyncTaskForceAIClient, TaskForceAIClient, TaskForceAIError, TaskStatusResponse


def build_transport(responses: List[Dict[str, Any]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if not responses:
            raise AssertionError("Unexpected request: no mock responses left")
        spec = responses.pop(0)
        status = spec.get("status", 200)
        json_data = spec.get("json")
        text_data = spec.get("text")
        headers = spec.get("headers")
        method = spec.get("method")
        if method:
            assert request.method == method
        path = spec.get("path")
        if path:
            assert request.url.path == path

        if json_data is not None:
            return httpx.Response(
                status_code=status,
                json=json_data,
                headers=headers,
                request=request,
            )

        return httpx.Response(
            status_code=status,
            text=text_data or "",
            headers=headers,
            request=request,
        )

    return httpx.MockTransport(handler)


def test_submit_task_success() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "task_123", "status": "processing"},
                "path": "/api/developer/run",
                "method": "POST",
            }
        ]
    )
    client = TaskForceAIClient(
        "test-key", base_url="https://example.com/api/developer", transport=transport
    )

    task_id = client.submit_task("Run analysis")

    assert task_id == "task_123"
    client.close()


def test_submit_task_includes_vercel_ai_key() -> None:
    captured_payload: Dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_payload
        captured_payload = json.loads(request.content.decode())
        return httpx.Response(
            status_code=200,
            json={"taskId": "task_789", "status": "processing"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    client = TaskForceAIClient(
        "key", base_url="https://example.com/api/developer", transport=transport
    )

    task_id = client.submit_task("Check payload", vercel_ai_key="custom-key")

    assert task_id == "task_789"
    assert captured_payload["prompt"] == "Check payload"
    assert captured_payload["vercelAiKey"] == "custom-key"
    assert captured_payload["options"] == {"silent": False, "mock": False}
    client.close()


def test_submit_task_accepts_custom_options() -> None:
    captured_payload: Dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_payload
        captured_payload = json.loads(request.content.decode())
        return httpx.Response(
            status_code=200,
            json={"taskId": "task_extra", "status": "processing"},
            request=request,
        )

    client = TaskForceAIClient(
        "key", base_url="https://example.com/api/developer", transport=httpx.MockTransport(handler)
    )

    task_id = client.submit_task(
        "Check options",
        options={"silent": True, "budget": 8},
        mock=False,
    )

    assert task_id == "task_extra"
    assert captured_payload["options"] == {"silent": True, "mock": False, "budget": 8}
    client.close()


def test_submit_task_error() -> None:
    transport = build_transport(
        [
            {
                "status": 401,
                "json": {"error": "Invalid API key"},
                "path": "/api/developer/run",
                "method": "POST",
            }
        ]
    )
    client = TaskForceAIClient(
        "bad-key", base_url="https://example.com/api/developer", transport=transport
    )

    with pytest.raises(TaskForceAIError) as exc:
        client.submit_task("Do something")

    assert exc.value.status_code == 401
    assert "Invalid API key" in str(exc.value)
    client.close()


def test_submit_task_error_with_non_string_payload() -> None:
    transport = build_transport(
        [
            {
                "status": 400,
                "json": {"error": {"detail": "bad request"}},
                "path": "/api/developer/run",
                "method": "POST",
            }
        ]
    )
    client = TaskForceAIClient(
        "bad-key", base_url="https://example.com/api/developer", transport=transport
    )

    with pytest.raises(TaskForceAIError) as exc:
        client.submit_task("Do something")

    assert "{'detail': 'bad request'}" in str(exc.value)
    client.close()


def test_wait_for_completion_success() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "task_123", "status": "processing"},
                "path": "/api/developer/status/task_123",
            },
            {
                "status": 200,
                "json": {"taskId": "task_123", "status": "completed", "result": "done"},
                "path": "/api/developer/status/task_123",
            },
        ]
    )
    client = TaskForceAIClient(
        "key", base_url="https://example.com/api/developer", transport=transport
    )

    statuses: List[TaskStatusResponse] = []
    result = client.wait_for_completion(
        "task_123",
        poll_interval=0.01,
        max_attempts=5,
        on_status=lambda payload: statuses.append(payload),
    )

    assert statuses[0].status == "processing"
    assert result.task_id == "task_123"
    assert result.result == "done"
    assert result.status == "completed"
    client.close()


def test_run_task_failure() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "task_456", "status": "processing"},
                "path": "/api/developer/run",
                "method": "POST",
            },
            {
                "status": 200,
                "json": {"taskId": "task_456", "status": "failed", "error": "Task failed"},
                "path": "/api/developer/status/task_456",
                "method": "GET",
            },
        ]
    )
    client = TaskForceAIClient(
        "key", base_url="https://example.com/api/developer", transport=transport
    )

    with pytest.raises(TaskForceAIError) as exc:
        client.run_task("Investigate bug", poll_interval=0.01, max_attempts=2)

    assert "Task failed" in str(exc.value)
    client.close()


def test_stream_task_status_emits_updates() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "task_stream", "status": "processing"},
                "path": "/api/developer/status/task_stream",
            },
            {
                "status": 200,
                "json": {"taskId": "task_stream", "status": "completed", "result": "done"},
                "path": "/api/developer/status/task_stream",
            },
        ]
    )
    client = TaskForceAIClient(
        "key", base_url="https://example.com/api/developer", transport=transport
    )

    stream = client.stream_task_status("task_stream", poll_interval=0.0, max_attempts=2)
    statuses = list(stream)

    assert statuses[-1].status == "completed"
    client.close()


def test_stream_task_status_cancel() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "task_cancel", "status": "processing"},
                "path": "/api/developer/status/task_cancel",
            }
        ]
    )
    client = TaskForceAIClient(
        "key", base_url="https://example.com/api/developer", transport=transport
    )

    stream = client.stream_task_status("task_cancel", poll_interval=0.0, max_attempts=2)
    first = next(stream)
    assert first.status == "processing"
    stream.cancel()
    with pytest.raises(TaskForceAIError, match="cancelled"):
        next(stream)
    client.close()


@pytest.mark.asyncio
async def test_async_run_task_success() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "task_async", "status": "processing"},
                "path": "/api/developer/run",
                "method": "POST",
            },
            {
                "status": 200,
                "json": {"taskId": "task_async", "status": "completed", "result": "async result"},
                "path": "/api/developer/status/task_async",
                "method": "GET",
            },
        ]
    )
    async with AsyncTaskForceAIClient(
        "key",
        base_url="https://example.com/api/developer",
        transport=transport,
    ) as client:
        result = await client.run_task("Async task", poll_interval=0.01, max_attempts=2)

    assert result.task_id == "task_async"
    assert result.result == "async result"
    assert result.status == "completed"


def test_client_validates_api_key() -> None:
    with pytest.raises(TaskForceAIError):
        TaskForceAIClient("  ")


def test_client_context_manager_closes_client() -> None:
    captured: TaskForceAIClient | None = None
    with TaskForceAIClient("key") as client:
        captured = client
        assert not client._client.is_closed

    assert captured is not None
    assert captured._client.is_closed


def test_client_request_timeout() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    client = TaskForceAIClient("key", transport=httpx.MockTransport(handler))

    with pytest.raises(TaskForceAIError, match="Request timeout"):
        client.get_task_status("task")

    client.close()


def test_client_http_status_error_with_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service unavailable", request=request)

    client = TaskForceAIClient("key", transport=httpx.MockTransport(handler))

    with pytest.raises(TaskForceAIError) as exc:
        client.get_task_status("task")

    assert exc.value.status_code == 503
    assert "Service unavailable" in str(exc.value)
    client.close()


def test_client_network_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.TransportError("boom")

    client = TaskForceAIClient("key", transport=httpx.MockTransport(handler))

    with pytest.raises(TaskForceAIError, match="Network error: boom"):
        client.get_task_status("task")

    client.close()


def test_response_hook_receives_headers() -> None:
    captured: List[httpx.Headers] = []

    def hook(response: httpx.Response) -> None:
        captured.append(response.headers)

    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "task_meta", "status": "completed", "result": "ok"},
                "path": "/api/developer/status/task_meta",
            }
        ]
    )

    client = TaskForceAIClient(
        "key",
        base_url="https://example.com/api/developer",
        transport=transport,
        response_hook=hook,
    )

    status = client.get_task_status("task_meta")
    assert status.result == "ok"
    assert captured
    client.close()


def test_submit_task_validates_prompt() -> None:
    client = TaskForceAIClient("key")
    with pytest.raises(TaskForceAIError, match="Prompt must be a non-empty string"):
        client.submit_task("   ")
    client.close()


def test_submit_task_missing_task_id() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"message": "ok"},
                "path": "/api/developer/run",
                "method": "POST",
            }
        ]
    )
    client = TaskForceAIClient(
        "key", base_url="https://example.com/api/developer", transport=transport
    )

    with pytest.raises(TaskForceAIError, match="Invalid API response"):
        client.submit_task("Prompt")
    client.close()


def test_get_task_result_validates_input() -> None:
    client = TaskForceAIClient("key")
    with pytest.raises(TaskForceAIError, match="Task ID must be a non-empty string"):
        client.get_task_result("")
    client.close()


def test_get_task_status_validates_input() -> None:
    client = TaskForceAIClient("key")
    with pytest.raises(TaskForceAIError, match="Task ID must be a non-empty string"):
        client.get_task_status(" ")
    client.close()


def test_get_task_result_success() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "task_1", "status": "completed", "result": "done"},
                "path": "/api/developer/results/task_1",
                "method": "GET",
            }
        ]
    )
    client = TaskForceAIClient(
        "key", base_url="https://example.com/api/developer", transport=transport
    )

    result = client.get_task_result("task_1")

    assert result.result == "done"
    assert result.status == "completed"
    client.close()


def test_wait_for_completion_timeout() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "task_1", "status": "processing"},
                "path": "/api/developer/status/task_1",
            },
            {
                "status": 200,
                "json": {"taskId": "task_1", "status": "processing"},
                "path": "/api/developer/status/task_1",
            },
        ]
    )
    client = TaskForceAIClient(
        "key", base_url="https://example.com/api/developer", transport=transport
    )

    with pytest.raises(TaskForceAIError, match="expected time"):
        client.wait_for_completion("task_1", poll_interval=0.0, max_attempts=2)
    client.close()


@pytest.mark.asyncio
async def test_async_client_validates_api_key() -> None:
    with pytest.raises(TaskForceAIError):
        AsyncTaskForceAIClient("")


@pytest.mark.asyncio
async def test_async_client_context_manager_closes_client() -> None:
    captured: AsyncTaskForceAIClient | None = None

    async with AsyncTaskForceAIClient("key") as client:
        captured = client
        assert not client._client.is_closed

    assert captured is not None
    assert captured._client.is_closed


@pytest.mark.asyncio
async def test_async_submit_task_validates_prompt() -> None:
    client = AsyncTaskForceAIClient("key")
    with pytest.raises(TaskForceAIError, match="Prompt must be a non-empty string"):
        await client.submit_task(" ")
    await client.close()


@pytest.mark.asyncio
async def test_async_client_request_timeout() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    client = AsyncTaskForceAIClient("key", transport=httpx.MockTransport(handler))

    with pytest.raises(TaskForceAIError, match="Request timeout"):
        await client.get_task_status("task")

    await client.close()


@pytest.mark.asyncio
async def test_async_get_task_status_validates_input() -> None:
    client = AsyncTaskForceAIClient("key")
    with pytest.raises(TaskForceAIError, match="Task ID must be a non-empty string"):
        await client.get_task_status(" ")
    await client.close()


@pytest.mark.asyncio
async def test_async_get_task_result_validates_input() -> None:
    client = AsyncTaskForceAIClient("key")
    with pytest.raises(TaskForceAIError, match="Task ID must be a non-empty string"):
        await client.get_task_result("")
    await client.close()


@pytest.mark.asyncio
async def test_async_submit_task_includes_vercel_ai_key() -> None:
    captured_payload: Dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_payload
        captured_payload = json.loads(request.content.decode())
        return httpx.Response(
            status_code=200,
            json={"taskId": "task_async_router", "status": "processing"},
            request=request,
        )

    client = AsyncTaskForceAIClient(
        "key",
        base_url="https://example.com/api/developer",
        transport=httpx.MockTransport(handler),
    )

    task_id = await client.submit_task("Check async payload", vercel_ai_key="async-key")

    assert task_id == "task_async_router"
    assert captured_payload["vercelAiKey"] == "async-key"
    await client.close()


@pytest.mark.asyncio
async def test_async_submit_task_error_with_object_payload() -> None:
    transport = build_transport(
        [
            {
                "status": 422,
                "json": {"error": ["Invalid"]},
                "path": "/api/developer/run",
                "method": "POST",
            }
        ]
    )
    client = AsyncTaskForceAIClient(
        "key",
        base_url="https://example.com/api/developer",
        transport=transport,
    )

    with pytest.raises(TaskForceAIError) as exc:
        await client.submit_task("prompt")

    assert "['Invalid']" in str(exc.value)
    await client.close()


@pytest.mark.asyncio
async def test_async_submit_task_missing_task_id() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"message": "ok"},
                "path": "/api/developer/run",
                "method": "POST",
            }
        ]
    )
    client = AsyncTaskForceAIClient(
        "key",
        base_url="https://example.com/api/developer",
        transport=transport,
    )

    with pytest.raises(TaskForceAIError, match="Invalid API response"):
        await client.submit_task("prompt")

    await client.close()


@pytest.mark.asyncio
async def test_async_client_network_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.TransportError("boom")

    client = AsyncTaskForceAIClient("key", transport=httpx.MockTransport(handler))

    with pytest.raises(TaskForceAIError, match="Network error: boom"):
        await client.get_task_status("task")

    await client.close()


@pytest.mark.asyncio
async def test_async_get_task_result_success() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "task_async", "status": "completed", "result": "value"},
                "path": "/api/developer/results/task_async",
                "method": "GET",
            }
        ]
    )
    client = AsyncTaskForceAIClient(
        "key",
        base_url="https://example.com/api/developer",
        transport=transport,
    )

    result = await client.get_task_result("task_async")

    assert result.result == "value"
    await client.close()


@pytest.mark.asyncio
async def test_async_wait_for_completion_failure() -> None:
    responses: List[Dict[str, Any]] = [
        {
            "status": 200,
            "json": {"taskId": "id", "status": "failed", "error": "Unable"},
            "path": "/api/developer/status/id",
            "method": "GET",
        },
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        if not responses:
            raise AssertionError("Unexpected request")
        spec = responses.pop(0)
        assert request.url.path == spec["path"]
        assert request.method == spec["method"]
        return httpx.Response(status_code=spec["status"], json=spec["json"], request=request)

    client = AsyncTaskForceAIClient(
        "key",
        base_url="https://example.com/api/developer",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(TaskForceAIError, match="Unable"):
        await client.wait_for_completion("id", poll_interval=0.0, max_attempts=1)

    await client.close()


@pytest.mark.asyncio
async def test_async_wait_for_completion_timeout() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "task_timeout", "status": "processing"},
                "path": "/api/developer/status/task_timeout",
            },
            {
                "status": 200,
                "json": {"taskId": "task_timeout", "status": "processing"},
                "path": "/api/developer/status/task_timeout",
            },
        ]
    )
    client = AsyncTaskForceAIClient(
        "key",
        base_url="https://example.com/api/developer",
        transport=transport,
    )

    with pytest.raises(TaskForceAIError, match="expected time"):
        await client.wait_for_completion("task_timeout", poll_interval=0.0, max_attempts=2)

    await client.close()


@pytest.mark.asyncio
async def test_async_stream_task_status() -> None:
    transport = build_transport(
        [
            {
                "status": 200,
                "json": {"taskId": "async_stream", "status": "processing"},
                "path": "/api/developer/status/async_stream",
            },
            {
                "status": 200,
                "json": {"taskId": "async_stream", "status": "completed", "result": "ok"},
                "path": "/api/developer/status/async_stream",
            },
        ]
    )
    client = AsyncTaskForceAIClient(
        "key",
        base_url="https://example.com/api/developer",
        transport=transport,
    )

    stream = client.stream_task_status("async_stream", poll_interval=0.0, max_attempts=2)
    statuses: List[TaskStatusResponse] = []
    async for status in stream:
        statuses.append(status)

    assert statuses[-1].status == "completed"
    await client.close()


def test_taskforceai_error_repr() -> None:
    err = TaskForceAIError("oops", status_code=400)
    assert repr(err) == "TaskForceAIError('oops', status_code=400)"