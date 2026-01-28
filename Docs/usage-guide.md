# Overwatch MCP Usage Guide

How to ask questions and get useful answers from your observability data.

## Quick Start Examples

### Finding Problems

```
"Show me errors from the last hour"
"What's failing in production?"
"Find any timeout errors in the last 6 hours"
"Are there any 5xx errors from the API?"
```

### Investigating Issues

```
"Search for errors mentioning 'connection refused'"
"Find logs where the database query failed"
"Show me authentication failures"
"What happened around 2pm today with the payment service?"
```

### System Health

```
"Is everything up?"
"Show me the CPU usage trend for the last hour"
"What's the request rate for the API?"
"Are there any services with high error rates?"
```

---

## Graylog (Log Search)

### Basic Searches

| Ask This | What It Does |
|----------|--------------|
| "Show me errors" | Searches for ERROR level logs |
| "Find warnings from the last 30 minutes" | Time-bounded WARN search |
| "Search logs for 'timeout'" | Keyword search |
| "Show me logs from service X" | Filter by source/service |

### Time Ranges

```
"errors from the last hour"        → -1h
"what happened in the last 6 hours" → -6h
"show me today's errors"           → -24h (max)
"errors between 2pm and 3pm"       → specific time range
```

### Filtering

```
"Show me only ERROR level logs"
"Find logs from the api-gateway service"
"Search for 'NullPointerException' errors"
"Show logs where http_status is 500"
```

### Combining Filters

```
"Find errors from the payment service mentioning 'timeout'"
"Show warnings from any API service in the last 2 hours"
"Search for database connection errors excluding test environments"
```

### Non-Production Searches

By default, searches focus on production. To search other environments:

```
"Search all environments for errors"
"Show me staging logs with errors"
"Find dev environment warnings"
"Search non-prod for deployment issues"
```

---

## Prometheus (Metrics)

### Current State

```
"Is everything up?"
"Show me current CPU usage"
"What's the memory usage right now?"
"Are all services healthy?"
```

### Trends Over Time

```
"Show me CPU usage over the last hour"
"What's the request rate trend for the last 6 hours?"
"Graph memory usage for today"
"Show error rate over time"
```

### Specific Metrics

```
"What's the p95 latency for HTTP requests?"
"Show me the request count per service"
"What's the disk usage percentage?"
"How many active connections are there?"
```

### Comparisons

```
"Compare CPU usage between services"
"Which service has the highest error rate?"
"Show me the top 5 services by request volume"
```

---

## InfluxDB (Time Series Data)

### Basic Queries

```
"Show me CPU metrics from the last hour"
"What's the average memory usage?"
"Get disk I/O statistics"
```

### Aggregations

```
"Show me average CPU per host"
"What's the max memory usage in the last hour?"
"Sum of all requests by endpoint"
```

### Filtering

```
"Show metrics for host server-01"
"Get CPU data where usage > 80%"
"Filter metrics by region"
```

---

## Investigation Workflows

### When Something is Broken

1. **Start broad**: "What errors are happening right now?"
2. **Identify the source**: "Which service has the most errors?"
3. **Dig deeper**: "Show me the actual error messages from [service]"
4. **Find the pattern**: "When did these errors start?"

### Performance Issues

1. **Check metrics**: "Show me CPU and memory trends for the last hour"
2. **Look for correlation**: "Did request latency increase at the same time?"
3. **Find the cause**: "Search logs for slow query warnings"

### After a Deployment

```
"Compare error rates before and after 2pm"
"Show me any new errors in the last 30 minutes"
"What's the current health of [service]?"
```

---

## Tips for Better Results

### Be Specific About Time

```
❌ "Show me errors"           → Defaults to 1 hour
✅ "Show me errors from the last 6 hours"
✅ "Errors between 2pm and 4pm today"
```

### Name Services/Sources

```
❌ "What's broken?"
✅ "What errors are coming from the API service?"
✅ "Show me payment service logs"
```

### Start Narrow, Then Expand

```
1. "Show me ERROR level logs only"
2. "Include WARN as well"
3. "Search all log levels for 'timeout'"
```

### Use Keywords

```
"timeout", "connection", "failed", "exception", "denied"
"refused", "unauthorized", "500", "503", "null"
```

### Avoid Leading Wildcards

```
❌ source:*api*        → Leading wildcards often fail
✅ source:api*         → Trailing wildcards work
✅ source:api-service  → Exact match is best
```

---

## Understanding Results

### Log Results

- **total_results**: How many logs matched (may be more than shown)
- **truncated**: True if there are more results than displayed
- **level_breakdown**: Count of logs by severity level
- **source_breakdown**: Which services/sources produced the logs

### Hints Section

Results include `_hints` with:
- **analysis_tips**: Suggestions for what to look at first
- **suggested_filters**: Recommended follow-up queries
- **level_breakdown**: ERROR/WARN/INFO counts

### When You See "truncated: true"

```
"There are more results. Show me only ERRORs to narrow it down."
"Filter to just the [service-name] source"
"Narrow the time range to the last 30 minutes"
```

---

## Common Query Patterns

### Error Investigation
```
"Show me all errors from the last hour"
→ Review the source_breakdown
→ "Now show me just the errors from [top source]"
→ "What was happening 5 minutes before these errors started?"
```

### Service Health Check
```
"Is the [service] healthy?"
"Show me error rate for [service] over the last hour"
"Any warnings from [service] recently?"
```

### Incident Response
```
"What errors are happening right now?"
"Which services are affected?"
"When did this start?"
"Show me related logs from 10 minutes before the incident"
```

### Post-Mortem
```
"Show me all errors between [start time] and [end time]"
"What was the error rate during the incident?"
"Compare metrics before, during, and after"
```

---

## Environment Filtering

### Default Behavior
- Searches automatically focus on **production** logs
- This saves tokens and focuses on what matters

### Override When Needed

```
"Search staging for this error"
"Show me dev environment logs"
"Search ALL environments for this issue"
"Include non-prod in the search"
```

---

## Getting Help

### Discover Available Fields
```
"What fields are available in Graylog?"
"Show me fields related to HTTP"
"List all kubernetes-related fields"
```

### Discover Available Metrics
```
"What Prometheus metrics are available?"
"Show me metrics related to CPU"
"List HTTP metrics"
```

### Query Syntax Help
```
"How do I search for exact phrase in Graylog?"
"What's the PromQL for error rate?"
"How do I filter by multiple services?"
```
