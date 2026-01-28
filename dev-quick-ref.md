# Overwatch MCP - Developer Quick Reference

## Docker Commands

### Building the Image

```bash
# Build the Docker image
docker build -t overwatch-mcp:latest .

# Build with specific tag
docker build -t overwatch-mcp:1.0.0 .

# Build with no cache (clean build)
docker build --no-cache -t overwatch-mcp:latest .

# Build for multi-platform (ARM64 + AMD64)
docker buildx build --platform linux/amd64,linux/arm64 -t overwatch-mcp:latest .
```

### Running the Container

```bash
# Run with environment variables
docker run --rm \
  -v $(pwd)/config:/app/config:ro \
  -e GRAYLOG_URL=https://graylog.internal:9000/api \
  -e GRAYLOG_TOKEN=your-token \
  -e PROMETHEUS_URL=http://prometheus.internal:9090 \
  -e INFLUXDB_URL=https://influxdb.internal:8086 \
  -e INFLUXDB_TOKEN=your-token \
  -e INFLUXDB_ORG=your-org \
  overwatch-mcp:latest

# Run with custom config file
docker run --rm \
  -v $(pwd)/config:/app/config:ro \
  --env-file .env \
  overwatch-mcp:latest --config /app/config/custom.yaml

# Run in detached mode
docker run -d \
  --name overwatch-mcp \
  -v $(pwd)/config:/app/config:ro \
  --env-file .env \
  overwatch-mcp:latest

# View logs
docker logs -f overwatch-mcp

# Stop container
docker stop overwatch-mcp
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  overwatch-mcp:
    image: overwatch-mcp:latest
    container_name: overwatch-mcp
    restart: unless-stopped
    volumes:
      - ./config:/app/config:ro
    environment:
      - GRAYLOG_URL=${GRAYLOG_URL}
      - GRAYLOG_TOKEN=${GRAYLOG_TOKEN}
      - PROMETHEUS_URL=${PROMETHEUS_URL}
      - INFLUXDB_URL=${INFLUXDB_URL}
      - INFLUXDB_TOKEN=${INFLUXDB_TOKEN}
      - INFLUXDB_ORG=${INFLUXDB_ORG}
    stdin_open: true
    tty: true
```

Run with Docker Compose:

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

### Pushing to Registry

```bash
# Tag for GitHub Container Registry
docker tag overwatch-mcp:latest ghcr.io/ftsgps/overwatch-mcp:latest
docker tag overwatch-mcp:latest ghcr.io/ftsgps/overwatch-mcp:1.0.0

# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Push to registry
docker push ghcr.io/ftsgps/overwatch-mcp:latest
docker push ghcr.io/ftsgps/overwatch-mcp:1.0.0

# Pull from registry
docker pull ghcr.io/ftsgps/overwatch-mcp:latest
```

## Development Workflow

### Local Development

```bash
# Install in editable mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ -v --cov=overwatch_mcp --cov-report=html

# Run linting
ruff check src/ tests/

# Run type checking
mypy src/
```

### Testing the Docker Image

```bash
# Build and test locally
docker build -t overwatch-mcp:test .

# Run tests inside container
docker run --rm overwatch-mcp:test pytest tests/ -v

# Test with minimal config
docker run --rm \
  -v $(pwd)/config/config.example.yaml:/app/config/config.yaml:ro \
  -e GRAYLOG_URL=https://graylog.test:9000/api \
  -e GRAYLOG_TOKEN=test-token \
  overwatch-mcp:test --help
```

### Debugging

```bash
# Run container with shell access
docker run --rm -it \
  -v $(pwd)/config:/app/config:ro \
  --env-file .env \
  --entrypoint /bin/bash \
  overwatch-mcp:latest

# Inside container, run manually
python -m overwatch_mcp --config /app/config/config.yaml

# Check container logs
docker logs overwatch-mcp 2>&1 | grep ERROR

# Inspect container
docker inspect overwatch-mcp
```

## GitHub Actions

### Triggering Builds

```bash
# Push to main triggers build
git push origin main

# Create release tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# Manual workflow dispatch via GitHub UI:
# Actions -> Docker Build and Push -> Run workflow
```

### Viewing Build Artifacts

```bash
# Download artifacts from GitHub UI:
# Actions -> Select workflow run -> Artifacts section

# Or use GitHub CLI
gh run list --workflow=docker-build.yml
gh run view RUN_ID
gh run download RUN_ID
```

