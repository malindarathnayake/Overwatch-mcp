# Overwatch MCP

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ghcr.io%2Fmalindarathnayake%2Foverwatch--mcp-blue?logo=docker)](https://ghcr.io/malindarathnayake/overwatch-mcp)
[![CI](https://github.com/malindarathnayake/Overwatch-mcp/actions/workflows/docker-build.yml/badge.svg)](https://github.com/malindarathnayake/Overwatch-mcp/actions/workflows/docker-build.yml)

MCP server for querying Graylog, Prometheus, and InfluxDB 2.x from Claude Desktop.

## Tools

| Tool | What it does |
|------|--------------|
| `graylog_search` | Search logs (Lucene syntax) |
| `graylog_fields` | List log fields |
| `prometheus_query` | Instant PromQL query |
| `prometheus_query_range` | Range PromQL query |
| `prometheus_metrics` | List metrics |
| `influxdb_query` | Flux query (bucket allowlisted) |

## Quick Start

### One-Line Setup (Docker)

```bash
curl -fsSL https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/setup.sh | bash
cd Overwatch_MCP
# Edit .env and config.yaml with your values
docker compose up -d
```

### Manual Setup (Docker)

```bash
# Download compose files
mkdir -p Overwatch_MCP && cd Overwatch_MCP
curl -fsSLO https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/.env.example
curl -fsSLO https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/config.example.yaml

# Create config from templates
cp .env.example .env
cp config.example.yaml config.yaml

# Edit .env with your credentials
# Edit config.yaml if needed (adjust allowed_buckets, limits, etc.)

# Run
docker compose up -d
```

### Local Install

```bash
pip install -e .
cp .env.example .env
cp config/config.example.yaml config/config.yaml
# Edit both files with your values
python -m overwatch_mcp
```

## Claude Desktop Config

### Docker

`~/.claude/config.json` (Linux/Mac) or `%APPDATA%\Claude\config.json` (Windows):

```json
{
  "mcpServers": {
    "overwatch": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/config:/app/config:ro",
        "--env-file", "/path/to/.env",
        "ghcr.io/malindarathnayake/Overwatch-mcp:latest"
      ]
    }
  }
}
```

### Local Python

```json
{
  "mcpServers": {
    "overwatch": {
      "command": "python",
      "args": ["-m", "overwatch_mcp"],
      "env": {
        "GRAYLOG_URL": "https://graylog.internal:9000/api",
        "GRAYLOG_TOKEN": "your-token",
        "PROMETHEUS_URL": "http://prometheus.internal:9090",
        "INFLUXDB_URL": "https://influxdb.internal:8086",
        "INFLUXDB_TOKEN": "your-token",
        "INFLUXDB_ORG": "your-org"
      }
    }
  }
}
```

## Configuration

### config.yaml

The config uses `${ENV_VAR}` substitution - values come from environment at runtime.

```yaml
server:
  log_level: "info"

datasources:
  graylog:
    enabled: true
    url: "${GRAYLOG_URL}"
    token: "${GRAYLOG_TOKEN}"
    timeout_seconds: 30
    max_time_range_hours: 24
    max_results: 1000

  prometheus:
    enabled: true
    url: "${PROMETHEUS_URL}"
    timeout_seconds: 30
    max_range_hours: 168

  influxdb:
    enabled: true
    url: "${INFLUXDB_URL}"
    token: "${INFLUXDB_TOKEN}"
    org: "${INFLUXDB_ORG}"
    timeout_seconds: 60
    allowed_buckets:
      - "telegraf"
      - "app_metrics"

cache:
  enabled: true
  default_ttl_seconds: 60
```

Disable a datasource by setting `enabled: false`. Server runs in degraded mode if some datasources fail health checks.

## Tool Parameters

### graylog_search

```json
{
  "query": "level:ERROR AND service:api",
  "from_time": "-2h",
  "to_time": "now",
  "limit": 100,
  "fields": ["timestamp", "message", "level"]
}
```

Time formats: ISO8601 (`2025-01-27T10:00:00Z`), relative (`-1h`, `-30m`), `now`

### graylog_fields

```json
{
  "pattern": "http_.*",
  "limit": 100
}
```

### prometheus_query

```json
{
  "query": "rate(http_requests_total[5m])",
  "time": "-1h"
}
```

### prometheus_query_range

```json
{
  "query": "up",
  "start": "-6h",
  "end": "now",
  "step": "1m"
}
```

Step auto-calculated if omitted.

### prometheus_metrics

```json
{
  "pattern": "http_.*",
  "limit": 100
}
```

### influxdb_query

```json
{
  "query": "from(bucket: \"telegraf\") |> range(start: -1h) |> filter(fn: (r) => r._measurement == \"cpu\")",
  "bucket": "telegraf"
}
```

Bucket must be in `allowed_buckets` config.

## Error Codes

| Code | Meaning |
|------|---------|
| `DATASOURCE_DISABLED` | Datasource disabled in config |
| `DATASOURCE_UNAVAILABLE` | Failed health check |
| `INVALID_QUERY` | Bad query syntax |
| `INVALID_PATTERN` | Bad regex |
| `TIME_RANGE_EXCEEDED` | Range exceeds max |
| `BUCKET_NOT_ALLOWED` | Bucket not in allowlist |
| `UPSTREAM_TIMEOUT` | Request timed out |
| `UPSTREAM_CLIENT_ERROR` | 4xx from datasource |
| `UPSTREAM_SERVER_ERROR` | 5xx from datasource |

## Development

```bash
# Install with dev deps
pip install -e ".[dev]"

# Tests
pytest tests/ -v

# Coverage
pytest tests/ -v --cov=overwatch_mcp
```

### Project Structure

```
src/overwatch_mcp/
├── __main__.py        # Entry point
├── server.py          # MCP server
├── config.py          # Config loader
├── cache.py           # TTL cache
├── clients/           # HTTP clients (graylog, prometheus, influxdb)
├── tools/             # MCP tool implementations
└── models/            # Pydantic models
```

127 tests (89 unit, 38 integration).

## Troubleshooting

**Server won't start**: Check `config/config.yaml` exists and env vars are set.

**Datasource unavailable**: Verify URL, check token permissions. Server continues with available datasources.

**Query errors**: Check syntax (Lucene/PromQL/Flux), verify time range within limits, ensure bucket is allowlisted for InfluxDB.

## License

MIT
