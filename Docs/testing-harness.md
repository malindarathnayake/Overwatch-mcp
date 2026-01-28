# Observability MCP Server - Testing Harness

This document defines how to run tests for this project across different environments.

---

## Archetype Selection

**Selected: Discovery Polling Exporter**

This project queries external APIs (Graylog, Prometheus, InfluxDB), transforms responses, and exposes data via MCP tools. No write operations.

---

## Operator Questions

Answer before running any tests. These determine which test tiers are available.

### Universal Questions

1. **Where are you running tests?**
   - [ ] Local Linux host
   - [ ] Windows + WSL2
   - [ ] macOS
   - [ ] CI runner (specify: _______)
   - [ ] Container-only (no host access)

2. **Can you run privileged containers?**
   - Not applicable — no privileged operations required

3. **What external dependencies are available for integration tests?**
   - [ ] None — mock everything
   - [ ] Dev instances available (Graylog, Prometheus, InfluxDB)
   - [ ] Production read-only access

### Archetype-Specific Questions (Discovery Polling Exporter)

4. **Target environment availability:**
   - [ ] Dev Graylog instance accessible: URL _______________
   - [ ] Dev Prometheus instance accessible: URL _______________
   - [ ] Dev InfluxDB instance accessible: URL _______________
   - [ ] None — unit tests with mocks only

5. **Test credential location:**
   - `GRAYLOG_URL` — Graylog API URL
   - `GRAYLOG_TOKEN` — Graylog API token
   - `PROMETHEUS_URL` — Prometheus URL (no auth)
   - `INFLUXDB_URL` — InfluxDB URL
   - `INFLUXDB_TOKEN` — InfluxDB API token
   - `INFLUXDB_ORG` — InfluxDB organization

6. **Rate limits or quotas to respect?**
   - Graylog: _____ requests/min (or "unknown")
   - Prometheus: _____ (typically none for internal)
   - InfluxDB: _____ requests/min (or "unknown")

---

## What This Harness Can and Cannot Prove

### Can Test Well
- Unit tests: **Always** — config parsing, response parsing, validation logic
- Integration with mocked HTTP: **Always** — using pytest-httpx
- Real API integration: **If dev instances available** — actual query execution

### Cannot Test (Requires Operator Verification)
- Query performance under production load
- Network latency to production backends
- Rate limit behavior at scale
- Credential rotation workflows
- Multi-day uptime stability
- MCP transport behavior (stdio tested manually with Claude Desktop)

---

## Pre-Implementation: Data Discovery

**Required before writing production code.**

Write throwaway scripts to capture real API responses for use as test fixtures.

### Discovery Scripts

#### Graylog Discovery
```bash
#!/bin/bash
# discover_graylog.sh
set -e

echo "=== Graylog Discovery ==="
echo "URL: $GRAYLOG_URL"

# Test connectivity
echo -e "\n--- Health Check ---"
curl -s -H "Authorization: Bearer $GRAYLOG_TOKEN" \
  "$GRAYLOG_URL/api/system" | jq '{version, cluster_id}'

# Search endpoint
echo -e "\n--- Search Sample ---"
curl -s -H "Authorization: Bearer $GRAYLOG_TOKEN" \
  "$GRAYLOG_URL/api/search/universal/relative?query=*&range=300&limit=2" | jq . > Docs/samples/graylog_search.json
cat Docs/samples/graylog_search.json | jq 'keys'

# Fields endpoint
echo -e "\n--- Fields Sample ---"
curl -s -H "Authorization: Bearer $GRAYLOG_TOKEN" \
  "$GRAYLOG_URL/api/system/fields" | jq . > Docs/samples/graylog_fields.json
cat Docs/samples/graylog_fields.json | jq 'keys'

echo -e "\n=== Graylog Discovery Complete ==="
```

