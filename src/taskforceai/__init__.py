"""TaskForceAI Python SDK."""

from importlib.metadata import version

from .client import AsyncTaskForceAIClient, TaskForceAIClient
from .exceptions import TaskForceAIError
from .models import (
    TaskCompleted,
    TaskFailed,
    TaskId,
    TaskProcessing,
    TaskStatusResponse,
    TaskSubmissionRequest,
)
from .streams import (
    AsyncTaskStatusStream,
    TaskStatusStream,
)
from .threads import (
    Thread,
    ThreadMessage,
    CreateThreadOptions,
    ThreadListResponse,
    ThreadMessagesResponse,
    ThreadRunOptions,
    ThreadRunResponse,
)
from .files import (
    File,
    FileUploadOptions,
    FileListResponse,
)

__version__ = version("taskforceai")

__all__ = [
    "TaskForceAIClient",
    "AsyncTaskForceAIClient",
    "TaskForceAIError",
    "TaskId",
    "TaskStatusResponse",
    "TaskProcessing",
    "TaskCompleted",
    "TaskFailed",
    "TaskSubmissionRequest",
    "TaskStatusStream",
    "AsyncTaskStatusStream",
    # Thread types
    "Thread",
    "ThreadMessage",
    "CreateThreadOptions",
    "ThreadListResponse",
    "ThreadMessagesResponse",
    "ThreadRunOptions",
    "ThreadRunResponse",
    # File types
    "File",
    "FileUploadOptions",
    "FileListResponse",
    "__version__",
]
