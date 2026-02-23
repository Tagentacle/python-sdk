# mcp_server_pkg

An example **MCP Server Node** that exposes tools over the Tagentacle message bus.

## What it does

1. Connects to the Tagentacle Daemon as `mcp_server_node`
2. Registers an MCP Server with a `get_weather` tool (mock data)
3. Serves incoming MCP JSON-RPC requests via `tagentacle_server_transport`
4. Stays running until terminated

## Supported Tools

| Tool | Input | Output |
|------|-------|--------|
| `get_weather` | `{"city": "Shenzhen"}` | `"Weather in Shenzhen: 32°C, Sunny"` |

Supported cities: Shenzhen, Beijing, Tokyo, London, New York (others return a default).

## Prerequisites

- Tagentacle Daemon running (`tagentacle daemon`)

## Run

```bash
# Standalone
cd examples/mcp_server_pkg
python server.py

# Via CLI (from workspace root)
tagentacle run --pkg examples/mcp_server_pkg
```

## Files

| File | Description |
|------|-------------|
| `server.py` | MCP Server entry point with `get_weather` tool |
| `tagentacle.toml` | Package manifest (type: executable) |

## Key Concepts

- **`tagentacle_server_transport`**: Registers a Tagentacle Service at `/mcp/{node_id}/rpc` and bridges inbound JSON-RPC to the local MCP `Server` instance.
- **Standard MCP SDK**: Uses `mcp.server.lowlevel.Server` with `@server.list_tools()` and `@server.call_tool()` decorators — no bus-specific code in tool implementations.