#### Prometheus Discovery
```bash
#!/bin/bash
# discover_prometheus.sh
set -e

echo "=== Prometheus Discovery ==="
echo "URL: $PROMETHEUS_URL"

# Instant query
echo -e "\n--- Instant Query (vector) ---"
curl -s "$PROMETHEUS_URL/api/v1/query?query=up" | jq . > Docs/samples/prometheus_instant.json
cat Docs/samples/prometheus_instant.json | jq '.data.resultType'

# Range query
echo -e "\n--- Range Query (matrix) ---"
START=$(date -d '1 hour ago' +%s 2>/dev/null || date -v-1H +%s)
END=$(date +%s)
curl -s "$PROMETHEUS_URL/api/v1/query_range?query=up&start=$START&end=$END&step=60" | jq . > Docs/samples/prometheus_range.json
cat Docs/samples/prometheus_range.json | jq '.data.resultType'

# Metric list
echo -e "\n--- Metric List ---"
curl -s "$PROMETHEUS_URL/api/v1/label/__name__/values" | jq . > Docs/samples/prometheus_metrics.json
cat Docs/samples/prometheus_metrics.json | jq '.data | length'

echo -e "\n=== Prometheus Discovery Complete ==="
```

#### InfluxDB Discovery
```bash
#!/bin/bash
# discover_influxdb.sh
set -e

echo "=== InfluxDB Discovery ==="
echo "URL: $INFLUXDB_URL"
echo "Org: $INFLUXDB_ORG"

# Health check
echo -e "\n--- Health Check ---"
curl -s "$INFLUXDB_URL/health" | jq .

# List buckets
echo -e "\n--- Buckets ---"
curl -s -H "Authorization: Token $INFLUXDB_TOKEN" \
  "$INFLUXDB_URL/api/v2/buckets?org=$INFLUXDB_ORG" | jq '.buckets[].name'

# Flux query (get first available bucket)
BUCKET=$(curl -s -H "Authorization: Token $INFLUXDB_TOKEN" \
  "$INFLUXDB_URL/api/v2/buckets?org=$INFLUXDB_ORG" | jq -r '.buckets[0].name')

echo -e "\n--- Flux Query (bucket: $BUCKET) ---"
curl -s -X POST "$INFLUXDB_URL/api/v2/query?org=$INFLUXDB_ORG" \
  -H "Authorization: Token $INFLUXDB_TOKEN" \
  -H "Content-Type: application/vnd.flux" \
  -d "from(bucket:\"$BUCKET\") |> range(start: -5m) |> limit(n: 5)" > Docs/samples/influxdb_flux.csv

head -20 Docs/samples/influxdb_flux.csv

echo -e "\n=== InfluxDB Discovery Complete ==="
```

### Discovery Checklist

Complete before starting implementation:

- [ ] **Graylog connectivity:** Script connects without errors
- [ ] **Graylog search response:** Shape matches expected (messages array, total count)
- [ ] **Graylog fields response:** Shape matches expected (field names + types)
- [ ] **Prometheus connectivity:** Script connects without errors
- [ ] **Prometheus instant query:** Vector response shape understood
- [ ] **Prometheus range query:** Matrix response shape understood
- [ ] **Prometheus metrics list:** Returns array of metric names
- [ ] **InfluxDB connectivity:** Script connects without errors
- [ ] **InfluxDB Flux response:** CSV format understood (annotations, headers, data)
- [ ] **All samples saved:** `Docs/samples/` contains all response files

### Discovery Output

Save findings to `Docs/discovery-notes.md`:

```markdown
# Observability API Discovery Notes

## Graylog

**Endpoint:** [URL]
**Auth:** Bearer token
**Tested:** [date]

### Search Response Shape
- `total_results`: integer
- `messages`: array of message objects
- Each message has: `timestamp`, `message`, `source`, `fields` (object)

### Fields Response Shape
- Object with field names as keys
- Each value is an object with `type` property

### Surprises vs Docs
- [list any deviations]

## Prometheus

**Endpoint:** [URL]
**Auth:** None (internal)
**Tested:** [date]

### Response Types
- `vector`: instant query, array of {metric, value}
- `matrix`: range query, array of {metric, values[]}
- `scalar`: single value (less common)

### Metric List
- Returns array of strings
- Count: [N] metrics available

## InfluxDB

**Endpoint:** [URL]
**Auth:** Token
**Tested:** [date]

### Flux CSV Format
- Lines starting with `#` are annotations
- `#group`, `#datatype`, `#default` headers
- Empty line separates tables
- First non-annotation line is column headers

