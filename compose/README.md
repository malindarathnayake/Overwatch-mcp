# Overwatch MCP - Docker Compose Deployment

Portable compose setup for deploying Overwatch MCP on any host.

## One-Line Setup

```bash
curl -fsSL https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/setup.sh | bash
cd Overwatch_MCP
nano .env          # Add your credentials
nano config.yaml   # Adjust if needed
docker compose up -d
```

## Manual Setup

```bash
# Download files
mkdir -p Overwatch_MCP && cd Overwatch_MCP
curl -fsSLO https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/.env.example
curl -fsSLO https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/config.example.yaml

# Create config from templates
cp .env.example .env
cp config.example.yaml config.yaml

# Edit with your values
nano .env
nano config.yaml

# Start
docker compose up -d
docker compose logs -f
```

## Alternative: Copy from Repo

```bash
# If you have the repo cloned
scp -r compose/ user@host:~/Overwatch_MCP/
ssh user@host "cd ~/Overwatch_MCP && cp .env.example .env && cp config.example.yaml config.yaml"
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
