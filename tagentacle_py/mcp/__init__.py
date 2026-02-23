"""
Tagentacle MCP Integration: Bus-as-Transport Layer.

Provides transport adapters that bridge MCP JSON-RPC sessions over the
Tagentacle message bus, enabling distributed MCP tool calling with
dual-track observability.
"""

from tagentacle_py.mcp.transport import (
    tagentacle_client_transport,
    tagentacle_server_transport,
    TagentacleClientTransport,
    TagentacleServerTransport,
    MCP_TRAFFIC_TOPIC,
)
from tagentacle_py.mcp.publish_bridge import MCPPublishBridge

__all__ = [
    "tagentacle_client_transport",
    "tagentacle_server_transport",
    "TagentacleClientTransport",
    "TagentacleServerTransport",
    "MCPPublishBridge",
    "MCP_TRAFFIC_TOPIC",
]
