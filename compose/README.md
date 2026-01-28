# Overwatch MCP - Docker Compose Deployment

Portable compose setup for deploying Overwatch MCP on any host.

## One-Line Setup

```bash
curl -fsSL https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/setup.sh | bash
```

This creates `Overwatch_MCP/` with all files. Then configure and run manually.

## Upgrade Existing Installation

```bash
curl -fsSL https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/setup.sh | bash -s -- --upgrade
```

This will:
1. Backup your existing `.env`, `config.yaml`, and `docker-compose.yml` to `backup_YYYYMMDD_HHMMSS/`
2. Download the latest templates
3. Keep your existing config files (you merge manually)

After upgrade:
```bash
cd Overwatch_MCP
diff .env .env.example              # Check for new env vars
diff config.yaml config.example.yaml # Check for new config options
docker compose down && docker compose pull && docker compose up -d
```

## Manual Setup

```bash
mkdir -p Overwatch_MCP && cd Overwatch_MCP
curl -fsSLO https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/.env.example
curl -fsSLO https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/config.example.yaml
cp .env.example .env
cp config.example.yaml config.yaml
```

## Configuration

1. **Edit `.env`** with your credentials:
   ```bash
   nano .env
   ```

2. **Edit `config.yaml`** to adjust:
   - `allowed_buckets` for InfluxDB
   - Time range limits
   - Cache TTL

## Running

### For Claude Desktop (Interactive MCP)
```bash
docker compose run --rm overwatch-mcp
```

### As Background Service
```bash
docker compose up -d
docker compose logs -f
```

## Port Override (Optional)

MCP uses stdio by default. If you need to expose a port:

### Via Command Line
```bash
docker compose run --rm -p 8080:8080 overwatch-mcp
```

### Via docker-compose.yml
Add to the service definition:
```yaml
services:
  overwatch-mcp:
    # ... existing config ...
    ports:
      - "8080:8080"
```

### Via Environment Variable
```bash
docker compose run --rm -p ${PORT:-8080}:8080 overwatch-mcp
```

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Service definition |
| `.env.example` | Environment template → copy to `.env` |
| `config.example.yaml` | Config template → copy to `config.yaml` |
| `setup.sh` | One-line setup script |

## Claude Desktop Integration

Add to `~/.claude/config.json`:

```json
{
  "mcpServers": {
    "overwatch": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/Overwatch_MCP/config.yaml:/app/config/config.yaml:ro",
        "--env-file", "/path/to/Overwatch_MCP/.env",
        "ghcr.io/malindarathnayake/overwatch-mcp:latest"
      ]
    }
  }
}
```

## Network Options

### Host Network (Linux only)
Uncomment in `docker-compose.yml`:
```yaml
network_mode: host
```

### Docker Desktop (Mac/Windows)
Use `host.docker.internal` for localhost services:
```
PROMETHEUS_URL=http://host.docker.internal:9090
```

### Static Host Mapping
Add to `docker-compose.yml`:
```yaml
extra_hosts:
  - "graylog.internal:192.168.1.100"
```

## Troubleshooting

**Can't reach datasources**: Docker has its own network. Use actual IPs or `host.docker.internal`.

**Debug mode**: Set `LOG_LEVEL=debug` in `.env`.

**View logs**: `docker compose logs -f`
