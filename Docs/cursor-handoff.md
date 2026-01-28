# Observability MCP Server - Implementation Handoff

## Project Overview

MCP server providing Claude Desktop with tools to query Graylog, Prometheus, and InfluxDB 2.x for log search, metric queries, and time-series analysis.

**Read the full spec:** `Docs/spec.md`

---

## Before Starting: Check Progress

**On every session start:**

1. Check `Docs/PROGRESS.md` for current state
2. Scan existing files to verify progress:
   ```bash
   find . -name "*.py" | grep -v __pycache__ | grep -v test | sort
   find . -name "test_*.py" | sort
   ```
3. Run test suite to verify status:
   ```bash
   pytest tests/ -v --tb=short
   ```
4. Resume from next incomplete item in PROGRESS.md

---

## Rules

**On every new session:**
1. Read `Docs/PROGRESS.md` to see current state
2. Scan existing files to verify progress is accurate
3. Run tests to check status
4. Resume from next incomplete item

**During implementation:**
1. **After each file, write tests for it** — Create test file alongside implementation
2. **If testing requires dependencies, build them first** — Build dep, then test together
3. **Run tests before proceeding** — Confirm the stack works
4. **Update `Docs/PROGRESS.md` after each unit** — Mark completed, log results
5. **Stop for review after each testable unit** — A unit may be 1-3 related files
6. **No features beyond the spec** — If not in spec, don't add it
7. **Ask if ambiguous** — Don't guess, ask before proceeding
8. **Environment variables for credentials** — Use `${VARNAME}`, never hardcode
9. **Error handling is mandatory** — Every external call needs error handling
10. **Start new chat after checkpoints** — Context isolation prevents drift
11. **Never silently retry failures** — Log error to PROGRESS.md, then change approach

---

## First Session Setup

**If `Docs/PROGRESS.md` does not exist, this is the first session.**

### Step 1: Create Progress Tracker

Create `Docs/PROGRESS.md` from template with:
- Checklist copied from Implementation Order
- Empty Session Log and Error Recovery Log
- Environment Notes filled in

### Step 2: Create Testing Harness

Create `Docs/testing-harness.md` — already provided.

### Step 3: Capture Discovery Samples

Before writing production code, capture sample API responses:

**Graylog:**
```bash
curl -H "Authorization: Bearer $GRAYLOG_TOKEN" \
  "$GRAYLOG_URL/api/search/universal/relative?query=*&range=300&limit=1" | jq . > Docs/samples/graylog_search.json

curl -H "Authorization: Bearer $GRAYLOG_TOKEN" \
  "$GRAYLOG_URL/api/system/fields" | jq . > Docs/samples/graylog_fields.json
```

**Prometheus:**
```bash
curl "$PROMETHEUS_URL/api/v1/query?query=up" | jq . > Docs/samples/prometheus_instant.json

curl "$PROMETHEUS_URL/api/v1/query_range?query=up&start=$(date -d '1 hour ago' +%s)&end=$(date +%s)&step=60" | jq . > Docs/samples/prometheus_range.json

curl "$PROMETHEUS_URL/api/v1/label/__name__/values" | jq . > Docs/samples/prometheus_metrics.json
```

**InfluxDB:**
```bash
curl -X POST "$INFLUXDB_URL/api/v2/query?org=$INFLUXDB_ORG" \
  -H "Authorization: Token $INFLUXDB_TOKEN" \
  -H "Content-Type: application/vnd.flux" \
  -d 'from(bucket:"telegraf") |> range(start: -5m) |> limit(n: 5)' > Docs/samples/influxdb_flux.csv
```

Save to `Docs/samples/` and document in `Docs/discovery-notes.md`.

### Step 4: Begin Implementation

Proceed to first file in Implementation Order.

---

## Implementation Order

**First: Check `Docs/PROGRESS.md` and resume from last completed unit.**

### Phase 1: Foundation