### Available Buckets
- [list buckets in test environment]
```

---

## Test Tiers

### Tier 1: Unit Tests (Always Run)

**Prerequisites:** Python 3.11+, dev dependencies installed

**What's tested:**
- Config model validation
- Response model parsing
- Time range parsing
- Regex pattern validation
- Cache TTL behavior
- HTTP client request building (mocked responses)

**Command:**
```bash
pytest tests/unit/ -v
```

**Expected result:** All tests pass, no external calls made

---

### Tier 2: Integration Tests - Mocked HTTP

**Prerequisites:** pytest-httpx installed (included in dev deps)

**What's tested:**
- Tool parameter validation
- End-to-end tool flow with mocked HTTP responses
- Error handling for various HTTP status codes
- Response transformation

**Setup:**
```bash
# No setup needed — uses pytest-httpx fixtures
```

**Command:**
```bash
pytest tests/integration/ -v
```

**Expected result:** All tests pass using recorded HTTP responses

---

### Tier 3: Integration Tests - Real Backends

**Prerequisites:**
- Environment variables set for all backends
- Network access to dev/test instances
- Appropriate permissions

**Setup:**
```bash
export GRAYLOG_URL="https://graylog.dev.internal:9000/api"
export GRAYLOG_TOKEN="your-token"
export PROMETHEUS_URL="http://prometheus.dev.internal:9090"
export INFLUXDB_URL="https://influxdb.dev.internal:8086"
export INFLUXDB_TOKEN="your-token"
export INFLUXDB_ORG="your-org"
```

**⚠ Caution:** Uses real APIs. Respect rate limits. Creates read-only load.

**Command:**
```bash
pytest tests/integration/ -v --real
```

**Note:** Tests should be marked to skip if `--real` flag not present:
```python
@pytest.mark.skipif(not pytest.config.getoption("--real"), reason="Requires --real flag")
def test_graylog_search_real():
    ...
```

---

### Tier 4: Manual E2E Test with Claude Desktop

**Prerequisites:**
- Server builds and runs
- Claude Desktop configured with MCP server
- Config file with valid credentials

**Procedure:**
1. Build/install the server:
   ```bash
   pip install -e .
   ```

2. Create config file:
   ```bash
   cp config/config.example.yaml config/config.yaml
   # Edit with real values
   ```

3. Add to Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "observability": {
         "command": "python",
         "args": ["-m", "observability_mcp_server", "--config", "/path/to/config.yaml"]
       }
     }
   }
   ```

4. Restart Claude Desktop

5. Test in conversation:
   - "Search Graylog for errors in the last hour"
   - "What metrics are available in Prometheus matching 'http'?"
   - "Query InfluxDB for CPU usage from telegraf bucket"

**Pass criteria:**
- Tools appear in Claude's tool list
- Queries execute without errors
- Responses are properly formatted

---

## Archetype-Specific Test Patterns

### Discovery Polling Exporter Patterns

#### Mock HTTP Responses
```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def graylog_search_response():
    """Load recorded Graylog search response."""
    return (Path(__file__).parent / "fixtures" / "graylog_search.json").read_text()

@pytest.fixture
def mock_graylog(httpx_mock, graylog_search_response):
    """Mock Graylog API endpoints."""
    httpx_mock.add_response(
        url="https://graylog.test/api/search/universal/relative",
        json=json.loads(graylog_search_response)
    )
    return httpx_mock
```

