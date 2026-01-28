"""Integration tests for Prometheus MCP tools."""

import re

import pytest
from pytest_httpx import HTTPXMock

from overwatch_mcp.cache import Cache
from overwatch_mcp.clients.prometheus import PrometheusClient
from overwatch_mcp.models.config import PrometheusConfig
from overwatch_mcp.models.errors import ErrorCode, OverwatchError
from overwatch_mcp.tools.prometheus import (
    prometheus_metrics,
    prometheus_query,
    prometheus_query_range,
)


@pytest.fixture
def prometheus_config() -> PrometheusConfig:
    """Prometheus test configuration."""
    return PrometheusConfig(
        url="http://prometheus.test:9090",
        timeout_seconds=30,
        max_range_hours=168,
        max_step_seconds=3600,
        max_series=10000,
        max_metric_results=500,
    )


@pytest.fixture
def prometheus_client(prometheus_config: PrometheusConfig) -> PrometheusClient:
    """Prometheus client fixture."""
    return PrometheusClient(prometheus_config)


@pytest.fixture
def cache() -> Cache:
    """Cache fixture."""
    return Cache(default_ttl=60)


class TestPrometheusQuery:
    """Tests for prometheus_query tool."""

    async def test_query_instant_basic(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test basic instant query."""
        httpx_mock.add_response(
            url="http://prometheus.test:9090/api/v1/query?query=up",
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {"__name__": "up", "job": "prometheus"},
                            "value": [1706356800, "1"]
                        }
                    ]
                }
            }
        )

        result = await prometheus_query(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            query="up",
        )

        assert result["resultType"] == "vector"
        assert len(result["result"]) == 1
        assert result["result"][0]["metric"]["job"] == "prometheus"

    async def test_query_with_time(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test query with specific evaluation time."""
        httpx_mock.add_response(
            url="http://prometheus.test:9090/api/v1/query?query=up&time=1706356800.0",
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": []
                }
            }
        )

        result = await prometheus_query(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            query="up",
            time="1706356800",
        )

        assert result["resultType"] == "vector"

    async def test_query_failure(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test query failure handling."""
        httpx_mock.add_response(
            url="http://prometheus.test:9090/api/v1/query?query=invalid%7B",
            json={
                "status": "error",
                "error": "parse error",
                "errorType": "bad_data"
            }
        )

        with pytest.raises(OverwatchError) as exc_info:
            await prometheus_query(
                client=prometheus_client,
                config=prometheus_config,
                cache=cache,
                query="invalid{",
            )

        assert exc_info.value.code == ErrorCode.UPSTREAM_CLIENT_ERROR


class TestPrometheusQueryRange:
    """Tests for prometheus_query_range tool."""

    async def test_query_range_basic(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test basic range query."""
        httpx_mock.add_response(
            url="http://prometheus.test:9090/api/v1/query_range?query=up&start=1706356800.0&end=1706360400.0&step=15s",
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {"__name__": "up", "job": "prometheus"},
                            "values": [
                                [1706356800, "1"],
                                [1706356815, "1"]
                            ]
                        }
                    ]
                }
            }
        )

        result = await prometheus_query_range(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            query="up",
            start="1706356800",
            end="1706360400",
            step="15s",
        )

        assert result["resultType"] == "matrix"
        assert len(result["result"]) == 1
        assert len(result["result"][0]["values"]) == 2

    async def test_query_range_auto_step(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test range query with auto-calculated step."""
        # Mock response - step will be auto-calculated
        httpx_mock.add_response(
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": []
                }
            }
        )

        result = await prometheus_query_range(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            query="up",
            start="1706356800",
            end="1706360400",
            # step not provided - will be auto-calculated
        )

        assert result["resultType"] == "matrix"

    async def test_query_range_caching(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test that completed time ranges are cached."""
        # Match any query_range request with these specific params
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r"http://prometheus\.test:9090/api/v1/query_range.*"),
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": []
                }
            }
        )

        # First call - should hit API
        result1 = await prometheus_query_range(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            query="up",
            start="1706356800",
            end="1706360400",
            step="15s",
        )

        # Second call - should use cache
        result2 = await prometheus_query_range(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            query="up",
            start="1706356800",
            end="1706360400",
            step="15s",
        )

        assert result1 == result2
        # Should only have made one HTTP request
        assert len(httpx_mock.get_requests()) == 1

    async def test_query_range_relative_not_cached(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test that relative time ranges are not cached."""
        # Match any query_range request with relative times (reusable for multiple calls)
        httpx_mock.add_response(
            method="GET",
            url=re.compile(r"http://prometheus\.test:9090/api/v1/query_range.*"),
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": []
                }
            },
            is_reusable=True,
        )

        # First call with relative times
        await prometheus_query_range(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            query="up",
            start="-1h",
            end="now",
            step="15s",
        )

        # Second call - should hit API again (not cached)
        await prometheus_query_range(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            query="up",
            start="-1h",
            end="now",
            step="15s",
        )

        # Should have made two HTTP requests
        assert len(httpx_mock.get_requests()) == 2

    async def test_query_range_exceeded(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
    ):
        """Test that time range validation rejects ranges exceeding max."""
        with pytest.raises(OverwatchError) as exc_info:
            await prometheus_query_range(
                client=prometheus_client,
                config=prometheus_config,
                cache=cache,
                query="up",
                start="-200h",  # Exceeds 168h (7 days) max
                end="now",
            )

        assert exc_info.value.code == ErrorCode.TIME_RANGE_EXCEEDED
        assert "200" in exc_info.value.message

    async def test_query_range_invalid_start(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
    ):
        """Test that invalid start time raises error."""
        with pytest.raises(OverwatchError) as exc_info:
            await prometheus_query_range(
                client=prometheus_client,
                config=prometheus_config,
                cache=cache,
                query="up",
                start="invalid-time",
                end="now",
            )

        assert exc_info.value.code == ErrorCode.INVALID_QUERY

    async def test_query_range_start_after_end(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
    ):
        """Test that start after end raises error."""
        with pytest.raises(OverwatchError) as exc_info:
            await prometheus_query_range(
                client=prometheus_client,
                config=prometheus_config,
                cache=cache,
                query="up",
                start="1706360400",
                end="1706356800",
            )

        assert exc_info.value.code == ErrorCode.INVALID_QUERY
        assert "before" in exc_info.value.message


class TestPrometheusMetrics:
    """Tests for prometheus_metrics tool."""

    async def test_metrics_no_filter(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test listing all metrics without filter."""
        httpx_mock.add_response(
            url="http://prometheus.test:9090/api/v1/label/__name__/values",
            json={
                "status": "success",
                "data": [
                    "http_requests_total",
                    "http_request_duration_seconds",
                    "up",
                    "process_cpu_seconds_total"
                ]
            }
        )

        result = await prometheus_metrics(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
        )

        assert result["count"] == 4
        assert result["total_available"] == 4
        assert result["truncated"] is False
        assert result["pattern"] is None
        assert result["cached"] is False  # First call
        assert len(result["metrics"]) == 4

        # Verify metrics are sorted
        assert result["metrics"] == sorted(result["metrics"])

    async def test_metrics_with_pattern(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test filtering metrics by pattern."""
        httpx_mock.add_response(
            url="http://prometheus.test:9090/api/v1/label/__name__/values",
            json={
                "status": "success",
                "data": [
                    "http_requests_total",
                    "http_request_duration_seconds",
                    "up",
                    "process_cpu_seconds_total"
                ]
            }
        )

        result = await prometheus_metrics(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            pattern="http_.*",
        )

        assert result["count"] == 2
        assert result["total_available"] == 2
        assert result["pattern"] == "http_.*"

        metric_names = result["metrics"]
        assert "http_requests_total" in metric_names
        assert "http_request_duration_seconds" in metric_names
        assert "up" not in metric_names

    async def test_metrics_case_insensitive_pattern(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test that pattern matching is case-insensitive."""
        httpx_mock.add_response(
            url="http://prometheus.test:9090/api/v1/label/__name__/values",
            json={
                "status": "success",
                "data": [
                    "HTTP_Requests_Total",
                    "http_request_duration",
                    "UP"
                ]
            }
        )

        result = await prometheus_metrics(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            pattern="http",
        )

        assert result["count"] == 2
        metric_names = result["metrics"]
        assert "HTTP_Requests_Total" in metric_names
        assert "http_request_duration" in metric_names

    async def test_metrics_with_limit(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test limiting number of returned metrics."""
        metrics_data = [f"metric_{i}" for i in range(50)]
        httpx_mock.add_response(
            url="http://prometheus.test:9090/api/v1/label/__name__/values",
            json={
                "status": "success",
                "data": metrics_data
            }
        )

        result = await prometheus_metrics(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            limit=10,
        )

        assert result["count"] == 10
        assert result["total_available"] == 50
        assert result["truncated"] is True

    async def test_metrics_limit_clamping(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test that limit is clamped to 500."""
        metrics_data = [f"metric_{i}" for i in range(600)]
        httpx_mock.add_response(
            url="http://prometheus.test:9090/api/v1/label/__name__/values",
            json={
                "status": "success",
                "data": metrics_data
            }
        )

        result = await prometheus_metrics(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
            limit=1000,  # Request more than max
        )

        assert result["count"] == 500  # Clamped to max
        assert result["total_available"] == 600
        assert result["truncated"] is True

    async def test_metrics_caching(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test that metric list is cached."""
        httpx_mock.add_response(
            url="http://prometheus.test:9090/api/v1/label/__name__/values",
            json={
                "status": "success",
                "data": ["metric1", "metric2"]
            }
        )

        # First call - should hit API
        result1 = await prometheus_metrics(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
        )
        assert result1["cached"] is False

        # Second call - should use cache
        result2 = await prometheus_metrics(
            client=prometheus_client,
            config=prometheus_config,
            cache=cache,
        )
        assert result2["cached"] is True

        # Should only have made one HTTP request
        assert len(httpx_mock.get_requests()) == 1

    async def test_metrics_invalid_pattern(
        self,
        prometheus_client: PrometheusClient,
        prometheus_config: PrometheusConfig,
        cache: Cache,
    ):
        """Test that invalid regex pattern raises error."""
        with pytest.raises(OverwatchError) as exc_info:
            await prometheus_metrics(
                client=prometheus_client,
                config=prometheus_config,
                cache=cache,
                pattern="[invalid",  # Invalid regex
            )

        assert exc_info.value.code == ErrorCode.INVALID_PATTERN
        assert "Invalid regex pattern" in exc_info.value.message
