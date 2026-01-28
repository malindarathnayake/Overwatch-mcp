"""Integration tests for Graylog MCP tools."""

import pytest
from pytest_httpx import HTTPXMock

from overwatch_mcp.cache import Cache
from overwatch_mcp.clients.graylog import GraylogClient
from overwatch_mcp.models.config import GraylogConfig
from overwatch_mcp.models.errors import ErrorCode, OverwatchError
from overwatch_mcp.tools.graylog import graylog_fields, graylog_search


@pytest.fixture
def graylog_config() -> GraylogConfig:
    """Graylog test configuration."""
    return GraylogConfig(
        url="https://graylog.test:9000/api",
        token="test-token-123",
        timeout_seconds=30,
        max_time_range_hours=24,
        default_time_range_hours=1,
        max_results=1000,
        default_results=100,
    )


@pytest.fixture
def graylog_client(graylog_config: GraylogConfig) -> GraylogClient:
    """Graylog client fixture."""
    return GraylogClient(graylog_config)


@pytest.fixture
def cache() -> Cache:
    """Cache fixture."""
    return Cache(default_ttl=60)


class TestGraylogSearch:
    """Tests for graylog_search tool."""

    async def test_search_basic(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test basic search functionality."""
        # Mock API response
        httpx_mock.add_response(
            url="https://graylog.test:9000/api/api/search/universal/relative?query=level%3AERROR&limit=100&range=-1h",
            json={
                "messages": [
                    {
                        "timestamp": "2025-01-27T10:45:23.123Z",
                        "source": "api-server-01",
                        "level": "ERROR",
                        "message": "Connection timeout",
                    }
                ],
                "total_results": 1,
            }
        )

        # Execute tool
        result = await graylog_search(
            client=graylog_client,
            config=graylog_config,
            cache=cache,
            query="level:ERROR",
        )

        # Verify response structure
        assert result["total_results"] == 1
        assert result["returned"] == 1
        assert result["truncated"] is False
        assert result["query"] == "level:ERROR"
        assert "time_range" in result
        assert "from" in result["time_range"]
        assert "to" in result["time_range"]
        assert len(result["messages"]) == 1

    async def test_search_with_fields(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test search with specific fields."""
        httpx_mock.add_response(
            url="https://graylog.test:9000/api/api/search/universal/relative?query=service%3Aapi&limit=50&fields=timestamp%2Clevel%2Cmessage&range=-30m",
            json={
                "messages": [
                    {
                        "timestamp": "2025-01-27T10:45:23.123Z",
                        "level": "INFO",
                        "message": "Request processed",
                    }
                ],
                "total_results": 1,
            }
        )

        result = await graylog_search(
            client=graylog_client,
            config=graylog_config,
            cache=cache,
            query="service:api",
            from_time="-30m",
            limit=50,
            fields=["timestamp", "level", "message"],
        )

        assert result["returned"] == 1
        assert result["query"] == "service:api"

    async def test_search_truncated_results(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test search with truncated results."""
        # Mock more results than returned
        httpx_mock.add_response(
            url="https://graylog.test:9000/api/api/search/universal/relative?query=*&limit=10&range=-1h",
            json={
                "messages": [{"message": f"log {i}"} for i in range(10)],
                "total_results": 1000,
            }
        )

        result = await graylog_search(
            client=graylog_client,
            config=graylog_config,
            cache=cache,
            query="*",
            limit=10,
        )

        assert result["total_results"] == 1000
        assert result["returned"] == 10
        assert result["truncated"] is True

    async def test_search_limit_clamping(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test that limit is clamped to max_results."""
        # Request should be clamped to 1000 (config.max_results)
        httpx_mock.add_response(
            url="https://graylog.test:9000/api/api/search/universal/relative?query=*&limit=1000&range=-1h",
            json={
                "messages": [],
                "total_results": 0,
            }
        )

        result = await graylog_search(
            client=graylog_client,
            config=graylog_config,
            cache=cache,
            query="*",
            limit=5000,  # Request more than max
        )

        assert result["returned"] == 0

    async def test_search_time_range_exceeded(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
    ):
        """Test that time range validation rejects ranges exceeding max."""
        with pytest.raises(OverwatchError) as exc_info:
            await graylog_search(
                client=graylog_client,
                config=graylog_config,
                cache=cache,
                query="*",
                from_time="-48h",  # Exceeds 24h max
                to_time="now",
            )

        assert exc_info.value.code == ErrorCode.TIME_RANGE_EXCEEDED
        assert "48" in exc_info.value.message

    async def test_search_invalid_time_format(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
    ):
        """Test that invalid time format raises error."""
        with pytest.raises(OverwatchError) as exc_info:
            await graylog_search(
                client=graylog_client,
                config=graylog_config,
                cache=cache,
                query="*",
                from_time="invalid-time",
            )

        assert exc_info.value.code == ErrorCode.INVALID_QUERY

    async def test_search_from_after_to(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
    ):
        """Test that from_time after to_time raises error."""
        with pytest.raises(OverwatchError) as exc_info:
            await graylog_search(
                client=graylog_client,
                config=graylog_config,
                cache=cache,
                query="*",
                from_time="now",
                to_time="-1h",
            )

        assert exc_info.value.code == ErrorCode.INVALID_QUERY
        assert "before" in exc_info.value.message


class TestGraylogFields:
    """Tests for graylog_fields tool."""

    async def test_fields_no_filter(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test listing all fields without filter."""
        httpx_mock.add_response(
            url="https://graylog.test:9000/api/api/system/fields",
            json={
                "fields": {
                    "http_method": "string",
                    "http_status_code": "long",
                    "level": "string",
                    "message": "string",
                }
            }
        )

        result = await graylog_fields(
            client=graylog_client,
            config=graylog_config,
            cache=cache,
        )

        assert result["count"] == 4
        assert result["total_available"] == 4
        assert result["truncated"] is False
        assert result["pattern"] is None
        assert result["cached"] is False  # First call
        assert len(result["fields"]) == 4

        # Verify fields are sorted
        field_names = [f["name"] for f in result["fields"]]
        assert field_names == sorted(field_names)

    async def test_fields_with_pattern(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test filtering fields by pattern."""
        httpx_mock.add_response(
            url="https://graylog.test:9000/api/api/system/fields",
            json={
                "fields": {
                    "http_method": "string",
                    "http_status_code": "long",
                    "level": "string",
                    "message": "string",
                }
            }
        )

        result = await graylog_fields(
            client=graylog_client,
            config=graylog_config,
            cache=cache,
            pattern="http_.*",
        )

        assert result["count"] == 2
        assert result["total_available"] == 2
        assert result["pattern"] == "http_.*"

        field_names = [f["name"] for f in result["fields"]]
        assert "http_method" in field_names
        assert "http_status_code" in field_names
        assert "level" not in field_names

    async def test_fields_case_insensitive_pattern(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test that pattern matching is case-insensitive."""
        httpx_mock.add_response(
            url="https://graylog.test:9000/api/api/system/fields",
            json={
                "fields": {
                    "HTTP_Method": "string",
                    "http_status": "long",
                    "Level": "string",
                }
            }
        )

        result = await graylog_fields(
            client=graylog_client,
            config=graylog_config,
            cache=cache,
            pattern="http",
        )

        assert result["count"] == 2
        field_names = [f["name"] for f in result["fields"]]
        assert "HTTP_Method" in field_names
        assert "http_status" in field_names

    async def test_fields_with_limit(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test limiting number of returned fields."""
        fields_data = {f"field_{i}": "string" for i in range(50)}
        httpx_mock.add_response(
            url="https://graylog.test:9000/api/api/system/fields",
            json={"fields": fields_data}
        )

        result = await graylog_fields(
            client=graylog_client,
            config=graylog_config,
            cache=cache,
            limit=10,
        )

        assert result["count"] == 10
        assert result["total_available"] == 50
        assert result["truncated"] is True

    async def test_fields_caching(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test that field list is cached."""
        httpx_mock.add_response(
            url="https://graylog.test:9000/api/api/system/fields",
            json={
                "fields": {
                    "field1": "string",
                    "field2": "long",
                }
            }
        )

        # First call - should hit API
        result1 = await graylog_fields(
            client=graylog_client,
            config=graylog_config,
            cache=cache,
        )
        assert result1["cached"] is False

        # Second call - should use cache
        result2 = await graylog_fields(
            client=graylog_client,
            config=graylog_config,
            cache=cache,
        )
        assert result2["cached"] is True

        # Should only have made one HTTP request
        assert len(httpx_mock.get_requests()) == 1

    async def test_fields_invalid_pattern(
        self,
        graylog_client: GraylogClient,
        graylog_config: GraylogConfig,
        cache: Cache,
    ):
        """Test that invalid regex pattern raises error."""
        with pytest.raises(OverwatchError) as exc_info:
            await graylog_fields(
                client=graylog_client,
                config=graylog_config,
                cache=cache,
                pattern="[invalid",  # Invalid regex
            )

        assert exc_info.value.code == ErrorCode.INVALID_PATTERN
        assert "Invalid regex pattern" in exc_info.value.message
