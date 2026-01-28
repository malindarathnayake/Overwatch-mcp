"""MCP server for observability tools."""

import asyncio
import logging
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from overwatch_mcp.cache import Cache, CacheManager
from overwatch_mcp.clients.graylog import GraylogClient
from overwatch_mcp.clients.influxdb import InfluxDBClient
from overwatch_mcp.clients.prometheus import PrometheusClient
from overwatch_mcp.config import load_config
from overwatch_mcp.models.config import Config
from overwatch_mcp.models.errors import OverwatchError
from overwatch_mcp.tools import graylog, influxdb, prometheus

logger = logging.getLogger(__name__)

# Transport mode constants
TRANSPORT_STDIO = "stdio"
TRANSPORT_SSE = "sse"


class OverwatchMCPServer:
    """MCP server for observability datasources."""

    def __init__(self, config: Config):
        """
        Initialize MCP server.

        Args:
            config: Server configuration
        """
        self.config = config
        self.server = Server("overwatch-mcp")

        # Initialize cache manager
        self.cache_manager = CacheManager(
            default_ttl=config.cache.default_ttl_seconds,
            ttl_overrides=config.cache.ttl_overrides,
        )

        # Initialize clients (None if datasource disabled)
        self.graylog_client: GraylogClient | None = None
        self.prometheus_client: PrometheusClient | None = None
        self.influxdb_client: InfluxDBClient | None = None

        # Track datasource availability
        self.datasource_available: dict[str, bool] = {}

    async def initialize_clients(self) -> None:
        """
        Initialize datasource clients and perform health checks.

        Logs warnings for failed health checks but continues with available datasources.
        Exits if no datasources are available.
        """
        logger.info("Initializing datasource clients...")

        # Initialize Graylog
        if self.config.datasources.graylog and self.config.datasources.graylog.enabled:
            try:
                self.graylog_client = GraylogClient(self.config.datasources.graylog)
                is_healthy = await self.graylog_client.health_check()
                self.datasource_available["graylog"] = is_healthy

                if is_healthy:
                    logger.info("✓ Graylog client initialized and healthy")
                else:
                    logger.warning("⚠ Graylog client initialized but health check failed")
            except Exception as e:
                logger.error(f"✗ Failed to initialize Graylog client: {e}")
                self.datasource_available["graylog"] = False

        # Initialize Prometheus
        if self.config.datasources.prometheus and self.config.datasources.prometheus.enabled:
            try:
                self.prometheus_client = PrometheusClient(self.config.datasources.prometheus)
                is_healthy = await self.prometheus_client.health_check()
                self.datasource_available["prometheus"] = is_healthy

                if is_healthy:
                    logger.info("✓ Prometheus client initialized and healthy")
                else:
                    logger.warning("⚠ Prometheus client initialized but health check failed")
            except Exception as e:
                logger.error(f"✗ Failed to initialize Prometheus client: {e}")
                self.datasource_available["prometheus"] = False

        # Initialize InfluxDB
        if self.config.datasources.influxdb and self.config.datasources.influxdb.enabled:
            try:
                self.influxdb_client = InfluxDBClient(self.config.datasources.influxdb)
                is_healthy = await self.influxdb_client.health_check()
                self.datasource_available["influxdb"] = is_healthy

                if is_healthy:
                    logger.info("✓ InfluxDB client initialized and healthy")
                else:
                    logger.warning("⚠ InfluxDB client initialized but health check failed")
            except Exception as e:
                logger.error(f"✗ Failed to initialize InfluxDB client: {e}")
                self.datasource_available["influxdb"] = False

        # Check if at least one datasource is available
        available_count = sum(1 for available in self.datasource_available.values() if available)
        if available_count == 0:
            logger.error("No datasources are available. Exiting.")
            raise RuntimeError("No datasources available")

        logger.info(f"Server initialized with {available_count} available datasource(s)")

    def register_tools(self) -> None:
        """Register MCP tools for available datasources."""
        logger.info("Registering MCP tools...")

        # Create unified tool list and call handlers
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List all available tools."""
            tools = []

            if self.graylog_client:
                tools.extend(await self._list_graylog_tools())

            if self.prometheus_client:
                tools.extend(await self._list_prometheus_tools())

            if self.influxdb_client:
                tools.extend(await self._list_influxdb_tools())

            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Call a tool by name."""
            # Graylog tools
            if name in ["graylog_search", "graylog_fields"]:
                return await self._call_graylog_tool(name, arguments)

            # Prometheus tools
            elif name in ["prometheus_query", "prometheus_query_range", "prometheus_metrics"]:
                return await self._call_prometheus_tool(name, arguments)

            # InfluxDB tools
            elif name == "influxdb_query":
                return await self._call_influxdb_tool(name, arguments)

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        tool_count = sum([
            2 if self.graylog_client else 0,
            3 if self.prometheus_client else 0,
            1 if self.influxdb_client else 0,
        ])
        logger.info(f"Registered {tool_count} MCP tools")

    async def _list_graylog_tools(self) -> list[Tool]:
        """List available Graylog tools."""
        return [
            Tool(
                name="graylog_search",
                description="Search Graylog logs with query string and time range",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Graylog search query (Lucene syntax)"
                        },
                        "from_time": {
                            "type": "string",
                            "description": "Start time (ISO8601 or relative: '-1h', '-30m'). Default: '-1h'",
                            "default": "-1h"
                        },
                        "to_time": {
                            "type": "string",
                            "description": "End time (ISO8601 or relative: 'now'). Default: 'now'",
                            "default": "now"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results. Default: 100, Max: 1000",
                            "default": 100
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Fields to return. Default: all"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="graylog_fields",
                description="List available fields in Graylog logs, optionally filtered by pattern",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regex pattern to filter field names (e.g., 'http_.*', 'error')"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max fields to return. Default: 100, Max: 500",
                            "default": 100
                        }
                    }
                }
            )
        ]

    async def _call_graylog_tool(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Call a Graylog tool."""
        if not self.datasource_available.get("graylog", False):
            error_msg = "Graylog datasource is not available"
            logger.warning(f"Tool call rejected: {error_msg}")
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        try:
            cache = self.cache_manager.get_cache("graylog_fields")

            if name == "graylog_search":
                result = await graylog.graylog_search(
                    client=self.graylog_client,
                    config=self.config.datasources.graylog,
                    cache=cache,
                    query=arguments["query"],
                    from_time=arguments.get("from_time", "-1h"),
                    to_time=arguments.get("to_time", "now"),
                    limit=arguments.get("limit"),
                    fields=arguments.get("fields"),
                )
            elif name == "graylog_fields":
                result = await graylog.graylog_fields(
                    client=self.graylog_client,
                    config=self.config.datasources.graylog,
                    cache=cache,
                    pattern=arguments.get("pattern"),
                    limit=arguments.get("limit", 100),
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except OverwatchError as e:
            logger.error(f"Tool error: {e.message}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {e.message}")]
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return [TextContent(type="text", text=f"Unexpected error: {str(e)}")]

    async def _list_prometheus_tools(self) -> list[Tool]:
        """List available Prometheus tools."""
        return [
            Tool(
                name="prometheus_query",
                description="Execute instant PromQL query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "PromQL expression"
                        },
                        "time": {
                            "type": "string",
                            "description": "Evaluation time (ISO8601, Unix, or relative). Default: now"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="prometheus_query_range",
                description="Execute PromQL range query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "PromQL expression"
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time (ISO8601, Unix, or relative: '-1h')"
                        },
                        "end": {
                            "type": "string",
                            "description": "End time (ISO8601, Unix, or relative: 'now')"
                        },
                        "step": {
                            "type": "string",
                            "description": "Query resolution (e.g., '15s', '1m', '1h'). Auto-calculated if not provided"
                        }
                    },
                    "required": ["query", "start", "end"]
                }
            ),
            Tool(
                name="prometheus_metrics",
                description="List available metric names, optionally filtered by pattern",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regex pattern to filter metric names (e.g., 'http_.*', 'cpu')"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max metrics to return. Default: 100, Max: 500",
                            "default": 100
                        }
                    }
                }
            )
        ]

    async def _call_prometheus_tool(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Call a Prometheus tool."""
        if not self.datasource_available.get("prometheus", False):
            error_msg = "Prometheus datasource is not available"
            logger.warning(f"Tool call rejected: {error_msg}")
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        try:
            cache = self.cache_manager.get_cache("prometheus_metrics")

            if name == "prometheus_query":
                result = await prometheus.prometheus_query(
                    client=self.prometheus_client,
                    config=self.config.datasources.prometheus,
                    cache=cache,
                    query=arguments["query"],
                    time=arguments.get("time"),
                )
            elif name == "prometheus_query_range":
                result = await prometheus.prometheus_query_range(
                    client=self.prometheus_client,
                    config=self.config.datasources.prometheus,
                    cache=cache,
                    query=arguments["query"],
                    start=arguments["start"],
                    end=arguments["end"],
                    step=arguments.get("step"),
                )
            elif name == "prometheus_metrics":
                result = await prometheus.prometheus_metrics(
                    client=self.prometheus_client,
                    config=self.config.datasources.prometheus,
                    cache=cache,
                    pattern=arguments.get("pattern"),
                    limit=arguments.get("limit", 100),
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except OverwatchError as e:
            logger.error(f"Tool error: {e.message}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {e.message}")]
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return [TextContent(type="text", text=f"Unexpected error: {str(e)}")]

    async def _list_influxdb_tools(self) -> list[Tool]:
        """List available InfluxDB tools."""
        return [
            Tool(
                name="influxdb_query",
                description="Execute Flux query against InfluxDB 2.x",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Flux query"
                        },
                        "bucket": {
                            "type": "string",
                            "description": "Target bucket (must be in allowed_buckets)"
                        }
                    },
                    "required": ["query", "bucket"]
                }
            )
        ]

    async def _call_influxdb_tool(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Call an InfluxDB tool."""
        if not self.datasource_available.get("influxdb", False):
            error_msg = "InfluxDB datasource is not available"
            logger.warning(f"Tool call rejected: {error_msg}")
            return [TextContent(type="text", text=f"Error: {error_msg}")]

        try:
            cache = self.cache_manager.get_cache("influxdb")

            if name == "influxdb_query":
                result = await influxdb.influxdb_query(
                    client=self.influxdb_client,
                    config=self.config.datasources.influxdb,
                    cache=cache,
                    query=arguments["query"],
                    bucket=arguments["bucket"],
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except OverwatchError as e:
            logger.error(f"Tool error: {e.message}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {e.message}")]
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return [TextContent(type="text", text=f"Unexpected error: {str(e)}")]

    async def run(self, transport: str = TRANSPORT_STDIO, host: str = "0.0.0.0", port: int = 8080) -> None:
        """
        Run the MCP server.
        
        Args:
            transport: Transport mode ('stdio' or 'sse')
            host: Host to bind for SSE mode
            port: Port to bind for SSE mode
        """
        await self.initialize_clients()
        self.register_tools()

        if transport == TRANSPORT_SSE:
            await self._run_sse(host, port)
        else:
            await self._run_stdio()

    async def _run_stdio(self) -> None:
        """Run server with stdio transport."""
        logger.info("Starting MCP server on stdio...")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )

    async def _run_sse(self, host: str, port: int) -> None:
        """Run server with SSE transport over HTTP."""
        from starlette.applications import Starlette
        from starlette.routing import Route, Mount
        from starlette.responses import JSONResponse
        from mcp.server.sse import SseServerTransport
        import uvicorn

        # Create SSE transport
        sse_transport = SseServerTransport("/messages/")

        async def handle_sse(request):
            """Handle SSE connection."""
            async with sse_transport.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await self.server.run(
                    streams[0],
                    streams[1],
                    self.server.create_initialization_options()
                )

        async def handle_messages(request):
            """Handle incoming messages."""
            await sse_transport.handle_post_message(
                request.scope, request.receive, request._send
            )

        async def health_check(request):
            """Health check endpoint."""
            return JSONResponse({
                "status": "healthy",
                "datasources": self.datasource_available,
                "transport": "sse"
            })

        # Create Starlette app
        app = Starlette(
            debug=False,
            routes=[
                Route("/health", health_check, methods=["GET"]),
                Route("/sse", handle_sse, methods=["GET"]),
                Route("/messages/", handle_messages, methods=["POST"]),
            ]
        )

        logger.info(f"Starting MCP server on http://{host}:{port}")
        logger.info(f"  SSE endpoint: http://{host}:{port}/sse")
        logger.info(f"  Health check: http://{host}:{port}/health")

        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        server = uvicorn.Server(config)
        await server.serve()


async def main(
    config_path: str = "config/config.yaml",
    transport: str = TRANSPORT_STDIO,
    host: str = "0.0.0.0",
    port: int = 8080
) -> None:
    """
    Main entry point for the MCP server.

    Args:
        config_path: Path to configuration file
        transport: Transport mode ('stdio' or 'sse')
        host: Host to bind for SSE mode
        port: Port to bind for SSE mode
    """
    # Set up logging - use LOG_LEVEL env var (default: info)
    log_level = os.environ.get("LOG_LEVEL", "info").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        # Load configuration
        logger.info(f"Loading configuration from {config_path}")
        config = load_config(config_path)

        # Create and run server
        server = OverwatchMCPServer(config)
        await server.run(transport=transport, host=host, port=port)

    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
