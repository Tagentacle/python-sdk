# Tagentacle Python SDK

> **ROS for AI Agent** — A lightweight message bus SDK for building multi-agent systems with native MCP integration.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Tagentacle Python SDK provides a dual-layer API for connecting Python programs to the [Tagentacle](https://github.com/Tagentacle/tagentacle) message bus daemon.

## Installation

Tagentacle uses [uv](https://docs.astral.sh/uv/) as the sole supported Python package manager.

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and sync SDK
cd tagentacle-py
uv sync
```

## Quick Start

### Publish / Subscribe

```python
import asyncio
from tagentacle_py import Node

async def main():
    node = Node("my_node")
    await node.connect()

    # Subscribe
    @node.subscribe("/chat/global")
    async def on_message(msg):
        print(f"[{msg['sender']}] {msg['payload']}")

    # Publish
    await node.publish("/chat/global", {"text": "Hello!"})
    await node.spin()

asyncio.run(main())
```

### Service Call

```python
import asyncio
from tagentacle_py import Node

async def main():
    # Server
    server = Node("math_server")

    @server.service("/math/add")
    async def add(payload):
        return {"sum": payload["a"] + payload["b"]}

    await server.connect()
    spin_task = asyncio.create_task(server.spin())

    # Client
    client = Node("math_client")
    await client.connect()
    client_spin = asyncio.create_task(client.spin())

    result = await client.call_service("/math/add", {"a": 10, "b": 20})
    print(result)  # {"sum": 30}

asyncio.run(main())
```

## Dual-Layer API

### Simple API: `Node`

Lightweight node for quick integration — no lifecycle management.

```python
from tagentacle_py import Node

node = Node("my_node")
await node.connect()
await node.publish("/topic", {"data": 42})
result = await node.call_service("/service", {"query": "hello"})
await node.spin()
```

| Method | Description |
|--------|-------------|
| `connect()` | Connect to Tagentacle Daemon |
| `disconnect()` | Gracefully disconnect |
| `publish(topic, payload)` | Publish to a topic |
| `subscribe(topic)` | Decorator: register topic callback |
| `service(name)` | Decorator: register service handler |
| `call_service(name, payload, timeout)` | RPC-style service call |
| `spin()` | Main loop — dispatches messages |

### Lifecycle API: `LifecycleNode`

Full lifecycle-managed node for Agent development, inspired by ROS 2 managed nodes.

```python
from tagentacle_py import LifecycleNode

class MyAgent(LifecycleNode):
    def on_configure(self, config):
        self.api_key = config.get("api_key", "")

    def on_activate(self):
        @self.subscribe("/tasks")
        async def handle(msg):
            print(f"Task: {msg['payload']}")

    def on_shutdown(self):
        print("Cleaning up...")

agent = MyAgent("agent_1")
await agent.bringup({"api_key": "sk-..."})
await agent.spin()
```

**Lifecycle States:**

```
UNCONFIGURED → configure() → INACTIVE → activate() → ACTIVE
                                       ← deactivate() ←
INACTIVE/ACTIVE → shutdown() → FINALIZED
```

| Method | Description |
|--------|-------------|
| `configure(config)` | Inject config, call `on_configure()` |
| `activate()` | Transition to ACTIVE, call `on_activate()` |
| `deactivate()` | Transition to INACTIVE, call `on_deactivate()` |
| `shutdown()` | Finalize and disconnect, call `on_shutdown()` |
| `bringup(config)` | Convenience: connect + configure + activate |

## MCP Integration

### Client Transport (Agent → MCP Server)

```python
from tagentacle_py import Node
from tagentacle_py.mcp import tagentacle_client_transport
from mcp import ClientSession

node = Node("agent_node")
await node.connect()
spin_task = asyncio.create_task(node.spin())

async with tagentacle_client_transport(node, "mcp_server_node") as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("get_weather", {"city": "Tokyo"})
```

### Server Transport (MCP Server on Bus)

```python
from tagentacle_py import Node
from tagentacle_py.mcp import tagentacle_server_transport
from mcp.server.lowlevel import Server

mcp_server = Server("my-server")
# ... register tools with @mcp_server.call_tool() ...

node = Node("mcp_server_node")
await node.connect()
spin_task = asyncio.create_task(node.spin())

async with tagentacle_server_transport(node) as (read, write):
    await mcp_server.run(read, write, mcp_server.create_initialization_options())
```

### Tagentacle MCP Server (Bus Interaction Tools)

Built-in MCP Server that exposes **all bus interaction capabilities** as MCP Tools, allowing Agent Nodes to autonomously interact with the entire Tagentacle bus through standard MCP tool calls:

```python
from tagentacle_py.mcp.tagentacle_mcp_server import TagentacleMCPServer

server = TagentacleMCPServer("bus_tools_node", allowed_topics=["/alerts", "/logs"])
await server.start()
```

**Exposed MCP Tools:**

| Tool | Description |
|------|-------------|
| `publish_to_topic` | Publish a JSON message to a bus Topic |
| `subscribe_topic` | Subscribe to a Topic and start receiving messages |
| `unsubscribe_topic` | Unsubscribe from a previously subscribed Topic |
| `list_nodes` | List all connected nodes (calls `/tagentacle/list_nodes`) |
| `list_topics` | List all active Topics (calls `/tagentacle/list_topics`) |
| `list_services` | List all registered Services (calls `/tagentacle/list_services`) |
| `get_node_info` | Get details for a specific node (calls `/tagentacle/get_node_info`) |
| `call_bus_service` | Call any Service on the bus via RPC |
| `ping_daemon` | Check Daemon health (calls `/tagentacle/ping`) |
| `describe_topic_schema` | Retrieve the JSON Schema definition for a specific Topic's message format. Enables LLMs to query schema on-demand before publishing, avoiding context bloat. |

**Dynamic Flattened Tools** *(Planned)*: The SDK will provide an API to auto-generate flattened MCP tools from Topic JSON Schema definitions. For example, registering a `/chat/input` schema with `{text: string, sender: string}` will auto-generate a `publish_chat_input(text, sender)` tool with expanded parameters — no nested JSON required from the LLM.

## Agent Architecture: IO + Inference Separation

Tagentacle adopts a clean separation between **Agent Nodes** and **Inference Nodes**:

### Agent Node = Complete Agentic Loop

An Agent Node is a single Pkg that owns the entire agentic loop:
- Subscribe to Topics → receive user messages / events
- Manage the context window (message queue, context engineering)
- Call Inference Node's Service for LLM completion
- Parse `tool_calls` → execute tools via MCP Transport → backfill results → re-infer

This loop is tightly-coupled and should **not** be split across multiple Nodes.

### Inference Node = Stateless LLM Gateway

A separate Pkg (official example at org level, not part of core SDK) providing:
- Service (e.g., `/inference/chat`) accepting OpenAI-compatible format
- Multiple Agent Nodes can call the same Inference Node concurrently

```
UI Node ──publish──▶ /chat/input ──▶ Agent Node (agentic loop)
                                        │
                                        ├─ call_service("/inference/chat") ──▶ Inference Node
                                        │◀── completion (with tool_calls) ◀───┘
                                        │
                                        ├─ MCP Transport ──▶ Tool Server Node
                                        │◀── tool result ◀──┘
                                        │
                                        └─ publish ──▶ /chat/output ──▶ UI Node
```

## Standard Topics & Services

The Daemon provides built-in **system Topics and Services** under the `/tagentacle/` namespace:

### Reserved Namespaces

| Prefix | Purpose |
|---|---|
| `/tagentacle/*` | System reserved (Daemon & SDK core) |
| `/mcp/*` | MCP protocol (audit, RPC tunnels) |

### Standard Topics

| Topic | Description |
|---|---|
| `/tagentacle/log` | Global log aggregation (analogous to ROS `/rosout`) |
| `/tagentacle/node_events` | Node lifecycle events (connected/disconnected/transitions) |
| `/tagentacle/diagnostics` | Node health heartbeats and resource reports |
| `/mcp/traffic` | MCP JSON-RPC audit stream |

### Standard Services

| Service | Description |
|---|---|
| `/tagentacle/ping` | Daemon health check |
| `/tagentacle/list_nodes` | List all connected nodes |
| `/tagentacle/list_topics` | List all active Topics |
| `/tagentacle/list_services` | List all registered Services |
| `/tagentacle/get_node_info` | Get details for a specific node |

All standard Services are also accessible as MCP Tools via the `TagentacleMCPServer`.

## Secrets Management

Secrets are loaded from `config/secrets.toml` (git-ignored) and injected into nodes either as environment variables (via bringup launcher) or through `LifecycleNode.config["secrets"]`.

```python
class MyAgent(LifecycleNode):
    def on_configure(self, config):
        # Secrets auto-loaded from secrets.toml
        self.api_key = config.get("secrets", {}).get("OPENAI_API_KEY", "")
        # Or from environment (set by bringup launcher)
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
```

See `examples/src/bringup_pkg/config/secrets.toml.example` for the template.

## Environment & Workspace

Every Tagentacle package is a **uv project** with its own `.venv`, allowing per-node Python version isolation.

### Package Structure

Each package directory should contain:

```
my_pkg/
├── pyproject.toml      # uv project config (dependencies)
├── tagentacle.toml     # Tagentacle package manifest
├── .venv/              # Created by `uv sync` (git-ignored)
├── main.py             # Your node code
└── .gitignore          # Excludes .venv/, __pycache__
```

### Workspace Setup

```bash
# Install all package dependencies in the workspace
tagentacle setup dep --all /path/to/workspace

# This will:
#   1. Find all directories with tagentacle.toml
#   2. Run `uv sync` in each package that has pyproject.toml
#   3. Create install/ structure with .venv symlinks
#   4. Generate install/setup_env.bash
```

The generated workspace layout:

```
workspace/
├── install/
│   ├── setup_env.bash              # source this to load all envs
│   └── src/
│       ├── agent_pkg/.venv → ...   # symlink to real .venv
│       └── mcp_server_pkg/.venv → ...
└── examples/
    └── src/
        ├── agent_pkg/.venv/        # real venv (created by uv sync)
        └── mcp_server_pkg/.venv/
```

### Running Nodes

```bash
# Run a single package (auto-sources its .venv)
tagentacle run --pkg examples/src/agent_pkg

# Launch full topology (each node gets its own venv)
tagentacle launch examples/src/bringup_pkg/launch/system_launch.toml
```

### Cleanup

```bash
# Remove install/ structure (symlinks + setup_env.bash)
tagentacle setup clean --workspace /path/to/workspace
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `TAGENTACLE_DAEMON_URL` | `tcp://127.0.0.1:19999` | Daemon address |
| `TAGENTACLE_SECRETS_FILE` | _(none)_ | Path to secrets.toml |

## Project Structure

```
tagentacle-py/
├── pyproject.toml               # uv project: SDK dependencies
├── uv.lock                      # Locked dependency versions
├── tagentacle_py/
│   ├── __init__.py              # Node, LifecycleNode, LifecycleState
│   └── mcp/
│       ├── __init__.py          # Public exports
│       ├── transport.py         # Client/Server transport
│       └── tagentacle_mcp_server.py  # Tagentacle MCP Server (bus tools)
├── examples/                        # Example workspace
│   └── src/                         # Packages live here
│       ├── agent_pkg/               # MCP client agent
│       │   ├── pyproject.toml       # uv project config
│       │   └── tagentacle.toml      # Package manifest
│       ├── mcp_server_pkg/          # MCP weather server
│       │   ├── pyproject.toml
│       │   └── tagentacle.toml
│       └── bringup_pkg/             # System bringup launcher
│           ├── pyproject.toml
│           ├── tagentacle.toml
│           ├── config/secrets.toml.example
│           └── launch/system_launch.toml
└── install/                         # Generated by setup dep --all
    ├── setup_env.bash
    └── src/<pkg>/.venv → ...
```

## Roadmap

### Completed
- [x] **Simple API (`Node`)**: `connect`, `publish`, `subscribe`, `service`, `call_service`, `spin`.
- [x] **Lifecycle API (`LifecycleNode`)**: `on_configure` / `on_activate` / `on_deactivate` / `on_shutdown`, `bringup()` convenience method.
- [x] **MCP Transport Layer**: `TagentacleClientTransport` and `TagentacleServerTransport` — Bus-as-Transport for MCP sessions.
- [x] **Tagentacle MCP Server**: Built-in MCP Server exposing bus tools (`publish_to_topic`, `subscribe_topic`, `list_nodes`, `list_topics`, `list_services`, `call_bus_service`, `ping_daemon`, `describe_topic_schema`).
- [x] **Secrets Management**: Auto-load `secrets.toml`, bringup environment variable injection.
- [x] **Bringup Utilities**: `load_pkg_toml`, `discover_packages`, `find_workspace_root`.
- [x] **Example Workspace**: `example_ws/src/` with agent_pkg, mcp_server_pkg, bringup_pkg.

### Planned
- [ ] **`get_logger()` Integration**: Auto-publish node logs to `/tagentacle/log` via a custom Python logging handler (local stderr + bus publish).
- [ ] **Node Event Auto-Reporting**: `LifecycleNode` auto-publishes state transitions to `/tagentacle/node_events`.
- [ ] **Diagnostics Heartbeat**: `Node.spin()` periodically publishes health reports to `/tagentacle/diagnostics`.
- [ ] **`describe_topic_schema` Tool**: On-demand Topic JSON Schema query — LLM retrieves schema before publishing, avoiding context bloat.
- [ ] **Flattened Topic Tools API**: SDK API to auto-generate flattened MCP tools from Topic JSON Schema definitions (e.g., `/chat/input` schema → `publish_chat_input(text, sender)` with expanded parameters).
- [ ] **JSON Schema Validation**: Client-side message validation before publish, rejecting malformed payloads at the SDK level.
- [ ] **Buffered Subscription**: Optional message buffer for subscriptions — accumulate messages while the agent is in inference, drain on completion.
- [ ] **Action Client/Server**: Long-running async task API with progress feedback (analogous to ROS 2 Actions).
- [ ] **Parameter Client**: Read/write Daemon parameter store, subscribe to `/tagentacle/parameter_events`.

## License

MIT
