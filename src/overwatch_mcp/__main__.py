"""Entry point for overwatch-mcp server."""

import argparse
import asyncio
import logging
import sys

from overwatch_mcp.server import main

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="overwatch-mcp",
        description="MCP server providing Claude Desktop access to Graylog, Prometheus, and InfluxDB",
    )
    parser.add_argument(
        "--config",
        "-c",
        default="config/config.yaml",
        help="Path to configuration file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="overwatch-mcp 1.0.0",
    )
    return parser.parse_args()


def main_sync() -> None:
    """Synchronous entry point."""
    args = parse_args()

    try:
        asyncio.run(main(config_path=args.config))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main_sync()
