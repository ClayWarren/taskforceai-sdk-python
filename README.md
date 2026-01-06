# TaskForceAI Python SDK

The official Python client for TaskForceAI's multi-agent orchestration platform.

- ✅ Sync + async clients powered by `httpx`
- ✅ Automatic authentication with your TaskForceAI API key
- ✅ Convenience helpers for polling task completion
- ✅ Rich error handling with status codes and retry-ready exceptions
- ✅ Mock mode for development without an API key

## Installation

```bash
python -m pip install taskforceai
```

## Quick Start

```python
from taskforceai import TaskForceAIClient

client = TaskForceAIClient(api_key="your-api-key")

task_id = client.submit_task("Analyze the security posture of this repository.")
status = client.wait_for_completion(task_id)

print(status["result"])
```

```python
# Bring your own Vercel AI Gateway key (unlocks premium models)
task_id = client.submit_task(
    "Draft a quarterly strategy update.",
    vercel_ai_key="sk-vercel-your-gateway-key",
)

# Forward arbitrary TaskForceAI orchestration options
task_id = client.submit_task(
    "Do a full repository risk review",
    options={"agents": 4, "budget": 12},
)
```

### Mock Mode

Build and test your integration without an API key using mock mode:

```python
from taskforceai import TaskForceAIClient

# No API key required in mock mode
client = TaskForceAIClient(mock_mode=True)

result = client.run_task("Test your integration")
print(result.result)  # "This is a mock response. Configure your API key to get real results."
```

Mock mode simulates the full task lifecycle locally—no network requests are made. Tasks go through "processing" then "completed" states, making it easy to build UIs and test error handling before launch.

### Async Variant

````python
import asyncio
from taskforceai import AsyncTaskForceAIClient

async def main() -> None:
    async with AsyncTaskForceAIClient(api_key="your-api-key") as client:
        result = await client.run_task("Summarize the latest launch notes.")
        print(result["result"])

asyncio.run(main())

### Streaming Task Updates

```python
from taskforceai import TaskForceAIClient

client = TaskForceAIClient(api_key="your-api-key")
stream = client.run_task_stream("Map open security issues", poll_interval=0.5)

for status in stream:
    print(f"{status['status']}: {status.get('result')}")

# Cancel locally if needed
# stream.cancel()
````

Async projects can use `AsyncTaskForceAIClient.stream_task_status()` and iterate with
`async for status in stream` for non-blocking workflows.

````

## API Surface

Both clients expose the same methods:

- `submit_task(prompt, *, options=None, silent=None, mock=None, vercel_ai_key=None) -> str`
- `get_task_status(task_id) -> dict`
- `get_task_result(task_id) -> dict`
- `wait_for_completion(task_id, poll_interval=2.0, max_attempts=150, on_status=None) -> dict`
- `run_task(prompt, ..., on_status=None) -> dict`
- `stream_task_status(task_id, ..., on_status=None) -> Iterator`
- `run_task_stream(prompt, ..., on_status=None) -> Iterator`

### Response Hooks & Rate-Limit Telemetry

Both clients accept `response_hook=` in their constructors. The hook is invoked with the
raw `httpx.Response` (headers included) for every request, making it easy to track
rate-limit headers, request IDs, or emit custom metrics without wrapping the SDK.

All responses mirror the REST API payloads. Errors raise `TaskForceAIError`, which includes `status_code` for quick branching.

## Development

```bash
python -m pip install -e "packages/python-sdk[dev]"
pytest packages/python-sdk/tests
ruff format packages/python-sdk/src packages/python-sdk/tests -q
ruff check packages/python-sdk/src packages/python-sdk/tests
mypy --config-file packages/python-sdk/pyproject.toml packages/python-sdk/src
````

## License

MIT
