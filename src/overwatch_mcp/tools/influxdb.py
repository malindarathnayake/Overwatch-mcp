"""InfluxDB MCP tools."""

from typing import Any

from overwatch_mcp.cache import Cache
from overwatch_mcp.clients.influxdb import InfluxDBClient
from overwatch_mcp.models.config import InfluxDBConfig


async def influxdb_query(
    client: InfluxDBClient,
    config: InfluxDBConfig,
    cache: Cache,
    query: str,
    bucket: str,
) -> dict[str, Any]:
    """
    Execute Flux query against InfluxDB 2.x.

    Args:
        client: InfluxDB client instance
        config: InfluxDB configuration
        cache: Cache instance (not used - InfluxDB queries are not cached)
        query: Flux query
        bucket: Target bucket (must be in allowed_buckets)

    Returns:
        Query result dictionary with structure:
        {
            "tables": [
                {
                    "columns": [str, ...],
                    "records": [dict, ...]
                }
            ],
            "record_count": int,
            "truncated": bool
        }

    Raises:
        OverwatchError: On bucket validation errors, query errors, or API failures
    """
    # Execute query (bucket validation happens in client)
    records = await client.query(query=query, bucket=bucket)

    # Group records by table (InfluxDB returns flat list, but we organize by table)
    # For now, we'll treat all records as a single table
    # In a more sophisticated implementation, we could parse the _measurement field
    # to separate into multiple tables

    # Extract column names from first record if available
    # Filter out empty column names (from leading commas in InfluxDB CSV format)
    columns = [col for col in records[0].keys() if col] if records else []

    # Clean records to remove empty column names
    cleaned_records = [{k: v for k, v in record.items() if k} for record in records]

    # Build response
    response = {
        "tables": [
            {
                "columns": columns,
                "records": cleaned_records,
            }
        ],
        "record_count": len(cleaned_records),
        "truncated": False,  # InfluxDB doesn't provide total count, so we can't detect truncation
    }

    return response
