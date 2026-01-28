"""Graylog API client."""

import logging
from datetime import datetime
from typing import Any

from overwatch_mcp.clients.base import BaseHTTPClient
from overwatch_mcp.models.config import GraylogConfig
from overwatch_mcp.models.errors import ErrorCode, OverwatchError

logger = logging.getLogger(__name__)


class GraylogClient(BaseHTTPClient):
    """Client for Graylog API."""

    def __init__(self, config: GraylogConfig):
        """
        Initialize Graylog client.

        Args:
            config: Graylog configuration
        """
        # Normalize URL - strip /api suffix if present (paths already include /api/)
        url = config.url.rstrip("/")
        if url.endswith("/api"):
            url = url[:-4]
        
        headers = {
            "Authorization": f"Bearer {config.token}",
            "Accept": "application/json",
        }
        super().__init__(
            base_url=url,
            timeout_seconds=config.timeout_seconds,
            headers=headers,
            verify_ssl=config.verify_ssl,
        )
        self.config = config

    def _parse_time(self, time_str: str) -> str | int:
        """
        Parse time string to appropriate format for Graylog API.

        Args:
            time_str: Time string (ISO8601 or relative like '-1h', 'now')

        Returns:
            Formatted time string or Unix timestamp

        Raises:
            OverwatchError: If time format is invalid
        """
        # Handle relative times (e.g., '-1h', '-30m', 'now')
        if time_str == "now" or time_str.startswith("-"):
            return time_str

        # Try parsing as ISO8601
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except (ValueError, AttributeError) as e:
            raise OverwatchError(
                code=ErrorCode.INVALID_QUERY,
                message=f"Invalid time format: {time_str}",
                details={"error": str(e)},
            )

    async def search(
        self,
        query: str,
        from_time: str = "-1h",
        to_time: str = "now",
        limit: int = 100,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Search Graylog logs.

        Args:
            query: Graylog search query (Lucene syntax)
            from_time: Start time (ISO8601 or relative)
            to_time: End time (ISO8601 or relative)
            limit: Maximum results
            fields: Fields to return (None = all)

        Returns:
            Search results dictionary

        Raises:
            OverwatchError: On API errors or invalid parameters
        """
        # Parse times
        parsed_from = self._parse_time(from_time)
        parsed_to = self._parse_time(to_time)

        # Determine if we're using relative or absolute search
        use_relative = isinstance(parsed_from, str) and isinstance(parsed_to, str)

        # Build request params
        params: dict[str, Any] = {
            "query": query,
            "limit": min(limit, self.config.max_results),
        }

        if fields:
            params["fields"] = ",".join(fields)

        # Choose endpoint based on time format
        if use_relative:
            endpoint = "/api/search/universal/relative"
            params["range"] = parsed_from  # e.g., "-1h"
        else:
            endpoint = "/api/search/universal/absolute"
            params["from"] = parsed_from
            params["to"] = parsed_to

        # Make request
        response = await self.get(endpoint, params=params)
        return response.json()

    async def get_fields(self) -> dict[str, Any]:
        """
        Get available fields from Graylog.

        Returns:
            Fields dictionary with field names and types

        Raises:
            OverwatchError: On API errors
        """
        response = await self.get("/api/system/fields")
        return response.json()

    async def health_check(self) -> bool:
        """
        Check if Graylog is reachable.

        Returns:
            True if healthy, False otherwise
        """
        endpoint = "/api/system/lbstatus"
        full_url = f"{self.base_url}{endpoint}"
        logger.debug(f"Graylog health check: {full_url}")
        try:
            response = await self.get(endpoint)
            logger.debug(f"Graylog health response: {response.status_code} - {response.text[:200]}")
            return response.status_code == 200
        except OverwatchError as e:
            logger.debug(f"Graylog health check failed: {e}")
            return False
