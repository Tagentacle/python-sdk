# bringup_pkg

A **Bringup Package** that orchestrates the entire Tagentacle system from a single configuration file.

## What it does

1. Reads `launch/system_launch.toml` for topology definition
2. Optionally starts the Tagentacle Daemon
3. Launches nodes in dependency order with parameter/secrets injection
4. Manages graceful shutdown on completion or Ctrl+C

## Run

```bash
# Default config
python examples/bringup_pkg/launch/system_launch.py

# Custom config
python examples/bringup_pkg/launch/system_launch.py my_config.toml
```

## Files

| File | Description |
|------|-------------|
| `launch/system_launch.toml` | Topology config: nodes, dependencies, parameters |
| `launch/system_launch.py` | Config-driven launcher with topological ordering |
| `config/secrets.toml` | API keys and credentials (git-ignored) |
| `config/secrets.toml.example` | Template showing expected secret keys |
| `tagentacle.toml` | Package manifest (type: bringup) |
| `.gitignore` | Ignores `config/secrets.toml` |

## Configuration Format

```toml
[daemon]
addr = "127.0.0.1:19999"

[[nodes]]
name = "mcp_server_node"
package = "mcp_server_pkg"
command = "python server.py"
depends_on = []

[[nodes]]
name = "weather_agent_node"
package = "agent_pkg"
command = "python client.py"
depends_on = ["mcp_server_node"]
startup_delay = 2

[parameters]
TAGENTACLE_DAEMON_URL = "tcp://127.0.0.1:19999"

[secrets]
secrets_file = "config/secrets.toml"
```

## Secrets Management

Sensitive credentials (API keys, tokens) are stored separately in `config/secrets.toml`:

```toml
OPENAI_API_KEY = "sk-..."
ANTHROPIC_API_KEY = "sk-ant-..."
```

- This file is **git-ignored** by default.
- Copy `config/secrets.toml.example` to `config/secrets.toml` and fill in your values.
- The launcher automatically loads secrets and injects them as environment variables to all launched nodes.
- Nodes access secrets via `os.environ["OPENAI_API_KEY"]` or through `LifecycleNode.config["secrets"]`.

## Key Concepts

- **Dependency ordering**: Nodes with `depends_on` wait for their dependencies to launch first.
- **Parameter injection**: All `[parameters]` entries become environment variables for child processes.
- **Secrets isolation**: Secrets live in a separate git-ignored file, never committed to version control.
