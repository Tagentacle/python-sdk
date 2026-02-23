"""
Tagentacle MCP Transport: Bus-as-Transport Layer

Provides TagentacleClientTransport and TagentacleServerTransport that bridge
MCP JSON-RPC sessions over the Tagentacle message bus using Service calls.

Design principles (from NEW_ARCHITECTURE.md §5):
  - Session Localization: MCP Client/Server Sessions stay in node memory.
  - Bus Traffic Forwarding: JSON-RPC wrapped in Tagentacle Service requests.
  - Dual-Track Integration: Traffic mirrored to /mcp/traffic Topic.
"""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from mcp.types import JSONRPCMessage
from mcp.shared.message import SessionMessage

logger = logging.getLogger("tagentacle.mcp.transport")

# Audit topic for dual-track observability
MCP_TRAFFIC_TOPIC = "/mcp/traffic"


@asynccontextmanager
async def tagentacle_client_transport(node, server_node_id: str):
    """Client-side MCP transport over Tagentacle bus.

    Wraps outbound JSON-RPC messages into Tagentacle Service calls to
    /mcp/{server_node_id}/rpc, and receives responses back through the
    bus's service response mechanism.

    Usage:
        async with tagentacle_client_transport(node, "mcp_server") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()

    Args:
        node: A connected tagentacle_py.Node instance.
        server_node_id: The node_id of the target MCP server node.
    """
    rpc_service = f"/mcp/{server_node_id}/rpc"

    # Create memory stream pairs for MCP Session
    # read_stream: Session reads responses/notifications FROM server
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]

    # write_stream: Session writes requests/notifications TO server
    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream[SessionMessage | Exception](0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream[SessionMessage](0)

    async def outbound_pump():
        """Pump: write_stream -> Tagentacle Service call -> read_stream."""
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    jsonrpc_raw = session_message.message.model_dump_json(
                        by_alias=True, exclude_none=True
                    )
                    jsonrpc_payload = json.loads(jsonrpc_raw)

                    # Mirror to audit topic (dual-track)
                    try:
                        await node.publish(MCP_TRAFFIC_TOPIC, {
                            "direction": "client_to_server",
                            "server": server_node_id,
                            "data": jsonrpc_payload,
                        })
                    except Exception:
                        pass  # Audit is best-effort

                    try:
                        # Send via Tagentacle Service call
                        response_payload = await node.call_service(
                            rpc_service, jsonrpc_payload
                        )

                        if response_payload is not None:
                            # Mirror response to audit topic
                            try:
                                await node.publish(MCP_TRAFFIC_TOPIC, {
                                    "direction": "server_to_client",
                                    "server": server_node_id,
                                    "data": response_payload,
                                })
                            except Exception:
                                pass

                            # Parse and send to read_stream
                            try:
                                msg = JSONRPCMessage.model_validate(response_payload)
                                await read_stream_writer.send(SessionMessage(msg))
                            except Exception as exc:
                                logger.error(f"Failed to parse server response: {exc}")
                                await read_stream_writer.send(exc)
                    except Exception as exc:
                        logger.error(f"Service call to {rpc_service} failed: {exc}")
                        await read_stream_writer.send(exc)
        except anyio.ClosedResourceError:
            pass

    async with anyio.create_task_group() as tg:
        tg.start_soon(outbound_pump)
        try:
            yield read_stream, write_stream
        finally:
            tg.cancel_scope.cancel()
            await read_stream.aclose()
            await write_stream.aclose()
            await read_stream_writer.aclose()


# Backward-compatible alias
TagentacleClientTransport = tagentacle_client_transport


@asynccontextmanager
async def tagentacle_server_transport(node, server_node_id: Optional[str] = None):
    """Server-side MCP transport over Tagentacle bus.

    Registers a Tagentacle Service at /mcp/{server_node_id}/rpc and bridges
    inbound JSON-RPC requests to the local MCP Server Session, forwarding
    responses back through Service responses.

    Usage:
        async with tagentacle_server_transport(node) as (read, write):
            async with ServerSession(read, write) as session:
                # session handles tool calls etc.
                ...

    Args:
        node: A connected tagentacle_py.Node instance.
        server_node_id: Override node_id for service registration (default: node.node_id).
    """
    effective_id = server_node_id or node.node_id
    rpc_service = f"/mcp/{effective_id}/rpc"

    # Create memory stream pairs for MCP ServerSession
    # read_stream: ServerSession reads requests FROM clients
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]

    # write_stream: ServerSession writes responses TO clients
    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream[SessionMessage | Exception](0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream[SessionMessage](0)

    # Pending request tracking: maps JSON-RPC id -> (request_id, caller_id)
    # so we can route ServerSession responses back to the correct bus caller
    pending_rpc: dict[str, tuple[str, str]] = {}

    async def handle_rpc_request(payload):
        """Service handler: receives JSON-RPC from bus, pushes to ServerSession."""
        # payload is the raw JSON-RPC message from the client
        try:
            msg = JSONRPCMessage.model_validate(payload)
            await read_stream_writer.send(SessionMessage(msg))
        except Exception as exc:
            logger.error(f"Failed to parse inbound JSON-RPC: {exc}")
            return {"jsonrpc": "2.0", "error": {"code": -32700, "message": str(exc)}}

        # For requests (have 'id'), wait for the response from write_stream
        if "id" in payload:
            rpc_id = str(payload["id"])
            response_future = asyncio.get_running_loop().create_future()
            pending_rpc[rpc_id] = response_future
            try:
                result = await asyncio.wait_for(response_future, timeout=60.0)
                return result
            except asyncio.TimeoutError:
                pending_rpc.pop(rpc_id, None)
                return {"jsonrpc": "2.0", "id": payload["id"],
                        "error": {"code": -32000, "message": "Server timeout"}}
        else:
            # Notification - no response expected
            return None

    async def outbound_pump():
        """Pump: ServerSession write_stream -> resolve pending RPC futures."""
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    response_raw = session_message.message.model_dump(
                        by_alias=True, exclude_none=True
                    )

                    # Mirror to audit topic
                    try:
                        await node.publish(MCP_TRAFFIC_TOPIC, {
                            "direction": "server_to_client",
                            "server": effective_id,
                            "data": response_raw,
                        })
                    except Exception:
                        pass

                    # Route response back to the pending future
                    rpc_id = str(response_raw.get("id", ""))
                    if rpc_id in pending_rpc:
                        future = pending_rpc.pop(rpc_id)
                        if not future.done():
                            future.set_result(response_raw)
        except anyio.ClosedResourceError:
            pass

    # Register the RPC service on the bus
    @node.service(rpc_service)
    async def _rpc_handler(payload):
        return await handle_rpc_request(payload)

    async with anyio.create_task_group() as tg:
        tg.start_soon(outbound_pump)
        try:
            yield read_stream, write_stream
        finally:
            tg.cancel_scope.cancel()
            await read_stream.aclose()
            await write_stream.aclose()
            await read_stream_writer.aclose()


# Backward-compatible alias
TagentacleServerTransport = tagentacle_server_transport
