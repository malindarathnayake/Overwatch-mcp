"""Tests for configuration models."""

import pytest
from pydantic import ValidationError

from overwatch_mcp.models.config import (
    CacheConfig,
    Config,
    DatasourcesConfig,
    GraylogConfig,
    InfluxDBConfig,
    PrometheusConfig,
    ServerConfig,
)


class TestServerConfig:
    """Tests for ServerConfig model."""

    def test_valid_server_config(self):
        """Test valid server configuration."""
        config = ServerConfig(
            name="test-server",
            version="1.0.0",
            log_level="info"
        )
        assert config.name == "test-server"
        assert config.version == "1.0.0"
        assert config.log_level == "info"

    def test_invalid_log_level(self):
        """Test that invalid log level raises error."""
        with pytest.raises(ValidationError):
            ServerConfig(
                name="test",
                version="1.0.0",
                log_level="invalid"  # type: ignore
            )

    def test_defaults(self):
        """Test default values."""
        config = ServerConfig()
        assert config.name == "overwatch-mcp-server"
        assert config.log_level == "info"


class TestGraylogConfig:
    """Tests for GraylogConfig model."""

    def test_valid_graylog_config(self):
        """Test valid Graylog configuration."""
        config = GraylogConfig(
            url="https://graylog.test:9000/api",
            token="test-token"
        )
        assert config.enabled is True
        assert config.url == "https://graylog.test:9000/api"
        assert config.token == "test-token"
        assert config.timeout_seconds == 30
        assert config.max_time_range_hours == 24

    def test_missing_required_fields(self):
        """Test that missing required fields raise error."""
        with pytest.raises(ValidationError):
            GraylogConfig()  # type: ignore

    def test_default_exceeds_max_time_range(self):
        """Test that default_time_range cannot exceed max."""
        with pytest.raises(ValidationError):
            GraylogConfig(
                url="https://test",
                token="token",
                max_time_range_hours=10,
                default_time_range_hours=20  # Invalid
            )

    def test_default_exceeds_max_results(self):
        """Test that default_results cannot exceed max."""
        with pytest.raises(ValidationError):
            GraylogConfig(
                url="https://test",
                token="token",
                max_results=100,
                default_results=200  # Invalid
            )

    def test_invalid_timeout(self):
        """Test that invalid timeout raises error."""
        with pytest.raises(ValidationError):
            GraylogConfig(
                url="https://test",
                token="token",
                timeout_seconds=0  # Must be >= 1
            )


class TestPrometheusConfig:
    """Tests for PrometheusConfig model."""

    def test_valid_prometheus_config(self):
        """Test valid Prometheus configuration."""
        config = PrometheusConfig(
            url="http://prometheus.test:9090"
        )
        assert config.enabled is True
        assert config.url == "http://prometheus.test:9090"
        assert config.max_range_hours == 168

    def test_missing_required_fields(self):
        """Test that missing URL raises error."""
        with pytest.raises(ValidationError):
            PrometheusConfig()  # type: ignore


class TestInfluxDBConfig:
    """Tests for InfluxDBConfig model."""

    def test_valid_influxdb_config(self):
        """Test valid InfluxDB configuration."""
        config = InfluxDBConfig(
            url="https://influxdb.test:8086",
            token="test-token",
            org="test-org"
        )
        assert config.enabled is True
        assert config.url == "https://influxdb.test:8086"
        assert config.token == "test-token"
        assert config.org == "test-org"
        assert "telegraf" in config.allowed_buckets

    def test_custom_allowed_buckets(self):
        """Test custom allowed buckets list."""
        config = InfluxDBConfig(
            url="https://test",
            token="token",
            org="org",
            allowed_buckets=["custom1", "custom2"]
        )
        assert config.allowed_buckets == ["custom1", "custom2"]

    def test_missing_required_fields(self):
        """Test that missing required fields raise error."""
        with pytest.raises(ValidationError):
            InfluxDBConfig(url="https://test")  # type: ignore


class TestDatasourcesConfig:
    """Tests for DatasourcesConfig model."""

    def test_get_enabled_datasources_all(self):
        """Test getting all enabled datasources."""
        config = DatasourcesConfig(
            graylog=GraylogConfig(url="https://test", token="token"),
            prometheus=PrometheusConfig(url="http://test"),
            influxdb=InfluxDBConfig(url="https://test", token="token", org="org")
        )
        enabled = config.get_enabled_datasources()
        assert enabled == ["graylog", "prometheus", "influxdb"]

    def test_get_enabled_datasources_partial(self):
        """Test getting partially enabled datasources."""
        config = DatasourcesConfig(
            graylog=GraylogConfig(url="https://test", token="token", enabled=False),
            prometheus=PrometheusConfig(url="http://test", enabled=True)
        )
        enabled = config.get_enabled_datasources()
        assert enabled == ["prometheus"]

    def test_get_enabled_datasources_none(self):
        """Test when no datasources are configured."""
        config = DatasourcesConfig()
        enabled = config.get_enabled_datasources()
        assert enabled == []


class TestCacheConfig:
    """Tests for CacheConfig model."""

    def test_valid_cache_config(self):
        """Test valid cache configuration."""
        config = CacheConfig(
            enabled=True,
            default_ttl_seconds=120
        )
        assert config.enabled is True
        assert config.default_ttl_seconds == 120
        assert "prometheus_metrics" in config.ttl_overrides

    def test_defaults(self):
        """Test default cache configuration."""
        config = CacheConfig()
        assert config.enabled is True
        assert config.default_ttl_seconds == 60
        assert config.ttl_overrides["prometheus_metrics"] == 300


class TestConfig:
    """Tests for root Config model."""

    def test_valid_config(self, sample_config_dict: dict):
        """Test valid complete configuration."""
        config = Config(**sample_config_dict)
        assert config.server.name == "overwatch-mcp-server"
        assert config.datasources.graylog is not None
        assert config.cache.enabled is True

    def test_minimal_config(self, minimal_config_dict: dict):
        """Test minimal valid configuration."""
        config = Config(**minimal_config_dict)
        assert config.server.name == "test-server"
        assert config.datasources.graylog is not None
        assert config.cache.enabled is True  # Default

    def test_no_enabled_datasources_fails(self):
        """Test that config with no enabled datasources fails."""
        with pytest.raises(ValidationError):
            Config(
                server=ServerConfig(),
                datasources=DatasourcesConfig()
            )

    def test_all_datasources_disabled_fails(self):
        """Test that all disabled datasources fails validation."""
        with pytest.raises(ValidationError):
            Config(
                server=ServerConfig(),
                datasources=DatasourcesConfig(
                    graylog=GraylogConfig(
                        url="https://test",
                        token="token",
                        enabled=False
                    )
                )
            )
