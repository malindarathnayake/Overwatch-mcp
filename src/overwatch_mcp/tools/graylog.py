"""Graylog MCP tools."""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from overwatch_mcp.cache import TTLCache
from overwatch_mcp.clients.graylog import GraylogClient
from overwatch_mcp.models.config import GraylogConfig
from overwatch_mcp.models.errors import ErrorCode, OverwatchError

logger = logging.getLogger(__name__)

# Cache for known applications (loaded once)
_known_applications: dict[str, Any] | None = None
_auto_filter: str | None = None


def _load_known_applications(config: GraylogConfig) -> dict[str, Any]:
    """Load known applications from JSON file if configured."""
    global _known_applications, _auto_filter

    if _known_applications is not None:
        return _known_applications

    if not config.known_applications_file:
        _known_applications = {}
        return _known_applications

    file_path = Path(config.known_applications_file)
    if not file_path.exists():
        logger.warning(f"Known applications file not found: {file_path}")
        _known_applications = {}
        return _known_applications

    try:
        with open(file_path) as f:
            _known_applications = json.load(f)
        
        app_count = len(_known_applications.get('applications', []))
        logger.info(f"Loaded {app_count} known applications")
        
        # Auto-build filter from discovered environments
        _auto_filter = _build_auto_filter(_known_applications, config)
        if _auto_filter:
            logger.info(f"Auto-built environment filter: {_auto_filter}")
            
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load known applications: {e}")
        _known_applications = {}

    return _known_applications


def _build_auto_filter(known_apps: dict[str, Any], config: GraylogConfig) -> str | None:
    """
    Build environment filter from discovered data.
    
    Uses environment fields from metadata and matches against production_environments config.
    """
    metadata = known_apps.get("_metadata", {})
    env_fields = metadata.get("environment_fields_used", [])
    discovered_envs = known_apps.get("environments", [])
    
    if not env_fields or not discovered_envs:
        return None
    
    # Find which production environments exist in discovered data
    prod_envs = [
        env for env in discovered_envs 
        if env in config.production_environments
    ]
    
    if not prod_envs:
        logger.warning(f"No production environments found. Discovered: {discovered_envs}, Looking for: {config.production_environments}")
        return None
    
    # Build filter for each environment field
    filters = []
    for field in env_fields:
        if len(prod_envs) == 1:
            filters.append(f"{field}:{prod_envs[0]}")
        else:
            env_values = " OR ".join(prod_envs)
            filters.append(f"{field}:({env_values})")
    
    if len(filters) == 1:
        return filters[0]
    else:
        return "(" + " OR ".join(filters) + ")"


def _get_effective_filter(config: GraylogConfig) -> str | None:
    """Get the effective filter - auto-built or configured."""
    # Ensure known apps are loaded (which builds auto filter)
    _load_known_applications(config)
    
    # Prefer auto-built filter, fall back to configured
    if _auto_filter:
        return _auto_filter
    return config.default_query_filter


def _apply_default_filter(query: str, config: GraylogConfig) -> str:
    """
    Apply default query filter if configured and not already present.

    The filter is NOT applied if:
    - No default/auto filter available
    - Query already contains environment/env filter
    - Query explicitly mentions other environments (dev, staging, test, etc.)
    """
    effective_filter = _get_effective_filter(config)
    
    if not effective_filter:
        return query

    # Check if query already has environment-related filter (case-insensitive)
    env_patterns = [
        r'\b[Ee]nvironment:', r'\b[Ee]nv:', r'\bENVIRONMENT:',
        r'\b(dev|development|staging|stage|test|qa|uat|preprod|prod|production)\b'
    ]
    for pattern in env_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return query  # User specified environment, don't override

    # Prepend effective filter
    # Handle wildcard-only queries (Graylog doesn't like "filter AND *")
    if query.strip() == "*":
        return effective_filter
    return f"({effective_filter}) AND ({query})"