## Configuration Management

### Environment Variables

Required variables:
```bash
GRAYLOG_URL=https://graylog.internal:9000/api
GRAYLOG_TOKEN=your-graylog-token
PROMETHEUS_URL=http://prometheus.internal:9090
INFLUXDB_URL=https://influxdb.internal:8086
INFLUXDB_TOKEN=your-influxdb-token
INFLUXDB_ORG=your-org-name
```

### Config File

```bash
# Copy example config
cp config/config.example.yaml config/config.yaml

# Edit config
vim config/config.yaml

# Validate config
python -c "from overwatch_mcp.config import load_config; load_config('config/config.yaml')"
```

## Quick Deployment

### Deploy to Docker Host

```bash
# 1. Pull latest image
docker pull ghcr.io/ftsgps/overwatch-mcp:latest

# 2. Create config directory
mkdir -p ~/overwatch-mcp/config

# 3. Copy config file
cp config/config.yaml ~/overwatch-mcp/config/

# 4. Create .env file
cat > ~/overwatch-mcp/.env << EOF
GRAYLOG_URL=https://graylog.internal:9000/api
GRAYLOG_TOKEN=your-token
PROMETHEUS_URL=http://prometheus.internal:9090
INFLUXDB_URL=https://influxdb.internal:8086
INFLUXDB_TOKEN=your-token
INFLUXDB_ORG=your-org
EOF

# 5. Run container
docker run -d \
  --name overwatch-mcp \
  --restart unless-stopped \
  -v ~/overwatch-mcp/config:/app/config:ro \
  --env-file ~/overwatch-mcp/.env \
  ghcr.io/ftsgps/overwatch-mcp:latest
```

## Troubleshooting

### Image Build Fails

```bash
# Check Docker daemon
docker info

# Clean build cache
docker builder prune -a

# Check Dockerfile syntax
docker build --check .

# Build with verbose output
docker build --progress=plain -t overwatch-mcp:latest .
```

### Container Won't Start

```bash
# Check logs
docker logs overwatch-mcp

# Check container status
docker ps -a | grep overwatch-mcp

# Inspect container
docker inspect overwatch-mcp | grep -A 10 State

# Test configuration
docker run --rm \
  -v $(pwd)/config:/app/config:ro \
  --env-file .env \
  overwatch-mcp:latest --help
```

### Permission Issues

```bash
# Fix config file permissions
chmod 644 config/config.yaml

# Run as specific user
docker run --rm \
  --user $(id -u):$(id -g) \
  -v $(pwd)/config:/app/config:ro \
  --env-file .env \
  overwatch-mcp:latest
```

## Performance Tuning

### Container Resources

```bash
# Limit CPU and memory
docker run --rm \
  --cpus=1 \
  --memory=512m \
  -v $(pwd)/config:/app/config:ro \
  --env-file .env \
  overwatch-mcp:latest

# Check resource usage
docker stats overwatch-mcp
```

### Image Size Optimization

```bash
# Check image size
docker images overwatch-mcp

# Remove unnecessary layers
docker history overwatch-mcp:latest

# Use slim base image (already configured)
# Use multi-stage builds for smaller images
```

## Useful Docker Commands

```bash
# Remove stopped containers
docker container prune

# Remove unused images
docker image prune -a

# Remove all overwatch-mcp resources
docker ps -a | grep overwatch-mcp | awk '{print $1}' | xargs docker rm -f
docker images | grep overwatch-mcp | awk '{print $3}' | xargs docker rmi -f

# Export image as tar
docker save overwatch-mcp:latest | gzip > overwatch-mcp-latest.tar.gz

# Import image from tar
docker load < overwatch-mcp-latest.tar.gz

# Copy files from container
docker cp overwatch-mcp:/app/logs ./logs
```

## CI/CD Pipeline Status

Check pipeline status:
- GitHub Actions: https://github.com/ftsgps/overwatch-mcp/actions
- Container Registry: https://github.com/ftsgps/overwatch-mcp/pkgs/container/overwatch-mcp

## Version Management

```bash
# Current version
docker run --rm overwatch-mcp:latest --version

# List all tags
docker images overwatch-mcp --format "{{.Tag}}"

# Tag management
docker tag overwatch-mcp:latest overwatch-mcp:1.0.0
docker tag overwatch-mcp:latest overwatch-mcp:stable
```
