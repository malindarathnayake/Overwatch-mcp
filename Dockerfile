# Overwatch MCP Server - Production Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (better caching)
COPY pyproject.toml ./
COPY README.md ./

# Create necessary directories
RUN mkdir -p config src/overwatch_mcp

# Copy source code
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create non-root user for security
RUN useradd -m -u 1000 overwatch && \
    chown -R overwatch:overwatch /app

# Switch to non-root user
USER overwatch

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose SSE port (used when running with --transport sse)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command - can be overridden
# Use --transport sse --port 8080 for HTTP/SSE mode
ENTRYPOINT ["python", "-m", "overwatch_mcp"]
CMD ["--config", "/app/config/config.yaml"]

# Metadata
LABEL maintainer="malinda@rathnayake.net" \
      description="MCP server for Graylog, Prometheus, and InfluxDB observability" \
      version="1.0.0"
