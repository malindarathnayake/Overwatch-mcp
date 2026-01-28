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
echo "==> Setup complete!"
echo ""
echo "Next steps:"
echo "  1. cd $DIR"
echo "  2. Edit .env with your credentials"
echo "  3. Edit config.yaml if needed (adjust allowed_buckets, etc.)"
echo "  4. docker compose up -d"
echo ""
echo "For debug logging, set LOG_LEVEL=debug in .env"
