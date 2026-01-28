"""Integration tests for InfluxDB MCP tools."""

import pytest
from pytest_httpx import HTTPXMock

from overwatch_mcp.cache import Cache
from overwatch_mcp.clients.influxdb import InfluxDBClient
from overwatch_mcp.models.config import InfluxDBConfig
from overwatch_mcp.models.errors import ErrorCode, OverwatchError
from overwatch_mcp.tools.influxdb import influxdb_query


@pytest.fixture
def influxdb_config() -> InfluxDBConfig:
    """InfluxDB test configuration."""
    return InfluxDBConfig(
        url="https://influxdb.test:8086",
        token="test-token-123",
        org="test-org",
        timeout_seconds=60,
        allowed_buckets=["telegraf", "app_metrics", "system_metrics"],
        max_time_range_hours=168,
    )


@pytest.fixture
def influxdb_client(influxdb_config: InfluxDBConfig) -> InfluxDBClient:
    """InfluxDB client fixture."""
    return InfluxDBClient(influxdb_config)


@pytest.fixture
def cache() -> Cache:
    """Cache fixture."""
    return Cache(default_ttl=60)


class TestInfluxDBQuery:
    """Tests for influxdb_query tool."""

    async def test_query_basic(
        self,
        influxdb_client: InfluxDBClient,
        influxdb_config: InfluxDBConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test basic Flux query execution."""
        # Mock CSV response
        csv_response = """#group,false,false,true,true,false,false,true,true,true,true
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,string,string,string,string
#default,_result,,,,,,,,,
,result,table,_start,_stop,_time,_value,_field,_measurement,host,region
,,0,2025-01-27T10:00:00Z,2025-01-27T11:00:00Z,2025-01-27T10:30:00Z,45.2,cpu_usage,system,server-01,us-west
,,0,2025-01-27T10:00:00Z,2025-01-27T11:00:00Z,2025-01-27T10:31:00Z,47.5,cpu_usage,system,server-01,us-west
"""
        httpx_mock.add_response(
            method="POST",
            url="https://influxdb.test:8086/api/v2/query?org=test-org",
            content=csv_response.encode("utf-8"),
            headers={"Content-Type": "application/csv"},
        )

        result = await influxdb_query(
            client=influxdb_client,
            config=influxdb_config,
            cache=cache,
            query='from(bucket: "telegraf") |> range(start: -1h)',
            bucket="telegraf",
        )

        assert result["record_count"] == 2
        assert result["truncated"] is False
        assert len(result["tables"]) == 1
        assert result["tables"][0]["columns"] == ["result", "table", "_start", "_stop", "_time", "_value", "_field", "_measurement", "host", "region"]
        assert len(result["tables"][0]["records"]) == 2
        assert result["tables"][0]["records"][0]["_value"] == "45.2"
        assert result["tables"][0]["records"][0]["host"] == "server-01"

    async def test_query_empty_result(
        self,
        influxdb_client: InfluxDBClient,
        influxdb_config: InfluxDBConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test query with no results."""
        # Mock empty CSV response
        csv_response = """#group,false,false,true,true,false,false,true,true
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,string,string
#default,_result,,,,,,,
,result,table,_start,_stop,_time,_value,_field,_measurement
"""
        httpx_mock.add_response(
            method="POST",
            url="https://influxdb.test:8086/api/v2/query?org=test-org",
            content=csv_response.encode("utf-8"),
            headers={"Content-Type": "application/csv"},
        )

        result = await influxdb_query(
            client=influxdb_client,
            config=influxdb_config,
            cache=cache,
            query='from(bucket: "telegraf") |> range(start: -1h)',
            bucket="telegraf",
        )

        assert result["record_count"] == 0
        assert result["truncated"] is False
        assert len(result["tables"]) == 1
        assert len(result["tables"][0]["records"]) == 0

    async def test_query_bucket_not_allowed(
        self,
        influxdb_client: InfluxDBClient,
        influxdb_config: InfluxDBConfig,
        cache: Cache,
    ):
        """Test that querying non-allowed bucket raises error."""
        with pytest.raises(OverwatchError) as exc_info:
            await influxdb_query(
                client=influxdb_client,
                config=influxdb_config,
                cache=cache,
                query='from(bucket: "forbidden") |> range(start: -1h)',
                bucket="forbidden",
            )

        assert exc_info.value.code == ErrorCode.BUCKET_NOT_ALLOWED
        assert "forbidden" in exc_info.value.message
        assert "telegraf" in str(exc_info.value.details.get("allowed_buckets", []))

    async def test_query_bucket_mismatch(
        self,
        influxdb_client: InfluxDBClient,
        influxdb_config: InfluxDBConfig,
        cache: Cache,
    ):
        """Test that query must reference the specified bucket."""
        with pytest.raises(OverwatchError) as exc_info:
            await influxdb_query(
                client=influxdb_client,
                config=influxdb_config,
                cache=cache,
                query='from(bucket: "app_metrics") |> range(start: -1h)',
                bucket="telegraf",  # Different bucket than in query
            )

        assert exc_info.value.code == ErrorCode.INVALID_QUERY
        assert "must reference bucket" in exc_info.value.message

    async def test_query_api_error(
        self,
        influxdb_client: InfluxDBClient,
        influxdb_config: InfluxDBConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test handling of API errors."""
        httpx_mock.add_response(
            method="POST",
            url="https://influxdb.test:8086/api/v2/query?org=test-org",
            status_code=400,
            content=b'{"error": "invalid syntax"}',
        )

        with pytest.raises(OverwatchError) as exc_info:
            await influxdb_query(
                client=influxdb_client,
                config=influxdb_config,
                cache=cache,
                query='from(bucket: "telegraf") |> invalid syntax',
                bucket="telegraf",
            )

        assert exc_info.value.code == ErrorCode.UPSTREAM_CLIENT_ERROR

    async def test_query_with_multiple_fields(
        self,
        influxdb_client: InfluxDBClient,
        influxdb_config: InfluxDBConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test query returning multiple fields."""
        csv_response = """#group,false,false,true,true,false,false,true,true
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,string,string
#default,_result,,,,,,,
,result,table,_start,_stop,_time,_value,_field,_measurement
,,0,2025-01-27T10:00:00Z,2025-01-27T11:00:00Z,2025-01-27T10:30:00Z,45.2,cpu_usage,system
,,0,2025-01-27T10:00:00Z,2025-01-27T11:00:00Z,2025-01-27T10:30:00Z,1024.5,memory_usage,system
"""
        httpx_mock.add_response(
            method="POST",
            url="https://influxdb.test:8086/api/v2/query?org=test-org",
            content=csv_response.encode("utf-8"),
            headers={"Content-Type": "application/csv"},
        )

        result = await influxdb_query(
            client=influxdb_client,
            config=influxdb_config,
            cache=cache,
            query='from(bucket: "app_metrics") |> range(start: -1h)',
            bucket="app_metrics",
        )

        assert result["record_count"] == 2
        assert len(result["tables"][0]["records"]) == 2
        # Verify different fields
        assert result["tables"][0]["records"][0]["_field"] == "cpu_usage"
        assert result["tables"][0]["records"][1]["_field"] == "memory_usage"

    async def test_query_allowed_buckets(
        self,
        influxdb_client: InfluxDBClient,
        influxdb_config: InfluxDBConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test that all allowed buckets can be queried."""
        csv_response = """#group,false,false,true,true,false,false,true,true
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,string,string
#default,_result,,,,,,,
,result,table,_start,_stop,_time,_value,_field,_measurement
,,0,2025-01-27T10:00:00Z,2025-01-27T11:00:00Z,2025-01-27T10:30:00Z,100.0,test_metric,test
"""
        # Test each allowed bucket
        for bucket in influxdb_config.allowed_buckets:
            httpx_mock.add_response(
                method="POST",
                url=f"https://influxdb.test:8086/api/v2/query?org=test-org",
                content=csv_response.encode("utf-8"),
                headers={"Content-Type": "application/csv"},
            )

            result = await influxdb_query(
                client=influxdb_client,
                config=influxdb_config,
                cache=cache,
                query=f'from(bucket: "{bucket}") |> range(start: -1h)',
                bucket=bucket,
            )

            assert result["record_count"] == 1

    async def test_query_not_cached(
        self,
        influxdb_client: InfluxDBClient,
        influxdb_config: InfluxDBConfig,
        cache: Cache,
        httpx_mock: HTTPXMock,
    ):
        """Test that InfluxDB queries are not cached."""
        csv_response = """#group,false,false,true,true,false,false,true,true
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,string,string
#default,_result,,,,,,,
,result,table,_start,_stop,_time,_value,_field,_measurement
,,0,2025-01-27T10:00:00Z,2025-01-27T11:00:00Z,2025-01-27T10:30:00Z,45.2,cpu_usage,system
"""
        # Add two mock responses since query should hit API twice
        for _ in range(2):
            httpx_mock.add_response(
                method="POST",
                url="https://influxdb.test:8086/api/v2/query?org=test-org",
                content=csv_response.encode("utf-8"),
                headers={"Content-Type": "application/csv"},
            )

        # First call
        result1 = await influxdb_query(
            client=influxdb_client,
            config=influxdb_config,
            cache=cache,
            query='from(bucket: "telegraf") |> range(start: -1h)',
            bucket="telegraf",
        )

        # Second call - should hit API again (not cached)
        result2 = await influxdb_query(
            client=influxdb_client,
            config=influxdb_config,
            cache=cache,
            query='from(bucket: "telegraf") |> range(start: -1h)',
            bucket="telegraf",
        )

        assert result1 == result2
        # Should have made two HTTP requests
        assert len(httpx_mock.get_requests()) == 2
