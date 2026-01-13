"""File types and models for TaskForceAI SDK."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class File(BaseModel):
    """Represents an uploaded file."""

    id: str
    filename: str
    purpose: str
    bytes: int
    created_at: datetime
    mime_type: Optional[str] = None


class FileUploadOptions(BaseModel):
    """Options for uploading a file."""

    purpose: Optional[str] = None
    mime_type: Optional[str] = None


class FileListResponse(BaseModel):
    """Response containing a list of files."""

    files: List[File]
    total: int
