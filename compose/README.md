# Overwatch MCP - Docker Compose Deployment

Portable compose setup for deploying Overwatch MCP on any host.

## Quick Start

```bash
# 1. Copy this folder to your target host
scp -r compose/ user@host:~/overwatch-mcp/

# 2. On the host, create config files
cd ~/overwatch-mcp
cp .env.example .env
cp config.example.yaml config.yaml

# 3. Edit .env with your credentials
nano .env

# 4. Edit config.yaml if needed (adjust allowed_buckets, limits, etc.)
nano config.yaml

# 5. Start the service
docker compose up -d

# 6. Check logs
docker compose logs -f
```

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Service definition |
| `.env.example` | Environment template (copy to `.env`) |
| `config.example.yaml` | Config template (copy to `config.yaml`) |

## Claude Desktop Integration

For Claude Desktop, the MCP server needs to run interactively (not as a daemon).

Add to `~/.claude/config.json`:

```json
{
  "mcpServers": {
    "overwatch": {
      "command": "docker",
      "args": [
        "compose", "-f", "/path/to/compose/docker-compose.yml",
        "run", "--rm", "-T", "overwatch-mcp"
      ]
    }
  }
}
```

Or use docker run directly:

```json
{
  "mcpServers": {
    "overwatch": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/compose/config.yaml:/app/config/config.yaml:ro",
        "--env-file", "/path/to/compose/.env",
        "ghcr.io/malindarathnayake/overwatch-mcp:latest"
      ]
    }
  }
}
```

## Troubleshooting

**Can't reach datasources**: Docker has its own network. Use actual IPs or hostnames resolvable from the container. For services on the host machine, use `host.docker.internal` (Docker Desktop) or `--network host` (Linux).

**Debug mode**: Set `LOG_LEVEL=debug` in `.env` and restart.

**Health check failing**: Check `docker compose logs` for errors.
