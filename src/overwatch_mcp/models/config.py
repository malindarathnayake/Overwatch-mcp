"""Configuration models for datasources and server settings."""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ServerConfig(BaseModel):
    """Server-level configuration."""

    name: str = "overwatch-mcp-server"
    version: str = "1.0.0"
    log_level: Literal["debug", "info", "warning", "error"] = "info"


class GraylogConfig(BaseModel):
    """Graylog datasource configuration."""

    enabled: bool = True
    url: str = Field(..., description="Graylog API URL (e.g., https://graylog.internal:9000)")
    token: str = Field(..., description="Graylog API token")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")

    # Query safety limits
    max_time_range_hours: int = Field(default=24, ge=1)
    default_time_range_hours: int = Field(default=1, ge=1)
    max_results: int = Field(default=1000, ge=1, le=10000)
    default_results: int = Field(default=100, ge=1)

    @field_validator("default_time_range_hours")
    @classmethod
    def validate_default_range(cls, v: int, info) -> int:
        """Ensure default time range doesn't exceed max."""
        if "max_time_range_hours" in info.data and v > info.data["max_time_range_hours"]:
            raise ValueError("default_time_range_hours cannot exceed max_time_range_hours")
        return v

    @field_validator("default_results")
    @classmethod
    def validate_default_results(cls, v: int, info) -> int:
        """Ensure default results doesn't exceed max."""
        if "max_results" in info.data and v > info.data["max_results"]:
            raise ValueError("default_results cannot exceed max_results")
        return v


class PrometheusConfig(BaseModel):
    """Prometheus datasource configuration."""

    enabled: bool = True
    url: str = Field(..., description="Prometheus URL (e.g., http://prometheus.internal:9090)")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")

    # Query safety limits
    max_range_hours: int = Field(default=168, ge=1, description="Max 7 days for range queries")
    max_step_seconds: int = Field(default=3600, ge=1, description="Min granularity 1 hour")
    max_series: int = Field(default=10000, ge=1, description="Max series returned")
    max_metric_results: int = Field(default=500, ge=1, le=10000)


class InfluxDBConfig(BaseModel):
    """InfluxDB 2.x datasource configuration."""

    enabled: bool = True
    url: str = Field(..., description="InfluxDB URL (e.g., https://influxdb.internal:8086)")
    token: str = Field(..., description="InfluxDB API token")
    org: str = Field(..., description="InfluxDB organization")
    timeout_seconds: int = Field(default=60, ge=1, le=300)
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")

    # Bucket allowlist
    allowed_buckets: list[str] = Field(
        default_factory=lambda: ["telegraf", "app_metrics", "system_metrics"],
        description="Queries to unlisted buckets are rejected"
    )

    # Query safety
    max_time_range_hours: int = Field(default=168, ge=1, description="Max 7 days")


class DatasourcesConfig(BaseModel):
    """All datasource configurations."""

    graylog: GraylogConfig | None = None
    prometheus: PrometheusConfig | None = None
    influxdb: InfluxDBConfig | None = None

    def get_enabled_datasources(self) -> list[str]:
        """Return list of enabled datasource names."""
        enabled = []
        if self.graylog and self.graylog.enabled:
            enabled.append("graylog")
        if self.prometheus and self.prometheus.enabled:
            enabled.append("prometheus")
        if self.influxdb and self.influxdb.enabled:
            enabled.append("influxdb")
        return enabled


class CacheConfig(BaseModel):
    """Cache configuration."""

    enabled: bool = True
    default_ttl_seconds: int = Field(default=60, ge=0)

    # Per-tool TTL overrides
    ttl_overrides: dict[str, int] = Field(
        default_factory=lambda: {
            "prometheus_metrics": 300,
            "graylog_fields": 300,
        }
    )


class Config(BaseModel):
    """Root configuration model."""

    server: ServerConfig
    datasources: DatasourcesConfig
    cache: CacheConfig = Field(default_factory=CacheConfig)

    def model_post_init(self, __context) -> None:
        """Validate that at least one datasource is enabled."""
        enabled = self.datasources.get_enabled_datasources()
        if not enabled:
            raise ValueError("At least one datasource must be enabled")
