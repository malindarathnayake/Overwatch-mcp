#!/bin/bash
# Overwatch MCP - Quick Setup Script
# Downloads all necessary files to deploy Overwatch MCP
#
# Usage:
#   Fresh install:
#     curl -fsSL https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/setup.sh | bash
#
#   Upgrade existing installation:
#     curl -fsSL https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/setup.sh | bash -s -- --upgrade
#
#   Or download and run:
#     curl -O https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose/setup.sh
#     chmod +x setup.sh && ./setup.sh [--upgrade]

set -e

REPO_BASE="https://raw.githubusercontent.com/malindarathnayake/Overwatch-mcp/main/compose"
DIR="Overwatch_MCP"
UPGRADE=false
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --upgrade|-u)
            UPGRADE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--upgrade]"
            exit 1
            ;;
    esac
done

if [ "$UPGRADE" = true ]; then
    # Upgrade mode
    if [ ! -d "$DIR" ]; then
        echo "ERROR: Directory $DIR not found. Run without --upgrade for fresh install."
        exit 1
    fi
    
    cd "$DIR"
    
    echo "=============================================="
    echo "  Overwatch MCP - UPGRADE MODE"
    echo "=============================================="
    echo ""
    
    # Backup existing files
    BACKUP_DIR="backup_$TIMESTAMP"
    echo "==> Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    
    if [ -f ".env" ]; then
        echo "==> Backing up .env -> $BACKUP_DIR/.env"
        cp .env "$BACKUP_DIR/.env"
    fi
    
    if [ -f "config.yaml" ]; then
        echo "==> Backing up config.yaml -> $BACKUP_DIR/config.yaml"
        cp config.yaml "$BACKUP_DIR/config.yaml"
    fi
    
    if [ -f "docker-compose.yml" ]; then
        echo "==> Backing up docker-compose.yml -> $BACKUP_DIR/docker-compose.yml"
        cp docker-compose.yml "$BACKUP_DIR/docker-compose.yml"
    fi
    
    echo ""
    echo "==> Downloading latest docker-compose.yml..."
    curl -fsSL "$REPO_BASE/docker-compose.yml" -o docker-compose.yml
    
    echo "==> Downloading latest .env.example..."
    curl -fsSL "$REPO_BASE/.env.example" -o .env.example
    
    echo "==> Downloading latest config.example.yaml..."
    curl -fsSL "$REPO_BASE/config.example.yaml" -o config.example.yaml
    
    echo ""
    echo "=============================================="
    echo "  UPGRADE COMPLETE!"
    echo "=============================================="
    echo ""
    echo "Backups saved to: $(pwd)/$BACKUP_DIR/"
    echo ""
    echo "IMPORTANT: Your .env and config.yaml were NOT overwritten."
    echo ""
    echo "If there are new config options, you need to manually add them:"
    echo ""
    echo "  1. Compare your files with the new templates:"
    echo "     diff .env .env.example"
    echo "     diff config.yaml config.example.yaml"
    echo ""
    echo "  2. Add any new options to your existing files"
    echo ""
    echo "  3. Restart the container:"
    echo "     docker compose down"
    echo "     docker compose pull"
    echo "     docker compose up -d"
    echo ""
    echo "To restore from backup if something breaks:"
    echo "     cp $BACKUP_DIR/.env .env"
    echo "     cp $BACKUP_DIR/config.yaml config.yaml"
    echo ""
    
else
    # Fresh install mode
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
fi
