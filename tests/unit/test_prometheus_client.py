"""Tests for Prometheus client."""

import pytest
from pytest_httpx import HTTPXMock

from overwatch_mcp.clients.prometheus import PrometheusClient
from overwatch_mcp.models.config import PrometheusConfig
from overwatch_mcp.models.errors import ErrorCode, OverwatchError


@pytest.fixture
def prometheus_config() -> PrometheusConfig:
    """Prometheus test configuration."""
    return PrometheusConfig(
        url="http://prometheus.test:9090",
        timeout_seconds=30,
    )


@pytest.fixture
def prometheus_client(prometheus_config: PrometheusConfig) -> PrometheusClient:
    """Prometheus client fixture."""
    return PrometheusClient(prometheus_config)


class TestPrometheusClient:
    """Tests for PrometheusClient class."""

    async def test_client_initialization(self, prometheus_client: PrometheusClient):
        """Test client initializes with correct config."""
        assert prometheus_client.base_url == "http://prometheus.test:9090"
        assert prometheus_client.timeout_seconds == 30

    async def test_parse_time_relative(self, prometheus_client: PrometheusClient):
        """Test parsing relative time strings."""
        assert prometheus_client._parse_time("-1h") == "-1h"
        assert prometheus_client._parse_time("now") == "now"

    async def test_parse_time_unix(self, prometheus_client: PrometheusClient):
        """Test parsing Unix timestamps."""
        result = prometheus_client._parse_time("1706356800")
        assert result == 1706356800.0

    async def test_parse_time_iso8601(self, prometheus_client: PrometheusClient):
        """Test parsing ISO8601 time strings."""
        result = prometheus_client._parse_time("2025-01-27T10:00:00Z")
        assert isinstance(result, float)
        assert result > 0

    async def test_parse_time_invalid(self, prometheus_client: PrometheusClient):
        """Test parsing invalid time strings raises error."""
        with pytest.raises(OverwatchError) as exc_info:
            prometheus_client._parse_time("invalid-time")
        assert exc_info.value.code == ErrorCode.INVALID_QUERY

    async def test_parse_duration_seconds(self, prometheus_client: PrometheusClient):
        """Test parsing duration in seconds."""
        assert prometheus_client._parse_duration("15s") == 15
        assert prometheus_client._parse_duration("60s") == 60

    async def test_parse_duration_minutes(self, prometheus_client: PrometheusClient):
        """Test parsing duration in minutes."""
        assert prometheus_client._parse_duration("1m") == 60
        assert prometheus_client._parse_duration("5m") == 300

    async def test_parse_duration_hours(self, prometheus_client: PrometheusClient):
        """Test parsing duration in hours."""
        assert prometheus_client._parse_duration("1h") == 3600
        assert prometheus_client._parse_duration("24h") == 86400

    async def test_parse_duration_days(self, prometheus_client: PrometheusClient):
        """Test parsing duration in days."""
        assert prometheus_client._parse_duration("1d") == 86400
        assert prometheus_client._parse_duration("7d") == 604800

    async def test_parse_duration_raw_seconds(self, prometheus_client: PrometheusClient):
        """Test parsing raw seconds."""
        assert prometheus_client._parse_duration("30") == 30

    async def test_parse_duration_invalid(self, prometheus_client: PrometheusClient):
        """Test parsing invalid duration raises error."""
        with pytest.raises(OverwatchError) as exc_info:
            prometheus_client._parse_duration("invalid")
        assert exc_info.value.code == ErrorCode.INVALID_QUERY

    async def test_parse_duration_empty(self, prometheus_client: PrometheusClient):
        """Test parsing empty duration raises error."""
        with pytest.raises(OverwatchError) as exc_info:
            prometheus_client._parse_duration("")
        assert exc_info.value.code == ErrorCode.INVALID_QUERY

    async def test_query_instant(
        self, prometheus_client: PrometheusClient, httpx_mock: HTTPXMock
    ):
        """Test instant query."""
        mock_response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"__name__": "up", "job": "prometheus"},
                        "value": [1706356800, "1"],
                    }
                ],
            },
        }
        httpx_mock.add_response(json=mock_response)

        async with prometheus_client:
            result = await prometheus_client.query("up")

        assert result["resultType"] == "vector"
        assert len(result["result"]) == 1

    async def test_query_with_time(
        self, prometheus_client: PrometheusClient, httpx_mock: HTTPXMock
    ):
        """Test instant query with specific time."""
        mock_response = {
            "status": "success",
            "data": {"resultType": "vector", "result": []},
        }
        httpx_mock.add_response(json=mock_response)

        async with prometheus_client:
            await prometheus_client.query("up", time="2025-01-27T10:00:00Z")

        request = httpx_mock.get_request()
        assert "time=" in str(request.url)

    async def test_query_failure(
        self, prometheus_client: PrometheusClient, httpx_mock: HTTPXMock
    ):
        """Test query failure handling."""
        mock_response = {
            "status": "error",
            "errorType": "bad_data",
            "error": "invalid query",
        }
        httpx_mock.add_response(json=mock_response)

        async with prometheus_client:
            with pytest.raises(OverwatchError) as exc_info:
                await prometheus_client.query("invalid{query")

        assert exc_info.value.code == ErrorCode.UPSTREAM_CLIENT_ERROR
        assert "query failed" in exc_info.value.message.lower()

    async def test_query_range(
        self, prometheus_client: PrometheusClient, httpx_mock: HTTPXMock
    ):
        """Test range query."""
        mock_response = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "http_requests_total"},
                        "values": [[1706356800, "100"], [1706356860, "105"]],
                    }
                ],
            },
        }
        httpx_mock.add_response(json=mock_response)

        async with prometheus_client:
            result = await prometheus_client.query_range(
                query="http_requests_total",
                start="2025-01-27T10:00:00Z",
                end="2025-01-27T11:00:00Z",
                step="1m",
            )

        assert result["resultType"] == "matrix"
        assert len(result["result"]) == 1

    async def test_query_range_auto_step(
        self, prometheus_client: PrometheusClient, httpx_mock: HTTPXMock
    ):
        """Test range query with auto-calculated step."""
        mock_response = {
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
        }
        httpx_mock.add_response(json=mock_response)

        async with prometheus_client:
            await prometheus_client.query_range(
                query="up",
                start="1706356800",  # Unix timestamp
                end="1706360400",    # 1 hour later
                step=None,           # Auto-calculate
            )

        request = httpx_mock.get_request()
        # Should calculate step for ~250 points over 3600 seconds
        assert "step=" in str(request.url)

    async def test_query_range_relative_time_default_step(
        self, prometheus_client: PrometheusClient, httpx_mock: HTTPXMock
    ):
        """Test range query with relative time uses default step."""
        mock_response = {
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
        }
        httpx_mock.add_response(json=mock_response)

        async with prometheus_client:
            await prometheus_client.query_range(
                query="up",
                start="-1h",
                end="now",
                step=None,
            )

        request = httpx_mock.get_request()
        # Should use default 15s when can't auto-calculate
        assert "step=15s" in str(request.url)

    async def test_get_metrics(
        self, prometheus_client: PrometheusClient, httpx_mock: HTTPXMock
    ):
        """Test getting metric list."""
        mock_response = {
            "status": "success",
            "data": [
                "http_requests_total",
                "http_request_duration_seconds",
                "up",
            ],
        }
        httpx_mock.add_response(
            url="http://prometheus.test:9090/api/v1/label/__name__/values",
            json=mock_response,
        )

        async with prometheus_client:
            result = await prometheus_client.get_metrics()

        assert len(result) == 3
        assert "up" in result

    async def test_get_metrics_failure(
        self, prometheus_client: PrometheusClient, httpx_mock: HTTPXMock
    ):
        """Test metric list failure handling."""
        mock_response = {"status": "error", "error": "internal error"}
        httpx_mock.add_response(json=mock_response)

        async with prometheus_client:
            with pytest.raises(OverwatchError) as exc_info:
                await prometheus_client.get_metrics()

        assert exc_info.value.code == ErrorCode.UPSTREAM_CLIENT_ERROR

    async def test_health_check_success(
        self, prometheus_client: PrometheusClient, httpx_mock: HTTPXMock
    ):
        """Test health check when service is healthy."""
        httpx_mock.add_response(status_code=200)

        async with prometheus_client:
            result = await prometheus_client.health_check()

        assert result is True

    async def test_health_check_failure(
        self, prometheus_client: PrometheusClient, httpx_mock: HTTPXMock
    ):
        """Test health check when service is down."""
        # Add multiple responses for retries (initial + 3 retries)
        for _ in range(4):
            httpx_mock.add_response(status_code=503)

        async with prometheus_client:
            result = await prometheus_client.health_check()

        assert result is False
