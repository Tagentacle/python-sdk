"""
MCP-Publish Bridge Node: Pre-built MCP Server that exposes bus publish() as MCP Tools.

This node acts as a bridge between MCP-compatible Agent Nodes and the Tagentacle
message bus. It registers itself as an MCP Server and provides a "publish_to_topic"
tool, allowing agents to autonomously send messages to any bus Topic through
standard MCP tool calls.

Architecture reference: NEW_ARCHITECTURE.md §4.3
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from tagentacle_py import Node

logger = logging.getLogger("tagentacle.mcp.publish_bridge")


class MCPPublishBridge:
    """Pre-built MCP Server Node that bridges MCP tool calls to bus publish().

    When an Agent calls the "publish_to_topic" MCP tool, this bridge node
    publishes the payload to the specified Tagentacle bus Topic.

    Usage:
        bridge = MCPPublishBridge("publish_bridge_node")
        await bridge.start()
        # Now any MCP client can call tools/call with:
        # {"name": "publish_to_topic", "arguments": {"topic": "/alerts", "payload": {"msg": "hello"}}}
    """

    def __init__(self, node_id: str = "mcp_publish_bridge",
                 allowed_topics: Optional[list] = None):
        """
        Args:
            node_id: Node ID for the bridge on the Tagentacle bus.
            allowed_topics: If set, only allow publishing to these topic prefixes.
                           If None, all topics are allowed.
        """
        self.node = Node(node_id)
        self.allowed_topics = allowed_topics
        self._tools = self._build_tool_definitions()

    def _build_tool_definitions(self):
        """Build MCP tool definitions for the publish bridge."""
        return [
            {
                "name": "publish_to_topic",
                "description": "Publish a JSON message to a Tagentacle bus Topic. "
                               "Other nodes subscribed to that topic will receive the message.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "The topic path to publish to (e.g., '/alerts/critical')"
                        },
                        "payload": {
                            "type": "object",
                            "description": "The JSON payload to publish"
                        }
                    },
                    "required": ["topic", "payload"]
                }
            },
            {
                "name": "list_available_topics",
                "description": "List the topics that this bridge is allowed to publish to. "
                               "Returns 'all' if there are no restrictions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    async def start(self):
        """Connect to bus and register MCP RPC service."""
        await self.node.connect()
        rpc_service = f"/mcp/{self.node.node_id}/rpc"

        @self.node.service(rpc_service)
        async def handle_rpc(payload: Dict[str, Any]):
            return await self._handle_jsonrpc(payload)

        logger.info(f"MCP-Publish Bridge ready on {rpc_service}")
        logger.info(f"Available tools: {[t['name'] for t in self._tools]}")

    async def run(self):
        """Start and spin (blocking)."""
        await self.start()
        await self.node.spin()

    async def _handle_jsonrpc(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process inbound JSON-RPC requests (MCP protocol)."""
        method = payload.get("method", "")
        rpc_id = payload.get("id")
        params = payload.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": "tagentacle-publish-bridge",
                        "version": "0.1.0"
                    }
                }
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"tools": self._tools}
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            return await self._call_tool(rpc_id, tool_name, arguments)

        elif method == "notifications/initialized":
            # Notification, no response needed
            return None

        else:
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    async def _call_tool(self, rpc_id, tool_name: str, arguments: dict):
        """Execute an MCP tool call."""
        try:
            if tool_name == "publish_to_topic":
                topic = arguments.get("topic", "")
                payload = arguments.get("payload", {})

                # Check topic allowlist
                if self.allowed_topics is not None:
                    if not any(topic.startswith(prefix) for prefix in self.allowed_topics):
                        return {
                            "jsonrpc": "2.0",
                            "id": rpc_id,
                            "result": {
                                "content": [{"type": "text",
                                             "text": f"Error: Topic '{topic}' is not in the allow-list."}],
                                "isError": True
                            }
                        }

                await self.node.publish(topic, payload)
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "content": [{"type": "text",
                                     "text": f"Published to '{topic}' successfully."}]
                    }
                }

            elif tool_name == "list_available_topics":
                if self.allowed_topics is None:
                    topics_info = "All topics are allowed (no restrictions)."
                else:
                    topics_info = f"Allowed topic prefixes: {self.allowed_topics}"
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "content": [{"type": "text", "text": topics_info}]
                    }
                }

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                }

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True
                }
            }


async def main():
    """Standalone entrypoint for the MCP-Publish Bridge."""
    import sys
    logging.basicConfig(level=logging.INFO)

    allowed = None
    if len(sys.argv) > 1:
        # Optional: pass allowed topic prefixes as args
        allowed = sys.argv[1:]
        logger.info(f"Topic allow-list: {allowed}")

    bridge = MCPPublishBridge(allowed_topics=allowed)
    await bridge.run()


if __name__ == "__main__":
    asyncio.run(main())
