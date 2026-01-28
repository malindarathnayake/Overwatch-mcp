"""Tests for InfluxDB client."""

import pytest
from pytest_httpx import HTTPXMock

from overwatch_mcp.clients.influxdb import InfluxDBClient
from overwatch_mcp.models.config import InfluxDBConfig
from overwatch_mcp.models.errors import ErrorCode, OverwatchError


@pytest.fixture
def influxdb_config() -> InfluxDBConfig:
    """InfluxDB test configuration."""
    return InfluxDBConfig(
        url="https://influxdb.test:8086",
        token="test-token-456",
        org="test-org",
        timeout_seconds=60,
        allowed_buckets=["telegraf", "app_metrics", "system_metrics"],
    )


@pytest.fixture
def influxdb_client(influxdb_config: InfluxDBConfig) -> InfluxDBClient:
    """InfluxDB client fixture."""
    return InfluxDBClient(influxdb_config)


class TestInfluxDBClient:
    """Tests for InfluxDBClient class."""

    async def test_client_initialization(self, influxdb_client: InfluxDBClient):
        """Test client initializes with correct config."""
        assert influxdb_client.base_url == "https://influxdb.test:8086"
        assert influxdb_client.timeout_seconds == 60
        assert "Authorization" in influxdb_client.default_headers
        assert influxdb_client.default_headers["Authorization"] == "Token test-token-456"

    def test_validate_bucket_allowed(self, influxdb_client: InfluxDBClient):
        """Test bucket validation for allowed bucket."""
        # Should not raise
        influxdb_client._validate_bucket("telegraf")
        influxdb_client._validate_bucket("app_metrics")

    def test_validate_bucket_not_allowed(self, influxdb_client: InfluxDBClient):
        """Test bucket validation for not allowed bucket."""
        with pytest.raises(OverwatchError) as exc_info:
            influxdb_client._validate_bucket("forbidden_bucket")

        assert exc_info.value.code == ErrorCode.BUCKET_NOT_ALLOWED
        assert "forbidden_bucket" in exc_info.value.message
        assert "telegraf" in str(exc_info.value.details)

    def test_validate_query_bucket_valid(self, influxdb_client: InfluxDBClient):
        """Test query bucket validation for valid query."""
        query = 'from(bucket: "telegraf") |> range(start: -1h)'
        # Should not raise
        influxdb_client._validate_query_bucket(query, "telegraf")

    def test_validate_query_bucket_invalid(self, influxdb_client: InfluxDBClient):
        """Test query bucket validation for invalid query."""
        query = 'from(bucket: "other_bucket") |> range(start: -1h)'

        with pytest.raises(OverwatchError) as exc_info:
            influxdb_client._validate_query_bucket(query, "telegraf")

        assert exc_info.value.code == ErrorCode.INVALID_QUERY
        assert "must reference bucket" in exc_info.value.message.lower()

    def test_parse_csv_response_simple(self, influxdb_client: InfluxDBClient):
        """Test parsing simple CSV response."""
        csv_text = """#group,false,false,true,true,false,false,true,true
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,string,string
#default,_result,,,,,,,
,result,table,_start,_stop,_time,_value,_field,host
,,0,2025-01-27T10:00:00Z,2025-01-27T11:00:00Z,2025-01-27T10:30:00Z,45.2,cpu_usage,server-01
,,0,2025-01-27T10:00:00Z,2025-01-27T11:00:00Z,2025-01-27T10:31:00Z,46.8,cpu_usage,server-01
"""
        records = influxdb_client._parse_csv_response(csv_text)

        assert len(records) == 2
        assert records[0]["_value"] == "45.2"
        assert records[0]["_field"] == "cpu_usage"
        assert records[0]["host"] == "server-01"
        assert records[1]["_value"] == "46.8"

    def test_parse_csv_response_empty(self, influxdb_client: InfluxDBClient):
        """Test parsing empty CSV response."""
        csv_text = """#group,false,false,true
#datatype,string,long,dateTime:RFC3339
#default,_result,,
,result,table,_start
"""
        records = influxdb_client._parse_csv_response(csv_text)
        assert len(records) == 0

    def test_parse_csv_response_invalid(self, influxdb_client: InfluxDBClient):
        """Test parsing invalid CSV raises error."""
        csv_text = "not,valid,csv\nwithout,proper,annotations"

        with pytest.raises(OverwatchError) as exc_info:
            influxdb_client._parse_csv_response(csv_text)

        assert exc_info.value.code == ErrorCode.UPSTREAM_CLIENT_ERROR
        assert "parse" in exc_info.value.message.lower()

    async def test_query_success(
        self, influxdb_client: InfluxDBClient, httpx_mock: HTTPXMock
    ):
        """Test successful query."""
        query = 'from(bucket: "telegraf") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "cpu")'
        csv_response = """#group,false,false,true,true,false,false,true,true
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,string,string
#default,_result,,,,,,,
,result,table,_start,_stop,_time,_value,_field,host
,,0,2025-01-27T10:00:00Z,2025-01-27T11:00:00Z,2025-01-27T10:30:00Z,45.2,cpu_usage,server-01
"""

        httpx_mock.add_response(
            url="https://influxdb.test:8086/api/v2/query?org=test-org",
            text=csv_response,
            status_code=200,
        )

        async with influxdb_client:
            records = await influxdb_client.query(query, "telegraf")

        assert len(records) == 1
        assert records[0]["_value"] == "45.2"

    async def test_query_bucket_not_allowed(
        self, influxdb_client: InfluxDBClient, httpx_mock: HTTPXMock
    ):
        """Test query with bucket not in allowlist."""
        query = 'from(bucket: "forbidden") |> range(start: -1h)'

        async with influxdb_client:
            with pytest.raises(OverwatchError) as exc_info:
                await influxdb_client.query(query, "forbidden")

        assert exc_info.value.code == ErrorCode.BUCKET_NOT_ALLOWED

    async def test_query_bucket_mismatch(
        self, influxdb_client: InfluxDBClient, httpx_mock: HTTPXMock
    ):
        """Test query with bucket mismatch."""
        query = 'from(bucket: "app_metrics") |> range(start: -1h)'

        async with influxdb_client:
            with pytest.raises(OverwatchError) as exc_info:
                await influxdb_client.query(query, "telegraf")  # Mismatch

        assert exc_info.value.code == ErrorCode.INVALID_QUERY

    async def test_query_error_response(
        self, influxdb_client: InfluxDBClient, httpx_mock: HTTPXMock
    ):
        """Test query with error response."""
        query = 'from(bucket: "telegraf") |> range(start: -1h)'

        httpx_mock.add_response(
            url="https://influxdb.test:8086/api/v2/query?org=test-org",
            text="Error: invalid query",
            status_code=400,
        )

        async with influxdb_client:
            with pytest.raises(OverwatchError) as exc_info:
                await influxdb_client.query(query, "telegraf")

        assert exc_info.value.code == ErrorCode.UPSTREAM_CLIENT_ERROR
        assert "400" in str(exc_info.value.details)

    async def test_health_check_success(
        self, influxdb_client: InfluxDBClient, httpx_mock: HTTPXMock
    ):
        """Test health check when service is healthy."""
        httpx_mock.add_response(status_code=200)

        async with influxdb_client:
            result = await influxdb_client.health_check()

        assert result is True

    async def test_health_check_failure(
        self, influxdb_client: InfluxDBClient, httpx_mock: HTTPXMock
    ):
        """Test health check when service is down."""
        # Add multiple responses for retries (initial + 3 retries)
        for _ in range(4):
            httpx_mock.add_response(status_code=503)

        async with influxdb_client:
            result = await influxdb_client.health_check()

        assert result is False

    def test_parse_csv_with_multiple_tables(self, influxdb_client: InfluxDBClient):
        """Test parsing CSV with multiple result tables."""
        csv_text = """#group,false,false,true,true,false,false,true
#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,string
#default,_result,,,,,,
,result,table,_start,_stop,_time,_value,_field
,,0,2025-01-27T10:00:00Z,2025-01-27T11:00:00Z,2025-01-27T10:30:00Z,45.2,cpu_usage
,,1,2025-01-27T10:00:00Z,2025-01-27T11:00:00Z,2025-01-27T10:30:00Z,1024.5,memory_usage
"""
        records = influxdb_client._parse_csv_response(csv_text)

        assert len(records) == 2
        assert records[0]["table"] == "0"
        assert records[1]["table"] == "1"
        assert records[0]["_field"] == "cpu_usage"
        assert records[1]["_field"] == "memory_usage"