def get_known_applications(config: GraylogConfig) -> dict[str, Any]:
    """
    Get known applications metadata.

    Returns:
        Dictionary with application info for faster lookups.
    """
    return _load_known_applications(config)


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

    # Check time range (allow small tolerance for floating point)
    time_range_hours = (to_dt - from_dt).total_seconds() / 3600
    if time_range_hours > max_hours + 0.01:  # 0.01h = 36 seconds tolerance
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
    include_env_filter: bool = True,
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
        include_env_filter: Apply default environment filter. Default: True

    Returns:
        Search results dictionary with structure:
        {
            "total_results": int,
            "returned": int,
            "truncated": bool,
            "query": str,
            "effective_query": str,
            "time_range": {"from": iso8601, "to": iso8601},
            "messages": [...]
        }

    Raises:
        OverwatchError: On validation or API errors
    """
    # Validate time range
    from_dt, to_dt = _validate_time_range(from_time, to_time, config.max_time_range_hours)

    # Apply default environment filter if configured
    effective_query = _apply_default_filter(query, config) if include_env_filter else query
    
    logger.debug(f"Graylog search - original query: {query}")
    logger.debug(f"Graylog search - effective query: {effective_query}")
    
    # Warn about leading wildcards (often disabled in Graylog)
    if re.search(r':\*[^*\s]+', effective_query):
        logger.warning(f"Query contains leading wildcard (*text) which may fail. Consider using trailing wildcard (text*) instead.")

    # Set limit with defaults and clamping
    if limit is None:
        limit = config.default_results
    limit = min(limit, config.max_results)

    # Execute search with effective query
    raw_response = await client.search(
        query=effective_query,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        fields=fields,
    )

    # Transform response to spec format
    messages = raw_response.get("messages", [])
    total_results = raw_response.get("total_results", len(messages))

    # Analyze results for hints
    hints = _generate_search_hints(messages, total_results, query)

    # Build response
    response = {
        "total_results": total_results,
        "returned": len(messages),
        "truncated": total_results > len(messages),
        "query": query,
        "effective_query": effective_query,
        "filter_applied": effective_query != query,
        "time_range": {
            "from": from_dt.isoformat(),
            "to": to_dt.isoformat(),
        },
        "messages": messages,
        "_hints": hints,
    }

    return response


def _generate_search_hints(messages: list[dict], total_results: int, query: str) -> dict[str, Any]:
    """Generate analysis hints based on search results."""
    hints: dict[str, Any] = {
        "analysis_tips": [],
        "suggested_filters": [],
        "key_fields": ["timestamp", "level", "source", "message"],
    }

    if not messages:
        hints["analysis_tips"].append("No results found. Try broadening your query or time range.")
        return hints

    # Analyze message levels
    levels: dict[str, int] = {}
    sources: dict[str, int] = {}
    
    for msg in messages:
        message_data = msg.get("message", {})
        
        level = message_data.get("level") or message_data.get("Level") or "unknown"
        levels[level] = levels.get(level, 0) + 1
        
        source = message_data.get("source") or message_data.get("application") or message_data.get("service") or "unknown"
        sources[source] = sources.get(source, 0) + 1

    # Add level breakdown
    if levels:
        hints["level_breakdown"] = dict(sorted(levels.items(), key=lambda x: x[1], reverse=True))
        
        error_count = levels.get("ERROR", 0) + levels.get("error", 0) + levels.get("3", 0)
        warn_count = levels.get("WARN", 0) + levels.get("WARNING", 0) + levels.get("warn", 0) + levels.get("4", 0)
        
        if error_count > 0:
            hints["analysis_tips"].append(f"Found {error_count} ERROR level logs - investigate these first")
            hints["suggested_filters"].append("level:ERROR")
        if warn_count > 0:
            hints["analysis_tips"].append(f"Found {warn_count} WARN level logs - check for degradation patterns")

    # Add source breakdown (top 5)
    if sources:
        top_sources = dict(sorted(sources.items(), key=lambda x: x[1], reverse=True)[:5])
        hints["source_breakdown"] = top_sources
        
        if len(sources) > 1:
            top_source = list(top_sources.keys())[0]
            hints["analysis_tips"].append(f"Most logs from '{top_source}' - filter by source to focus")
            hints["suggested_filters"].append(f"source:{top_source}")

    # Truncation warning
    if total_results > len(messages):
        hints["analysis_tips"].append(
            f"Results truncated ({len(messages)} of {total_results}). "
            "Add filters or narrow time range for complete data."
        )

    # Pattern detection tips
    if "error" not in query.lower() and "level" not in query.lower():
        hints["suggested_filters"].append("level:ERROR")
        hints["suggested_filters"].append("level:WARN")

    return hints


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
