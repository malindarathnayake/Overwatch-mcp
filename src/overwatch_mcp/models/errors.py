"""Error types and schemas for the MCP server."""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class ErrorCode(str, Enum):
    """Error codes for tool responses."""

    DATASOURCE_DISABLED = "DATASOURCE_DISABLED"
    DATASOURCE_UNAVAILABLE = "DATASOURCE_UNAVAILABLE"
    INVALID_QUERY = "INVALID_QUERY"
    INVALID_PATTERN = "INVALID_PATTERN"
    TIME_RANGE_EXCEEDED = "TIME_RANGE_EXCEEDED"
    BUCKET_NOT_ALLOWED = "BUCKET_NOT_ALLOWED"
    RESULTS_TRUNCATED = "RESULTS_TRUNCATED"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_CLIENT_ERROR = "UPSTREAM_CLIENT_ERROR"
    UPSTREAM_SERVER_ERROR = "UPSTREAM_SERVER_ERROR"
    RATE_LIMITED = "RATE_LIMITED"


class ErrorDetail(BaseModel):
    """Structured error details."""

    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: ErrorDetail


class OverwatchError(Exception):
    """Base exception for overwatch-mcp errors."""

    def __init__(self, code: ErrorCode, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_response(self) -> ErrorResponse:
        """Convert to error response model."""
        return ErrorResponse(
            error=ErrorDetail(
                code=self.code,
                message=self.message,
                details=self.details if self.details else None,
            )
        )
