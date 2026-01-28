"""Base HTTP client with retry and timeout support."""

import asyncio
from typing import Any

import httpx

from overwatch_mcp.models.errors import ErrorCode, OverwatchError


class BaseHTTPClient:
    """
    Base HTTP client with retry logic and error handling.

    Provides common functionality for all datasource clients.
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
        verify_ssl: bool = True,
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL for the API
            timeout_seconds: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
            headers: Default headers to include in all requests
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.default_headers = headers or {}
        self.verify_ssl = verify_ssl
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseHTTPClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            headers=self.default_headers,
            verify=self.verify_ssl,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                headers=self.default_headers,
                verify=self.verify_ssl,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retry_count: int = 0,
    ) -> httpx.Response:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            params: Query parameters
            json: JSON body
            headers: Additional headers
            retry_count: Current retry attempt

        Returns:
            HTTP response

        Raises:
            OverwatchError: On timeout, client error, or server error
        """
        client = await self._get_client()
        request_headers = {**self.default_headers, **(headers or {})}

        try:
            response = await client.request(
                method=method,
                url=path,
                params=params,
                json=json,
                headers=request_headers,
            )

            # Handle 4xx client errors
            if 400 <= response.status_code < 500:
                raise OverwatchError(
                    code=ErrorCode.UPSTREAM_CLIENT_ERROR,
                    message=f"Upstream client error: {response.status_code}",
                    details={
                        "status_code": response.status_code,
                        "response": response.text,
                        "url": str(response.url),
                    },
                )

            # Handle 5xx server errors with retry
            if 500 <= response.status_code < 600:
                if retry_count < self.max_retries:
                    # Exponential backoff: 1s, 2s, 4s
                    await asyncio.sleep(2**retry_count)
                    return await self._request(
                        method=method,
                        path=path,
                        params=params,
                        json=json,
                        headers=headers,
                        retry_count=retry_count + 1,
                    )
                else:
                    raise OverwatchError(
                        code=ErrorCode.UPSTREAM_SERVER_ERROR,
                        message=f"Upstream server error after {self.max_retries} retries",
                        details={
                            "status_code": response.status_code,
                            "response": response.text,
                            "url": str(response.url),
                        },
                    )

            response.raise_for_status()
            return response

        except httpx.TimeoutException as e:
            raise OverwatchError(
                code=ErrorCode.UPSTREAM_TIMEOUT,
                message=f"Request timed out after {self.timeout_seconds}s",
                details={"timeout_seconds": self.timeout_seconds, "error": str(e)},
            )
        except httpx.RequestError as e:
            # Network errors - retry if we haven't exceeded max retries
            if retry_count < self.max_retries:
                await asyncio.sleep(2**retry_count)
                return await self._request(
                    method=method,
                    path=path,
                    params=params,
                    json=json,
                    headers=headers,
                    retry_count=retry_count + 1,
                )
            else:
                raise OverwatchError(
                    code=ErrorCode.UPSTREAM_SERVER_ERROR,
                    message=f"Network error after {self.max_retries} retries: {str(e)}",
                    details={"error": str(e)},
                )

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """
        Make GET request.

        Args:
            path: API path
            params: Query parameters
            headers: Additional headers

        Returns:
            HTTP response
        """
        return await self._request("GET", path, params=params, headers=headers)

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """
        Make POST request.

        Args:
            path: API path
            json: JSON body
            params: Query parameters
            headers: Additional headers

        Returns:
            HTTP response
        """
        return await self._request(
            "POST", path, params=params, json=json, headers=headers
        )
