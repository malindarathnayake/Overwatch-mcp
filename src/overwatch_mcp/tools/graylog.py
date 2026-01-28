"""Graylog MCP tools."""

import re
from datetime import datetime, timedelta
from typing import Any

from overwatch_mcp.cache import TTLCache
from overwatch_mcp.clients.graylog import GraylogClient
from overwatch_mcp.models.config import GraylogConfig
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
    from_time: str,
    to_time: str,
    max_hours: int
) -> tuple[datetime, datetime]:
    """
    Validate and parse time range.

    Args:
        from_time: Start time (ISO8601 or relative)
        to_time: End time (ISO8601 or relative)
        max_hours: Maximum allowed time range in hours

    Returns:
        Tuple of (from_dt, to_dt)

    Raises:
        OverwatchError: If time range is invalid or exceeds max
    """
    # Parse from_time
    from_dt = _parse_relative_time(from_time)
    if from_dt is None:
        try:
            from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
        except ValueError as e:
            raise OverwatchError(
                code=ErrorCode.INVALID_QUERY,
                message=f"Invalid from_time format: {from_time}",
                details={"error": str(e)}
            )

    # Parse to_time
    to_dt = _parse_relative_time(to_time)
    if to_dt is None:
        try:
            to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
        except ValueError as e:
            raise OverwatchError(
                code=ErrorCode.INVALID_QUERY,
                message=f"Invalid to_time format: {to_time}",
                details={"error": str(e)}
            )

    # Validate from < to
    if from_dt >= to_dt:
        raise OverwatchError(
            code=ErrorCode.INVALID_QUERY,
            message="from_time must be before to_time",
            details={"from_time": from_time, "to_time": to_time}
        )

    # Check time range
    time_range_hours = (to_dt - from_dt).total_seconds() / 3600
    if time_range_hours > max_hours:
        raise OverwatchError(
            code=ErrorCode.TIME_RANGE_EXCEEDED,
            message=f"Requested time range ({time_range_hours:.1f}h) exceeds maximum allowed ({max_hours}h)",
            details={
                "requested_hours": time_range_hours,
                "max_hours": max_hours
            }
        )

    return from_dt, to_dt


async def graylog_search(
    client: GraylogClient,
    config: GraylogConfig,
    cache: TTLCache,
    query: str,
    from_time: str = "-1h",
    to_time: str = "now",
    limit: int | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """
    Search Graylog logs with query string and time range.

    Args:
        client: Graylog client instance
        config: Graylog configuration
        cache: Cache instance (not used for search - always live data)
        query: Graylog search query (Lucene syntax)
        from_time: Start time (ISO8601 or relative: '-1h', '-30m'). Default: '-1h'
        to_time: End time (ISO8601 or relative: 'now'). Default: 'now'
        limit: Max results. Default: config.default_results, Max: config.max_results
        fields: Fields to return. Default: all

    Returns:
        Search results dictionary with structure:
        {
            "total_results": int,
            "returned": int,
            "truncated": bool,
            "query": str,
            "time_range": {"from": iso8601, "to": iso8601},
            "messages": [...]
        }

    Raises:
        OverwatchError: On validation or API errors
    """
    # Validate time range
    from_dt, to_dt = _validate_time_range(from_time, to_time, config.max_time_range_hours)

    # Set limit with defaults and clamping
    if limit is None:
        limit = config.default_results
    limit = min(limit, config.max_results)

    # Execute search
    raw_response = await client.search(
        query=query,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        fields=fields,
    )

    # Transform response to spec format
    messages = raw_response.get("messages", [])
    total_results = raw_response.get("total_results", len(messages))

    # Build response
    response = {
        "total_results": total_results,
        "returned": len(messages),
        "truncated": total_results > len(messages),
        "query": query,
        "time_range": {
            "from": from_dt.isoformat(),
            "to": to_dt.isoformat(),
        },
        "messages": messages,
    }

    return response


async def graylog_fields(
    client: GraylogClient,
    config: GraylogConfig,
    cache: TTLCache,
    pattern: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """
    List available fields in Graylog logs, optionally filtered by pattern.

    Args:
        client: Graylog client instance
        config: Graylog configuration
        cache: Cache instance for field list caching
        pattern: Regex pattern to filter field names (e.g., 'http_.*', 'error'). Default: none
        limit: Max fields to return. Default: 100, Max: 500

    Returns:
        Fields list dictionary with structure:
        {
            "fields": [{"name": str, "type": str}, ...],
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

    # Try to get from cache
    cache_key = "graylog_fields"
    cached_data = cache.get(cache_key)
    was_cached = cached_data is not None

    if cached_data is None:
        # Fetch from API
        raw_response = await client.get_fields()
        cached_data = raw_response.get("fields", [])

        # Cache the raw field list (TTL managed by cache instance)
        cache.set(cache_key, cached_data)

    # Transform to list of {name, type} dicts
    all_fields = []
    for field_name, field_info in cached_data.items():
        field_type = field_info if isinstance(field_info, str) else field_info.get("type", "unknown")
        all_fields.append({
            "name": field_name,
            "type": field_type
        })

    # Apply pattern filter if provided
    if compiled_pattern:
        all_fields = [
            field for field in all_fields
            if compiled_pattern.search(field["name"])
        ]

    # Sort alphabetically
    all_fields.sort(key=lambda f: f["name"])

    # Apply limit
    total_available = len(all_fields)
    truncated_fields = all_fields[:limit]

    response = {
        "fields": truncated_fields,
        "count": len(truncated_fields),
        "total_available": total_available,
        "pattern": pattern,
        "truncated": total_available > len(truncated_fields),
        "cached": was_cached,
    }

    return response
