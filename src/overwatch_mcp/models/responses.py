"""Response schemas for MCP tools."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# Graylog responses

class TimeRange(BaseModel):
    """Time range for queries."""

    from_time: datetime = Field(..., alias="from")
    to: datetime


class GraylogMessage(BaseModel):
    """Single Graylog log message."""

    timestamp: datetime
    source: str
    level: str | None = None
    message: str
    fields: dict[str, Any] = Field(default_factory=dict)


class GraylogSearchResponse(BaseModel):
    """Response from graylog_search tool."""

    total_results: int
    returned: int
    truncated: bool
    query: str
    time_range: TimeRange
    messages: list[GraylogMessage]


class GraylogField(BaseModel):
    """Field metadata from Graylog."""

    name: str
    type: str


class GraylogFieldsResponse(BaseModel):
    """Response from graylog_fields tool."""

    fields: list[GraylogField]
    count: int
    total_available: int
    pattern: str | None = None
    truncated: bool
    cached: bool


# Prometheus responses

class MetricValue(BaseModel):
    """Single metric value with timestamp."""

    timestamp: datetime
    value: str


class PrometheusMetric(BaseModel):
    """Prometheus metric labels."""

    __root__: dict[str, str]


class PrometheusVectorResult(BaseModel):
    """Single result from instant query."""

    metric: dict[str, str]
    value: MetricValue


class PrometheusMatrixValue(BaseModel):
    """Time-series values."""

    timestamp: datetime
    value: str


class PrometheusMatrixResult(BaseModel):
    """Single result from range query."""

    metric: dict[str, str]
    values: list[PrometheusMatrixValue]


class PrometheusQueryResponse(BaseModel):
    """Response from prometheus_query tool."""

    result_type: str
    result: list[PrometheusVectorResult]


class PrometheusQueryRangeResponse(BaseModel):
    """Response from prometheus_query_range tool."""

    result_type: str
    result: list[PrometheusMatrixResult]


class PrometheusMetricsResponse(BaseModel):
    """Response from prometheus_metrics tool."""

    metrics: list[str]
    count: int
    total_available: int
    pattern: str | None = None
    truncated: bool
    cached: bool


# InfluxDB responses

class InfluxDBTable(BaseModel):
    """Single table from InfluxDB result."""

    columns: list[str]
    records: list[dict[str, Any]]


class InfluxDBQueryResponse(BaseModel):
    """Response from influxdb_query tool."""

    tables: list[InfluxDBTable]
    record_count: int
    truncated: bool