**Unit 1a: Project scaffold + models**
1. `pyproject.toml` — dependencies, project metadata
2. `src/observability_mcp_server/__init__.py` — package init with version
3. `src/observability_mcp_server/models/__init__.py` — models package
4. `src/observability_mcp_server/models/errors.py` — error code enum + ErrorResponse model
5. `src/observability_mcp_server/models/config.py` — Pydantic config models (nested: server, datasources, cache)
6. `src/observability_mcp_server/models/responses.py` — response schemas for each tool
7. `tests/__init__.py`, `tests/unit/__init__.py`
8. `tests/conftest.py` — shared fixtures
9. `tests/unit/test_config.py` — config model validation tests

```bash
pytest tests/unit/test_config.py -v
```

**Unit 1b: Config loader + cache**
10. `src/observability_mcp_server/config.py` — YAML loader, env var substitution, validation
11. `src/observability_mcp_server/cache.py` — TTL cache wrapper around cachetools
12. `tests/unit/test_cache.py` — cache TTL expiry, key generation, hit/miss

```bash
pytest tests/unit/test_config.py tests/unit/test_cache.py -v
```

**✓ CHECKPOINT:** `pytest tests/unit/ -v`
**→ NEW CHAT after passing. Update PROGRESS.md first.**

---

### Phase 2: HTTP Clients

**Unit 2a: Base client + Graylog**
13. `src/observability_mcp_server/clients/__init__.py`
14. `src/observability_mcp_server/clients/base.py` — BaseClient with httpx, retry logic, timeout handling
15. `src/observability_mcp_server/clients/graylog.py` — GraylogClient (search, fields endpoints)
16. `tests/unit/test_graylog_client.py` — request building, response parsing, auth header

```bash
pytest tests/unit/test_graylog_client.py -v
```

**Unit 2b: Prometheus client**
17. `src/observability_mcp_server/clients/prometheus.py` — PrometheusClient (query, query_range, label values)
18. `tests/unit/test_prometheus_client.py` — vector/matrix/scalar response parsing

```bash
pytest tests/unit/test_prometheus_client.py -v
```

**Unit 2c: InfluxDB client**
19. `src/observability_mcp_server/clients/influxdb.py` — InfluxDBClient (query endpoint, CSV parsing)
20. `tests/unit/test_influxdb_client.py` — annotated CSV to JSON conversion

```bash
pytest tests/unit/test_influxdb_client.py -v
```

**✓ CHECKPOINT:** `pytest tests/unit/ -v`
**→ NEW CHAT after passing. Update PROGRESS.md first.**

---

### Phase 3: MCP Tools

**Unit 3a: Graylog tools**
21. `src/observability_mcp_server/tools/__init__.py`
22. `src/observability_mcp_server/tools/graylog.py` — graylog_search, graylog_fields tool implementations
23. `tests/integration/__init__.py`
24. `tests/integration/test_graylog_tool.py` — parameter validation, time range limits, pattern filtering

```bash
pytest tests/integration/test_graylog_tool.py -v
```

**Unit 3b: Prometheus tools**
25. `src/observability_mcp_server/tools/prometheus.py` — prometheus_query, prometheus_query_range, prometheus_metrics
26. `tests/integration/test_prometheus_tool.py` — step auto-calculation, pattern filtering, limits

```bash
pytest tests/integration/test_prometheus_tool.py -v
```

**Unit 3c: InfluxDB tools**
27. `src/observability_mcp_server/tools/influxdb.py` — influxdb_query with bucket allowlist
28. `tests/integration/test_influxdb_tool.py` — bucket validation, query validation

```bash
pytest tests/integration/test_influxdb_tool.py -v
```

**✓ CHECKPOINT:** `pytest tests/ -v`
**→ NEW CHAT after passing. Update PROGRESS.md first.**

---

### Phase 4: Server Assembly

**Unit 4a: Server + entry point**
29. `src/observability_mcp_server/server.py` — MCP server class, tool registration, health checks
30. `src/observability_mcp_server/__main__.py` — entry point, 5-phase startup sequence
31. `config/config.example.yaml` — documented example config
32. `.env.example` — required environment variables
33. `README.md` — installation, configuration, usage

**✓ FINAL:** 
```bash
pytest tests/ -v
python -m observability_mcp_server --config config/config.example.yaml --help
```
**→ DELIVER to user. Implementation complete.**

---

## Testing Strategy

### Archetype: Discovery Polling Exporter

See `Docs/testing-harness.md` for environment-specific test execution.

