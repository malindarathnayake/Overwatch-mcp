"""Tests for Graylog client."""

import pytest
from pytest_httpx import HTTPXMock

from overwatch_mcp.clients.graylog import GraylogClient
from overwatch_mcp.models.config import GraylogConfig
from overwatch_mcp.models.errors import ErrorCode, OverwatchError


@pytest.fixture
def graylog_config() -> GraylogConfig:
    """Graylog test configuration."""
    return GraylogConfig(
        url="https://graylog.test:9000",
        token="test-token-123",
        timeout_seconds=30,
        max_results=1000,
    )


@pytest.fixture
def graylog_client(graylog_config: GraylogConfig) -> GraylogClient:
    """Graylog client fixture."""
    return GraylogClient(graylog_config)


class TestGraylogClient:
    """Tests for GraylogClient class."""

    async def test_client_initialization(self, graylog_client: GraylogClient):
        """Test client initializes with correct config."""
        assert graylog_client.base_url == "https://graylog.test:9000"
        assert graylog_client.timeout_seconds == 30
        assert "Authorization" in graylog_client.default_headers
        assert graylog_client.default_headers["Authorization"] == "Bearer test-token-123"

    async def test_parse_time_relative(self, graylog_client: GraylogClient):
        """Test parsing relative time strings."""
        assert graylog_client._parse_time("-1h") == "-1h"
        assert graylog_client._parse_time("-30m") == "-30m"
        assert graylog_client._parse_time("now") == "now"

    async def test_parse_time_iso8601(self, graylog_client: GraylogClient):
        """Test parsing ISO8601 time strings."""
        result = graylog_client._parse_time("2025-01-27T10:00:00Z")
        assert isinstance(result, int)
        assert result > 0

    async def test_parse_time_invalid(self, graylog_client: GraylogClient):
        """Test parsing invalid time strings raises error."""
        with pytest.raises(OverwatchError) as exc_info:
            graylog_client._parse_time("invalid-time")
        assert exc_info.value.code == ErrorCode.INVALID_QUERY

    async def test_search_relative_time(
        self, graylog_client: GraylogClient, httpx_mock: HTTPXMock
    ):
        """Test search with relative time."""
        mock_response = {
            "total_results": 150,
            "messages": [
                {
                    "timestamp": "2025-01-27T10:45:23.123Z",
                    "message": "Test log message",
                }
            ],
        }
        httpx_mock.add_response(json=mock_response)

        async with graylog_client:
            result = await graylog_client.search(
                query="level:ERROR", from_time="-1h", to_time="now", limit=100
            )

        assert result["total_results"] == 150
        assert len(result["messages"]) == 1

    async def test_search_absolute_time(
        self, graylog_client: GraylogClient, httpx_mock: HTTPXMock
    ):
        """Test search with absolute time."""
        mock_response = {
            "total_results": 50,
            "messages": [],
        }
        httpx_mock.add_response(json=mock_response)

        async with graylog_client:
            result = await graylog_client.search(
                query="service:api",
                from_time="2025-01-27T10:00:00Z",
                to_time="2025-01-27T11:00:00Z",
                limit=100,
            )

        assert result["total_results"] == 50

    async def test_search_with_fields(
        self, graylog_client: GraylogClient, httpx_mock: HTTPXMock
    ):
        """Test search with specific fields."""
        mock_response = {"total_results": 10, "messages": []}
        httpx_mock.add_response(json=mock_response)

        async with graylog_client:
            result = await graylog_client.search(
                query="*",
                from_time="-1h",
                to_time="now",
                limit=50,
                fields=["timestamp", "message", "level"],
            )

        request = httpx_mock.get_request()
        assert "fields=timestamp%2Cmessage%2Clevel" in str(request.url)

    async def test_search_respects_max_results(
        self, graylog_client: GraylogClient, httpx_mock: HTTPXMock
    ):
        """Test search respects max_results config."""
        mock_response = {"total_results": 0, "messages": []}
        httpx_mock.add_response(json=mock_response)

        async with graylog_client:
            await graylog_client.search(
                query="*", from_time="-1h", to_time="now", limit=2000  # Over max
            )

        request = httpx_mock.get_request()
        # Should be clamped to max_results (1000)
        assert "limit=1000" in str(request.url)

    async def test_get_fields(
        self, graylog_client: GraylogClient, httpx_mock: HTTPXMock
    ):
        """Test getting field list."""
        mock_response = {
            "fields": [
                {"name": "timestamp", "type": "date"},
                {"name": "message", "type": "string"},
                {"name": "level", "type": "string"},
            ]
        }
        httpx_mock.add_response(json=mock_response)

        async with graylog_client:
            result = await graylog_client.get_fields()

        assert len(result["fields"]) == 3
        assert result["fields"][0]["name"] == "timestamp"

    async def test_health_check_success(
        self, graylog_client: GraylogClient, httpx_mock: HTTPXMock
    ):
        """Test health check when service is healthy."""
        httpx_mock.add_response(status_code=200)

        async with graylog_client:
            result = await graylog_client.health_check()

        assert result is True

    async def test_health_check_failure(
        self, graylog_client: GraylogClient, httpx_mock: HTTPXMock
    ):
        """Test health check when service is down."""
        # Add multiple responses for retries (initial + 3 retries)
        for _ in range(4):
            httpx_mock.add_response(status_code=503)

        async with graylog_client:
            result = await graylog_client.health_check()

        assert result is False

    async def test_timeout_error(
        self, graylog_client: GraylogClient, httpx_mock: HTTPXMock
    ):
        """Test handling of timeout errors."""
        import httpx
        httpx_mock.add_exception(httpx.TimeoutException("Timeout"))

        async with graylog_client:
            with pytest.raises(OverwatchError) as exc_info:
                await graylog_client.search(query="*")

        assert exc_info.value.code == ErrorCode.UPSTREAM_TIMEOUT

    async def test_4xx_error(
        self, graylog_client: GraylogClient, httpx_mock: HTTPXMock
    ):
        """Test handling of 4xx client errors."""
        httpx_mock.add_response(status_code=401, text="Unauthorized")

        async with graylog_client:
            with pytest.raises(OverwatchError) as exc_info:
                await graylog_client.search(query="*")

        assert exc_info.value.code == ErrorCode.UPSTREAM_CLIENT_ERROR
        assert "401" in exc_info.value.message

    async def test_5xx_error_with_retry(
        self, graylog_client: GraylogClient, httpx_mock: HTTPXMock
    ):
        """Test handling of 5xx server errors with retry."""
        # First 2 attempts fail, third succeeds
        httpx_mock.add_response(status_code=503)
        httpx_mock.add_response(status_code=503)
        httpx_mock.add_response(
            json={"total_results": 0, "messages": []}, status_code=200
        )

        async with graylog_client:
            result = await graylog_client.search(query="*")

        assert result["total_results"] == 0
        assert len(httpx_mock.get_requests()) == 3

    async def test_5xx_error_max_retries_exceeded(
        self, graylog_client: GraylogClient, httpx_mock: HTTPXMock
    ):
        """Test 5xx errors after max retries."""
        # All attempts fail
        for _ in range(4):  # Initial + 3 retries
            httpx_mock.add_response(status_code=503)

        async with graylog_client:
            with pytest.raises(OverwatchError) as exc_info:
                await graylog_client.search(query="*")

        assert exc_info.value.code == ErrorCode.UPSTREAM_SERVER_ERROR
        assert "retries" in exc_info.value.message
