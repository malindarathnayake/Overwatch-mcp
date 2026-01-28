#!/usr/bin/env python3
"""
Discover applications from Graylog and generate known_applications.json.

Usage:
    python scripts/discover_applications.py --url https://graylog.example.com --token YOUR_TOKEN
    python scripts/discover_applications.py --env  # Uses GRAYLOG_URL and GRAYLOG_TOKEN env vars

Output: known_applications.json (edit to remove unwanted entries)
"""

import argparse
import asyncio
import base64
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)


# Common field names that identify applications
APP_IDENTIFIER_FIELDS = [
    "application",
    "app",
    "app_name",
    "service",
    "service_name",
    "container_name",
    "source",
    "facility",
    "logger_name",
    "kubernetes_container_name",
    "kubernetes_pod_name",
]

# Environment fields
ENV_FIELDS = ["environment", "env", "stage", "deployment"]


async def get_graylog_fields(client: httpx.AsyncClient, base_url: str) -> list[str]:
    """Get all available fields from Graylog."""
    response = await client.get(f"{base_url}/api/system/fields")
    response.raise_for_status()
    data = response.json()
    
    # Handle different response formats
    fields = data.get("fields", data)
    
    if isinstance(fields, dict):
        return list(fields.keys())
    elif isinstance(fields, list):
        # List of field names or field objects
        result = []
        for item in fields:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict) and "name" in item:
                result.append(item["name"])
        return result
    else:
        return []


async def get_field_values(
    client: httpx.AsyncClient,
    base_url: str,
    field: str,
    query: str = "*",
    time_range: int = 86400,  # 24 hours
) -> list[str]:
    """Get unique values for a field by searching and extracting."""
    # Use relative search and extract unique field values
    params = {
        "query": f"_exists_:{field}" if query == "*" else f"({query}) AND _exists_:{field}",
        "range": time_range,
        "limit": 500,  # Get enough to find unique values
        "fields": field,
    }

    try:
        response = await client.get(
            f"{base_url}/api/search/universal/relative",
            params=params,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        # Extract unique values from messages
        unique_values = set()
        messages = data.get("messages", [])
        
        for msg in messages:
            message = msg.get("message", {})
            value = message.get(field)
            if value and isinstance(value, str) and value.strip():
                unique_values.add(value.strip())
        
        return list(unique_values)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (400, 404):
            # Field might not work or endpoint issue
            print(f"    Warning: Could not query field '{field}': {e.response.status_code}")
            return []
        raise


async def discover_applications(
    base_url: str,
    token: str,
    verify_ssl: bool = False,
    time_range_hours: int = 24,
    environment_filter: str | None = None,
) -> dict:
    """
    Discover applications from Graylog.

    Returns:
        Dictionary with discovered applications and metadata.
    """
    # Setup auth
    auth_string = f"{token}:token"
    auth_bytes = base64.b64encode(auth_string.encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_bytes}",
        "Accept": "application/json",
    }

    # Normalize URL
    base_url = base_url.rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[:-4]

    time_range_seconds = time_range_hours * 3600
    query = environment_filter or "*"

    async with httpx.AsyncClient(headers=headers, verify=verify_ssl) as client:
        print(f"Connecting to {base_url}...")

        # Get available fields
        print("Fetching available fields...")
        all_fields = await get_graylog_fields(client, base_url)
        print(f"  Found {len(all_fields)} fields")

        # Find which identifier fields exist
        available_id_fields = [f for f in APP_IDENTIFIER_FIELDS if f in all_fields]
        available_env_fields = [f for f in ENV_FIELDS if f in all_fields]

        print(f"  Application identifier fields: {available_id_fields}")
        print(f"  Environment fields: {available_env_fields}")

        # Discover applications per field
        applications = defaultdict(lambda: {"sources": [], "environments": set(), "count": 0})

        for field in available_id_fields:
            print(f"\nDiscovering from '{field}'...")
            values = await get_field_values(
                client, base_url, field, query=query, time_range=time_range_seconds
            )
            print(f"  Found {len(values)} unique values")

            for value in values:
                if value and value.strip():
                    app_key = value.strip()
                    if field not in applications[app_key]["sources"]:
                        applications[app_key]["sources"].append(field)

        # Discover environments
        environments = set()
        for field in available_env_fields:
            print(f"\nDiscovering environments from '{field}'...")
            values = await get_field_values(
                client, base_url, field, query="*", time_range=time_range_seconds
            )
            environments.update(v.strip() for v in values if v and v.strip())

        print(f"\nFound {len(applications)} unique applications")
        print(f"Found environments: {sorted(environments)}")

        # Build output structure
        output = {
            "_metadata": {
                "generated_at": datetime.now().isoformat(),
                "graylog_url": base_url,
                "time_range_hours": time_range_hours,
                "environment_filter": environment_filter,
                "identifier_fields_used": available_id_fields,
                "environment_fields_used": available_env_fields,
            },
            "environments": sorted(environments),
            "applications": [],
        }

        # Sort applications alphabetically
        for app_name in sorted(applications.keys()):
            app_info = applications[app_name]
            output["applications"].append({
                "name": app_name,
                "identifier_fields": app_info["sources"],
                "aliases": [],  # User can add manual aliases
                "description": "",  # User can add description
                "team": "",  # User can add team ownership
                "enabled": True,  # User can disable entries they don't want
            })

        return output


def main():
    parser = argparse.ArgumentParser(
        description="Discover applications from Graylog and generate known_applications.json"
    )
    parser.add_argument(
        "--url",
        help="Graylog URL (or set GRAYLOG_URL env var)",
    )
    parser.add_argument(
        "--token",
        help="Graylog API token (or set GRAYLOG_TOKEN env var)",
    )
    parser.add_argument(
        "--env",
        action="store_true",
        help="Use GRAYLOG_URL and GRAYLOG_TOKEN environment variables",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="known_applications.json",
        help="Output file path (default: known_applications.json)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Time range to search in hours (default: 24)",
    )
    parser.add_argument(
        "--environment",
        "-e",
        help="Filter by environment (e.g., 'environment:prod')",
    )
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Verify SSL certificates (default: False)",
    )

    args = parser.parse_args()

    # Get credentials
    url = args.url or os.environ.get("GRAYLOG_URL")
    token = args.token or os.environ.get("GRAYLOG_TOKEN")

    if not url:
        print("Error: Graylog URL required. Use --url or set GRAYLOG_URL env var")
        sys.exit(1)
    if not token:
        print("Error: Graylog token required. Use --token or set GRAYLOG_TOKEN env var")
        sys.exit(1)

    # Run discovery
    try:
        result = asyncio.run(
            discover_applications(
                base_url=url,
                token=token,
                verify_ssl=args.verify_ssl,
                time_range_hours=args.hours,
                environment_filter=args.environment,
            )
        )
    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code} - {e.response.text[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Write output
    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Output written to: {output_path}")
    print(f"Applications discovered: {len(result['applications'])}")
    print(f"Environments found: {result['environments']}")
    print(f"\nNext steps:")
    print(f"  1. Review {output_path} and remove unwanted entries")
    print(f"  2. Set 'enabled: false' for apps to exclude")
    print(f"  3. Add descriptions, teams, and aliases as needed")
    print(f"  4. Set GRAYLOG_KNOWN_APPS_FILE={output_path.absolute()} in your config")


if __name__ == "__main__":
    main()
