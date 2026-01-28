"""InfluxDB 2.x API client."""

import csv
import io
import logging
from typing import Any

from overwatch_mcp.clients.base import BaseHTTPClient
from overwatch_mcp.models.config import InfluxDBConfig
from overwatch_mcp.models.errors import ErrorCode, OverwatchError

logger = logging.getLogger(__name__)


class InfluxDBClient(BaseHTTPClient):
    """Client for InfluxDB 2.x API."""

    def __init__(self, config: InfluxDBConfig):
        """
        Initialize InfluxDB client.

        Args:
            config: InfluxDB configuration
        """
        # Normalize URL - strip /api/v2 suffix if present (paths already include it)
        url = config.url.rstrip("/")
        if url.endswith("/api/v2"):
            url = url[:-7]
        elif url.endswith("/api"):
            url = url[:-4]
        
        headers = {
            "Authorization": f"Token {config.token}",
            "Accept": "application/csv",
            "Content-Type": "application/vnd.flux",
        }
        super().__init__(
            base_url=url,
            timeout_seconds=config.timeout_seconds,
            headers=headers,
            verify_ssl=config.verify_ssl,
        )
        self.config = config

    def _validate_bucket(self, bucket: str) -> None:
        """
        Validate bucket against allowlist.

        Args:
            bucket: Bucket name to validate

        Raises:
            OverwatchError: If bucket is not in allowlist
        """
        if bucket not in self.config.allowed_buckets:
            raise OverwatchError(
                code=ErrorCode.BUCKET_NOT_ALLOWED,
                message=f"Bucket '{bucket}' is not in allowed list",
                details={
                    "requested_bucket": bucket,
                    "allowed_buckets": self.config.allowed_buckets,
                },
            )

    def _validate_query_bucket(self, query: str, bucket: str) -> None:
        """
        Validate that query references the specified bucket.

        Args:
            query: Flux query
            bucket: Expected bucket name

        Raises:
            OverwatchError: If query doesn't reference the correct bucket
        """
        # Simple validation - check if 'from(bucket: "name")' exists
        if f'from(bucket: "{bucket}")' not in query and f"from(bucket:\"{bucket}\")" not in query:
            raise OverwatchError(
                code=ErrorCode.INVALID_QUERY,
                message=f"Query must reference bucket '{bucket}'",
                details={"bucket": bucket, "query": query[:200]},
            )

    def _parse_csv_response(self, csv_text: str) -> list[dict[str, Any]]:
        """
        Parse InfluxDB annotated CSV response to list of records.

        InfluxDB returns CSV with annotation rows (starting with #) followed by data.

        Args:
            csv_text: CSV response text

        Returns:
            List of record dictionaries

        Raises:
            OverwatchError: If CSV parsing fails
        """
        try:
            lines = csv_text.strip().split("\n")
            if not lines:
                return []

            # Find where annotation rows end and data begins
            # Annotations start with #, then comes header row, then data rows
            has_annotations = any(line.startswith("#") for line in lines)

            non_annotation_lines = []
            for line in lines:
                if not line.startswith("#"):
                    non_annotation_lines.append(line)

            # If we have no annotations and multiple lines, this isn't InfluxDB format
            if not has_annotations and len(lines) > 1:
                raise ValueError("Invalid InfluxDB CSV format: missing annotation rows")

            if len(non_annotation_lines) < 1:  # Need at least header
                return []

            # First non-annotation line is the header
            header_line = non_annotation_lines[0]
            data_lines = non_annotation_lines[1:] if len(non_annotation_lines) > 1 else []

            # If there are no data lines (only empty lines), return empty
            if not any(line.strip() for line in data_lines):
                return []

            # Parse CSV
            reader = csv.DictReader(
                io.StringIO("\n".join([header_line] + data_lines))
            )
            return list(reader)

        except Exception as e:
            raise OverwatchError(
                code=ErrorCode.UPSTREAM_CLIENT_ERROR,
                message=f"Failed to parse InfluxDB CSV response: {str(e)}",
                details={"error": str(e), "csv_preview": csv_text[:500]},
            )

    async def query(self, query: str, bucket: str) -> list[dict[str, Any]]:
        """
        Execute Flux query against InfluxDB.

        Args:
            query: Flux query
            bucket: Target bucket

        Returns:
            List of records

        Raises:
            OverwatchError: On API errors, bucket not allowed, or parsing failures
        """
        # Validate bucket
        self._validate_bucket(bucket)
        self._validate_query_bucket(query, bucket)

        # Add org parameter
        params = {"org": self.config.org}

        # Make request with raw Flux query body
        client = await self._get_client()
        try:
            response = await client.post(
                "/api/v2/query",
                params=params,
                content=query,
                headers={
                    **self.default_headers,
                    "Content-Type": "application/vnd.flux",
                },
            )

            if response.status_code != 200:
                raise OverwatchError(
                    code=ErrorCode.UPSTREAM_CLIENT_ERROR,
                    message=f"InfluxDB query failed: {response.status_code}",
                    details={
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                )

            # Parse CSV response
            return self._parse_csv_response(response.text)

        except OverwatchError:
            raise
        except Exception as e:
            raise OverwatchError(
                code=ErrorCode.UPSTREAM_SERVER_ERROR,
                message=f"InfluxDB request failed: {str(e)}",
                details={"error": str(e)},
            )

    async def health_check(self) -> bool:
        """
        Check if InfluxDB is reachable.

        Returns:
            True if healthy, False otherwise
        """
        endpoint = "/health"
        full_url = f"{self.base_url}{endpoint}"
        logger.debug(f"InfluxDB health check: {full_url}")
        try:
            response = await self.get(endpoint)
            logger.debug(f"InfluxDB health response: {response.status_code} - {response.text[:200]}")
            return response.status_code == 200
        except OverwatchError as e:
            logger.debug(f"InfluxDB health check failed: {e}")
            return False
