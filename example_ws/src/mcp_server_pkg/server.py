"""
Example MCP Server: Weather Service over Tagentacle Bus.

This demonstrates how to run an MCP Server that serves tools over the
Tagentacle message bus using TagentacleServerTransport.

The server provides a "get_weather" tool that returns mock weather data.
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tagentacle_py import Node
from tagentacle_py.mcp import tagentacle_server_transport

from mcp.server.lowlevel import Server
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP Server with tool definitions
mcp_server = Server("weather-server")


@mcp_server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_weather",
            description="Get current weather for a given city (mock data)",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name"
                    }
                },
                "required": ["city"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "get_weather":
        city = arguments.get("city", "Unknown")
        # Mock weather data
        weather = {
            "Shenzhen": "32°C, Sunny",
            "Beijing": "15°C, Cloudy",
            "Tokyo": "22°C, Clear",
            "London": "12°C, Rainy",
            "New York": "18°C, Partly Cloudy",
        }
        result = weather.get(city, f"25°C, Fair (no data for {city})")
        return [TextContent(type="text", text=f"Weather in {city}: {result}")]
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    node = Node("mcp_server_node")
    await node.connect()
    spin_task = asyncio.create_task(node.spin())

    logger.info("Starting Weather MCP Server over Tagentacle bus...")

    async with tagentacle_server_transport(node) as (read_stream, write_stream):
        # Run the MCP server with the bus-backed transport
        await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())

    spin_task.cancel()
    try:
        await spin_task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