### Test Patterns
- **pytest-httpx** for mocking HTTP responses
- **Pydantic model validation** for config and response testing
- **tmp_path fixture** for config file tests
- **monkeypatch** for environment variables

### Mock Boundaries

| Dependency | Mock Strategy |
|------------|---------------|
| Graylog API | pytest-httpx with recorded responses |
| Prometheus API | pytest-httpx with fixtures for vector/matrix/scalar |
| InfluxDB API | pytest-httpx with CSV response fixtures |
| Config file | tmp_path with test YAML |
| Env vars | monkeypatch |

### Coverage Targets

| Package | Target | Focus |
|---------|--------|-------|
| `models/config` | 90% | validation edge cases |
| `clients/*` | 90% | response parsing, error paths |
| `tools/*` | 80% | parameter validation, filtering |
| `cache` | 80% | TTL behavior |
| `server` | 70% | happy path startup |

---

## Quick Reference

### Checkpoint Commands

| Phase | Command |
|-------|---------|
| 1 | `pytest tests/unit/test_config.py tests/unit/test_cache.py -v` |
| 2 | `pytest tests/unit/ -v` |
| 3 | `pytest tests/ -v` |
| Final | `pytest tests/ -v && python -m observability_mcp_server --help` |

### Test Execution

```bash
# Unit tests only
pytest tests/unit/ -v

# All tests with coverage
pytest tests/ -v --cov=observability_mcp_server --cov-report=term-missing

# Single test file
pytest tests/unit/test_graylog_client.py -v

# With real backends (requires env vars)
GRAYLOG_URL=... GRAYLOG_TOKEN=... pytest tests/integration/ -v --real
```

### Error Recovery Protocol

When something fails:

| Attempt | Action |
|---------|--------|
| 1 | Diagnose root cause, apply targeted fix |
| 2 | Different approach — same error means wrong strategy |
| 3 | Question assumptions, check docs/examples |
| 4+ | **STOP** — log to Error Recovery Log, escalate to user |

**Never silently retry the same approach.** If it failed twice, the strategy is wrong.

---

## Key Implementation Details

### Config Loading Order
1. Load YAML file
2. Substitute `${VAR}` with environment variables
3. Validate with Pydantic
4. Missing required env vars → Exit(1)

### Time Parsing
Support both formats:
- ISO8601: `2025-01-27T10:00:00Z`
- Relative: `-1h`, `-30m`, `now`

Use a shared utility function in `tools/__init__.py` or a dedicated `utils.py`.

### Regex Pattern Filtering
```python
import re

def filter_by_pattern(items: list[str], pattern: str | None, limit: int) -> tuple[list[str], bool]:
    if pattern:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise InvalidPatternError(str(e))
        items = [i for i in items if regex.search(i)]
    
    truncated = len(items) > limit
    return sorted(items)[:limit], truncated
```

### InfluxDB CSV Parsing
InfluxDB returns annotated CSV with metadata rows. Key parsing rules:
- Lines starting with `#` are annotations (skip or parse for column types)
- Empty lines separate tables
- First non-annotation line is header
- Parse `_time` as ISO8601, `_value` as float

### MCP Tool Registration
```python
from mcp import Server

server = Server("observability-mcp-server")

@server.tool()
async def graylog_search(query: str, from_time: str = "-1h", ...) -> dict:
    """Search Graylog logs with query string and time range."""
    # Implementation
```

---

## Start

**First session?**
1. Create `Docs/PROGRESS.md` (Step 1 above)
2. Capture API samples (Step 3 above)
3. Begin with `pyproject.toml`

**Resuming?**
1. Read `Docs/PROGRESS.md` — check Current Status and Error Recovery Log
2. Verify with file scan
3. Run checkpoint for current phase
4. Continue from next incomplete item

### First File: `pyproject.toml`

Requirements:
- Python >=3.11
- Dependencies as listed in spec
- Dev dependencies for testing
- Entry point: `observability-mcp-server = "observability_mcp_server.__main__:main"`

Test:
```bash
pip install -e ".[dev]"
python -c "import observability_mcp_server; print('OK')"
```

Update `Docs/PROGRESS.md`, then proceed to models.
