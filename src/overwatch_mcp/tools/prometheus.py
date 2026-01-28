"""Prometheus MCP tools."""

import re
from datetime import datetime, timedelta
from typing import Any

from overwatch_mcp.cache import Cache
from overwatch_mcp.clients.prometheus import PrometheusClient
from overwatch_mcp.models.config import PrometheusConfig
from overwatch_mcp.models.errors import ErrorCode, OverwatchError


def _parse_relative_time(time_str: str) -> datetime | None:
    """
    Parse relative time string to datetime.

    Args:
        time_str: Relative time string like '-1h', '-30m', 'now'

    Returns:
        datetime object or None if not relative
    """
    if time_str == "now":
        return datetime.now()

    # Match pattern like '-1h', '-30m', '-2d'
    match = re.match(r'^-(\d+)([mhd])$', time_str)
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    now = datetime.now()
    if unit == 'm':
        return now - timedelta(minutes=value)
    elif unit == 'h':
        return now - timedelta(hours=value)
    elif unit == 'd':
        return now - timedelta(days=value)

    return None


def _validate_time_range(
    start: str,
    end: str,
    max_hours: int
) -> tuple[datetime, datetime]:
    """
    Validate and parse time range for range queries.

    Args:
        start: Start time (ISO8601, Unix, or relative)
        end: End time (ISO8601, Unix, or relative)
        max_hours: Maximum allowed time range in hours

    Returns:
        Tuple of (start_dt, end_dt)

    Raises:
        OverwatchError: If time range is invalid or exceeds max
    """
    # Parse start time
    start_dt = _parse_relative_time(start)
    if start_dt is None:
        try:
            # Try Unix timestamp
            start_dt = datetime.fromtimestamp(float(start))
        except (ValueError, TypeError):
            try:
                # Try ISO8601
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            except ValueError as e:
                raise OverwatchError(
                    code=ErrorCode.INVALID_QUERY,
                    message=f"Invalid start time format: {start}",
                    details={"error": str(e)}
                )

    # Parse end time
    end_dt = _parse_relative_time(end)
    if end_dt is None:
        try:
            # Try Unix timestamp
            end_dt = datetime.fromtimestamp(float(end))
        except (ValueError, TypeError):
            try:
                # Try ISO8601
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            except ValueError as e:
                raise OverwatchError(
                    code=ErrorCode.INVALID_QUERY,
                    message=f"Invalid end time format: {end}",
                    details={"error": str(e)}
                )

    # Validate start < end
    if start_dt >= end_dt:
        raise OverwatchError(
            code=ErrorCode.INVALID_QUERY,
            message="start time must be before end time",
            details={"start": start, "end": end}
        )

    # Check time range
    time_range_hours = (end_dt - start_dt).total_seconds() / 3600
    if time_range_hours > max_hours:
        raise OverwatchError(
            code=ErrorCode.TIME_RANGE_EXCEEDED,
            message=f"Requested time range ({time_range_hours:.1f}h) exceeds maximum allowed ({max_hours}h)",
            details={
                "requested_hours": time_range_hours,
                "max_hours": max_hours
            }
        )

    return start_dt, end_dt


async def prometheus_query(
    client: PrometheusClient,
    config: PrometheusConfig,
    cache: Cache,
    query: str,
    time: str | None = None,
) -> dict[str, Any]:
    """
    Execute instant PromQL query.

    Args:
        client: Prometheus client instance
        config: Prometheus configuration
        cache: Cache instance (not used for instant queries - always live data)
        query: PromQL expression
        time: Evaluation time (ISO8601, Unix timestamp, or relative). Default: now

    Returns:
        Query result dictionary with structure:
        {
            "result_type": "vector" | "scalar" | "matrix" | "string",
            "result": [...]
        }

    Raises:
        OverwatchError: On validation or API errors
    """
    # Execute query
    result = await client.query(query=query, time=time)

    return result


async def prometheus_query_range(
    client: PrometheusClient,
    config: PrometheusConfig,
    cache: Cache,
    query: str,
    start: str,
    end: str,
    step: str | None = None,
) -> dict[str, Any]:
    """
    Execute PromQL range query.

    Args:
        client: Prometheus client instance
        config: Prometheus configuration
        cache: Cache instance for caching completed range queries
        query: PromQL expression
        start: Start time (ISO8601, Unix, or relative: '-1h')
        end: End time (ISO8601, Unix, or relative: 'now')
        step: Query resolution (e.g., '15s', '1m', '1h'). Default: auto-calculated

    Returns:
        Range query result dictionary with structure:
        {
            "result_type": "matrix",
            "result": [...]
        }

    Raises:
        OverwatchError: On validation or API errors
    """
    # Validate time range
    start_dt, end_dt = _validate_time_range(start, end, config.max_range_hours)

    # Check cache for completed ranges (only cache if both times are not relative)
    cache_key = None
    if not (start.startswith("-") or start == "now") and not (end.startswith("-") or end == "now"):
        # This is a completed time range, can be cached
        cache_key = f"prom_range:{query}:{start}:{end}:{step}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

    # Execute range query
    result = await client.query_range(
        query=query,
        start=start,
        end=end,
        step=step,
    )

    # Cache completed ranges
    if cache_key:
        cache.set(cache_key, result)

    return result


async def prometheus_metrics(
    client: PrometheusClient,
    config: PrometheusConfig,
    cache: Cache,
    pattern: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """
    List available metric names, optionally filtered by pattern.

    Args:
        client: Prometheus client instance
        config: Prometheus configuration
        cache: Cache instance for metric list caching
        pattern: Regex pattern to filter metric names (e.g., 'http_.*', 'cpu'). Default: none
        limit: Max metrics to return. Default: 100, Max: 500

    Returns:
        Metrics list dictionary with structure:
        {
            "metrics": [str, ...],
            "count": int,
            "total_available": int,
            "pattern": str | None,
            "truncated": bool,
            "cached": bool
        }

    Raises:
        OverwatchError: On API errors or invalid pattern
    """
    # Compile regex pattern if provided
    compiled_pattern = None
    if pattern:
        try:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise OverwatchError(
                code=ErrorCode.INVALID_PATTERN,
                message=f"Invalid regex pattern: {pattern}",
                details={"error": str(e)}
            )

    # Clamp limit
    limit = min(limit, 500)

    # Try to get from cache
    cache_key = "prometheus_metrics"
    cached_data = cache.get(cache_key)
    was_cached = cached_data is not None

    if cached_data is None:
        # Fetch from API
        cached_data = await client.get_metrics()

        # Cache the raw metric list
        cache.set(cache_key, cached_data)

    # Apply pattern filter if provided
    all_metrics = list(cached_data)
    if compiled_pattern:
        all_metrics = [
            metric for metric in all_metrics
            if compiled_pattern.search(metric)
        ]

    # Sort alphabetically
    all_metrics.sort()

    # Apply limit
    total_available = len(all_metrics)
    truncated_metrics = all_metrics[:limit]

    response = {
        "metrics": truncated_metrics,
        "count": len(truncated_metrics),
        "total_available": total_available,
        "pattern": pattern,
        "truncated": total_available > len(truncated_metrics),
        "cached": was_cached,
    }

    return response