#### Response Parsing Tests
```python
def test_influx_csv_parsing():
    """Test annotated CSV to JSON conversion."""
    csv_data = '''#group,false,false,true,true
#datatype,string,long,dateTime:RFC3339,double
#default,_result,,,
,result,table,_time,_value
,_result,0,2025-01-27T10:00:00Z,45.2
,_result,0,2025-01-27T10:01:00Z,46.1
'''
    result = parse_influx_csv(csv_data)
    assert len(result["tables"]) == 1
    assert result["tables"][0]["records"][0]["_value"] == 45.2
```

#### Pattern Filtering Tests
```python
@pytest.mark.parametrize("pattern,input_list,expected", [
    ("http_.*", ["http_requests", "cpu_usage", "http_errors"], ["http_errors", "http_requests"]),
    ("CPU", ["cpu_usage", "CPU_temp", "memory"], ["CPU_temp", "cpu_usage"]),  # case insensitive
    (None, ["b", "a", "c"], ["a", "b", "c"]),  # no filter, sorted
])
def test_pattern_filtering(pattern, input_list, expected):
    result, _ = filter_by_pattern(input_list, pattern, limit=100)
    assert result == expected
```

#### Time Range Validation Tests
```python
@pytest.mark.parametrize("from_time,to_time,max_hours,should_pass", [
    ("-1h", "now", 24, True),
    ("-48h", "now", 24, False),  # exceeds max
    ("2025-01-27T00:00:00Z", "2025-01-27T12:00:00Z", 24, True),
    ("2025-01-27T00:00:00Z", "2025-01-26T00:00:00Z", 24, False),  # from > to
])
def test_time_range_validation(from_time, to_time, max_hours, should_pass):
    if should_pass:
        validate_time_range(from_time, to_time, max_hours)
    else:
        with pytest.raises(ValidationError):
            validate_time_range(from_time, to_time, max_hours)
```

---

## Quick Reference

### Checkpoint Commands

| Phase | Command |
|-------|---------|
| 1 | `pytest tests/unit/test_config.py tests/unit/test_cache.py -v` |
| 2 | `pytest tests/unit/ -v` |
| 3 | `pytest tests/ -v` |
| Final | `pytest tests/ -v && python -m observability_mcp_server --help` |

### Common Failures and Fixes

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `ModuleNotFoundError: mcp` | MCP SDK not installed | `pip install mcp` |
| Config validation fails | Missing env var | Check `.env` or export vars |
| httpx_mock not matching | URL mismatch | Check exact URL including query params |
| InfluxDB CSV parse error | Unexpected annotation format | Check sample CSV, update parser |
| Tests hang | Real backend timeout | Check network, add `--timeout` |

### Environment Variables for Testing

| Variable | Purpose | Test Value |
|----------|---------|------------|
| `GRAYLOG_URL` | Graylog API URL | `https://graylog.test/api` (mocked) |
| `GRAYLOG_TOKEN` | Graylog auth | `test-token` (mocked) |
| `PROMETHEUS_URL` | Prometheus URL | `http://prometheus.test:9090` (mocked) |
| `INFLUXDB_URL` | InfluxDB URL | `https://influxdb.test:8086` (mocked) |
| `INFLUXDB_TOKEN` | InfluxDB auth | `test-token` (mocked) |
| `INFLUXDB_ORG` | InfluxDB org | `test-org` (mocked) |

---

## CI Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -e ".[dev]"
      
      - name: Run unit tests
        run: pytest tests/unit/ -v --tb=short
      
      - name: Run integration tests (mocked)
        run: pytest tests/integration/ -v --tb=short

  coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -e ".[dev]"
      
      - name: Run tests with coverage
        run: pytest tests/ -v --cov=observability_mcp_server --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Test Fixtures Location

```
tests/
├── fixtures/
│   ├── graylog_search.json      # From discovery
│   ├── graylog_fields.json      # From discovery
│   ├── prometheus_instant.json  # From discovery
│   ├── prometheus_range.json    # From discovery
│   ├── prometheus_metrics.json  # From discovery
│   └── influxdb_flux.csv        # From discovery
├── conftest.py                  # Fixture loaders
├── unit/
└── integration/
```

Copy discovery samples to `tests/fixtures/` for use as test data.
