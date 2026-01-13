"""Thread types and models for TaskForceAI SDK."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Thread(BaseModel):
    """Represents a conversation thread."""

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ThreadMessage(BaseModel):
    """Represents a message within a thread."""

    id: int
    thread_id: int
    role: str  # "user" or "assistant"
    content: str
    created_at: datetime


class CreateThreadOptions(BaseModel):
    """Options for creating a thread."""

    title: Optional[str] = None
    messages: Optional[List[ThreadMessage]] = None
    metadata: Optional[Dict[str, Any]] = None


class ThreadListResponse(BaseModel):
    """Response containing a list of threads."""

    threads: List[Thread]
    total: int


class ThreadMessagesResponse(BaseModel):
    """Response containing messages from a thread."""

    messages: List[ThreadMessage]
    total: int


class ThreadRunOptions(BaseModel):
    """Options for running a prompt in a thread."""

    prompt: str
    model_id: Optional[str] = Field(None, alias="model_id")
    options: Optional[Dict[str, Any]] = None


class ThreadRunResponse(BaseModel):
    """Response from running in a thread."""

    task_id: str
    thread_id: int
    message_id: int
