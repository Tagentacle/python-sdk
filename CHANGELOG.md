# Changelog — tagentacle-py (Python SDK)

All notable changes to the **tagentacle-py** Python SDK will be documented in this file.
For Core (Rust daemon & CLI) changes see [`tagentacle/CHANGELOG.md`](../tagentacle/CHANGELOG.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Python SDK Dual-Layer API**:
  - `LifecycleNode(Node)` with state machine (UNCONFIGURED → INACTIVE → ACTIVE → FINALIZED).
  - Lifecycle hooks: `on_configure`, `on_activate`, `on_deactivate`, `on_shutdown`.
  - `bringup()` convenience method for one-call startup.
  - Improved `Node`: `disconnect()`, `_connected` flag, `call_service()` timeout, error responses on handler failure.
- **MCP Bus-as-Transport** (`tagentacle_py/mcp/`):
  - `tagentacle_client_transport(node, server_node_id)` — async context manager bridging MCP ClientSession over the bus.
  - `tagentacle_server_transport(node, server_node_id)` — async context manager exposing MCP Server as a bus service.
  - Automatic traffic mirroring to `/mcp/traffic` topic.
  - Backward-compatible class aliases `TagentacleClientTransport` / `TagentacleServerTransport`.
- **MCP-Publish Bridge Node** (`tagentacle_py/mcp/publish_bridge.py`):
  - Pre-built MCP Server exposing `publish_to_topic` and `list_available_topics` as MCP Tools.
  - Topic allow-list support. Standalone `main()` entrypoint.
- **`tagentacle.toml` Package Manifest** (examples):
  - Created example manifests for `agent_pkg`, `mcp_server_pkg`, `bringup_pkg`.
- **Bringup Configuration Center** (`examples/src/bringup_pkg/launch/`):
  - `system_launch.toml` — TOML-based topology definition with `depends_on`, `startup_delay`, parameters.
  - `system_launch.py` — config-driven launcher using `tomllib`, topological ordering, env var injection.
- **Secrets Management**:
  - `secrets.toml` auto-loading via `TAGENTACLE_SECRETS_FILE` environment variable.
  - `_load_secrets_file()` and `_parse_toml_fallback()` in Node.
  - Bringup launcher injects `TAGENTACLE_SECRETS_FILE` into child node environments.
- **SDK Bringup Utilities**:
  - `load_pkg_toml(pkg_dir)` — parse and return `tagentacle.toml` as dict.
  - `discover_packages(workspace_root)` — recursively find all packages with `tagentacle.toml`.
  - `find_workspace_root(start_path)` — locate workspace root by traversing parent directories.
- **Examples**:
  - `mcp_server_pkg/server.py` — MCP weather server over bus transport.
  - Updated `agent_pkg/client.py` — MCP client using `tagentacle_client_transport`.
  - `mcp_seamless_demo.py` — end-to-end MCP-over-bus pipeline demo.
  - All example packages converted to independent uv projects (`pyproject.toml` + `uv.lock`).

### Changed
- **Documentation**: Updated bilingual SDK READMEs with uv environment workflow and workspace documentation.
- **Build System**: Switched from pip to uv as sole Python package manager for all packages.

## [0.1.1] - 2026-02-22

### Added
- **Python SDK Enhancements**:
  - Added `@node.service` decorator for declaring service handlers (supporting both sync and async).
  - Implemented `node.call_service()` for asynchronous RPC-style calls using `asyncio.Future`.
  - Updated `Node.spin()` to handle service request dispatching and response routing.
- **Examples**:
  - Added `service_server.py` and `service_client.py` for service mechanism demonstration.

## [0.1.0] - 2026-02-22
