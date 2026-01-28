"""Prometheus API client."""

import logging
from datetime import datetime
from typing import Any

from overwatch_mcp.clients.base import BaseHTTPClient
from overwatch_mcp.models.config import PrometheusConfig
from overwatch_mcp.models.errors import ErrorCode, OverwatchError

logger = logging.getLogger(__name__)


class PrometheusClient(BaseHTTPClient):
    """Client for Prometheus API."""

    def __init__(self, config: PrometheusConfig):
        """
        Initialize Prometheus client.

        Args:
            config: Prometheus configuration
        """
        # Normalize URL - strip /api/v1 suffix if present (paths already include it)
        url = config.url.rstrip("/")
        if url.endswith("/api/v1"):
            url = url[:-7]
        elif url.endswith("/api"):
            url = url[:-4]
        
        super().__init__(
            base_url=url,
            timeout_seconds=config.timeout_seconds,
            verify_ssl=config.verify_ssl,
        )
        self.config = config

    def _parse_time(self, time_str: str) -> str | float:
        """
        Parse time string to appropriate format for Prometheus API.

        Args:
            time_str: Time string (ISO8601, Unix timestamp, or relative like '-1h')

        Returns:
            Unix timestamp or relative time string

        Raises:
            OverwatchError: If time format is invalid
        """
        # Handle relative times (e.g., '-1h', 'now')
        if time_str == "now" or time_str.startswith("-"):
            return time_str

        # Try parsing as Unix timestamp
        try:
            return float(time_str)
        except ValueError:
            pass

        # Try parsing as ISO8601
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, AttributeError) as e:
            raise OverwatchError(
                code=ErrorCode.INVALID_QUERY,
                message=f"Invalid time format: {time_str}",
                details={"error": str(e)},
            )

    def _parse_duration(self, duration_str: str) -> int:
        """
        Parse duration string to seconds.

        Args:
            duration_str: Duration like '15s', '1m', '1h'

        Returns:
            Duration in seconds

        Raises:
            OverwatchError: If duration format is invalid
        """
        if not duration_str:
            raise OverwatchError(
                code=ErrorCode.INVALID_QUERY,
                message="Empty duration string",
            )

        try:
            if duration_str.endswith("s"):
                return int(duration_str[:-1])
            elif duration_str.endswith("m"):
                return int(duration_str[:-1]) * 60
            elif duration_str.endswith("h"):
                return int(duration_str[:-1]) * 3600
            elif duration_str.endswith("d"):
                return int(duration_str[:-1]) * 86400
            else:
                # Try parsing as raw seconds
                return int(duration_str)
        except (ValueError, IndexError) as e:
            raise OverwatchError(
                code=ErrorCode.INVALID_QUERY,
                message=f"Invalid duration format: {duration_str}",
                details={"error": str(e)},
            )

    async def query(self, query: str, time: str | None = None) -> dict[str, Any]:
        """
        Execute instant PromQL query.

        Args:
            query: PromQL expression
            time: Evaluation time (ISO8601, Unix, or relative). Default: now

        Returns:
            Query result dictionary

        Raises:
            OverwatchError: On API errors or invalid parameters
        """
        params: dict[str, Any] = {"query": query}

        if time:
            params["time"] = self._parse_time(time)

        response = await self.get("/api/v1/query", params=params)
        data = response.json()

        # Prometheus wraps response in {"status": "success", "data": {...}}
        if data.get("status") != "success":
            raise OverwatchError(
                code=ErrorCode.UPSTREAM_CLIENT_ERROR,
                message=f"Prometheus query failed: {data.get('error', 'Unknown error')}",
                details=data,
            )

        return data["data"]

    async def query_range(
        self,
        query: str,
        start: str,
        end: str,
        step: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute PromQL range query.

        Args:
            query: PromQL expression
            start: Start time (ISO8601, Unix, or relative)
            end: End time (ISO8601, Unix, or relative)
            step: Query resolution (e.g., '15s', '1m'). Auto-calculated if None

        Returns:
            Range query result dictionary

        Raises:
            OverwatchError: On API errors or invalid parameters
        """
        parsed_start = self._parse_time(start)
        parsed_end = self._parse_time(end)

        # Calculate step if not provided
        if step is None:
            # Auto-calculate: aim for ~250 data points
            if isinstance(parsed_start, (int, float)) and isinstance(
                parsed_end, (int, float)
            ):
                range_seconds = int(parsed_end - parsed_start)
                step_seconds = max(1, range_seconds // 250)
                step = f"{step_seconds}s"
            else:
                # Can't auto-calculate for relative times, use default
                step = "15s"

        params: dict[str, Any] = {
            "query": query,
            "start": parsed_start,
            "end": parsed_end,
            "step": step,
        }

        response = await self.get("/api/v1/query_range", params=params)
        data = response.json()

        if data.get("status") != "success":
            raise OverwatchError(
                code=ErrorCode.UPSTREAM_CLIENT_ERROR,
                message=f"Prometheus range query failed: {data.get('error', 'Unknown error')}",
                details=data,
            )

        return data["data"]

    async def get_metrics(self) -> list[str]:
        """
        Get list of all metric names.

        Returns:
            List of metric names

        Raises:
            OverwatchError: On API errors
        """
        response = await self.get("/api/v1/label/__name__/values")
        data = response.json()

        if data.get("status") != "success":
            raise OverwatchError(
                code=ErrorCode.UPSTREAM_CLIENT_ERROR,
                message=f"Failed to fetch metrics: {data.get('error', 'Unknown error')}",
                details=data,
            )

        return data["data"]

    async def health_check(self) -> bool:
        """
        Check if Prometheus is reachable.

        Returns:
            True if healthy, False otherwise
        """
        endpoint = "/-/healthy"
        full_url = f"{self.base_url}{endpoint}"
        logger.debug(f"Prometheus health check: {full_url}")
        try:
            response = await self.get(endpoint)
            logger.debug(f"Prometheus health response: {response.status_code}")
            return response.status_code == 200
        except OverwatchError as e:
            logger.debug(f"Prometheus health check failed: {e}")
            return False
