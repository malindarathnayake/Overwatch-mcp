#!/bin/bash
# Overwatch MCP - Quick Setup Script
# Downloads all necessary files to deploy Overwatch MCP
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/setup.sh | bash
#
# Or download and run:
#   curl -O https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/setup.sh
#   chmod +x setup.sh && ./setup.sh

set -e

REPO_BASE="https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose"
DIR="Overwatch_MCP"

echo "==> Creating $DIR directory..."
mkdir -p "$DIR"
cd "$DIR"

echo "==> Downloading docker-compose.yml..."
curl -fsSL "$REPO_BASE/docker-compose.yml" -o docker-compose.yml

echo "==> Downloading .env.example..."
curl -fsSL "$REPO_BASE/.env.example" -o .env.example

echo "==> Downloading config.example.yaml..."
curl -fsSL "$REPO_BASE/config.example.yaml" -o config.example.yaml

echo "==> Creating .env and config.yaml from templates..."
cp .env.example .env
cp config.example.yaml config.yaml

echo ""
echo "=============================================="
echo "  Setup complete!"
echo "=============================================="
echo ""
echo "Files created in: $(pwd)"
echo ""
echo "NEXT STEPS:"
echo ""
echo "  1. Edit .env with your credentials:"
echo "     nano .env"
echo ""
echo "  2. Edit config.yaml if needed:"
echo "     nano config.yaml"
echo ""
echo "  3. Run the container:"
echo ""
echo "     # For Claude Desktop (interactive MCP):"
echo "     docker compose run --rm overwatch-mcp"
echo ""
echo "     # As a background service:"
echo "     docker compose up -d"
echo ""
echo "OPTIONAL - Expose a port (if needed):"
echo "     docker compose run --rm -p 8080:8080 overwatch-mcp"
echo ""
echo "     Port format: HOST_PORT:CONTAINER_PORT"
echo "                  ├─────────┘ └──────────┘"
echo "                  │          Fixed (don't change)"
echo "                  └── Change this if port 8080 is in use"
echo ""
echo "     Example: Use port 9000 instead:"
echo "     docker compose run --rm -p 9000:8080 overwatch-mcp"
echo ""
echo "     Or edit docker-compose.yml and add:"
echo "       ports:"
echo "         - \"9000:8080\"  # HOST:CONTAINER\""
echo ""
echo "For debug logging, set LOG_LEVEL=debug in .env"
