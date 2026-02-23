"""
Tagentacle Bringup Launcher: Config-driven topology orchestration.

Reads system_launch.toml (or system_launch.yaml) and:
1. Starts the Tagentacle Daemon
2. Launches nodes in dependency order with parameter injection
3. Manages graceful shutdown

Usage:
    python system_launch.py                         # Uses system_launch.toml
    python system_launch.py my_config.toml          # Custom config
"""

import asyncio
import os
import sys

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for Python 3.8-3.10
    except ImportError:
        tomllib = None

# Paths setup
LAUNCH_DIR = os.path.dirname(os.path.abspath(__file__))
BRINGUP_DIR = os.path.dirname(LAUNCH_DIR)
EXAMPLES_DIR = os.path.dirname(BRINGUP_DIR)
ROOT_DIR = os.path.dirname(EXAMPLES_DIR)
RUST_CORE_DIR = os.path.join(ROOT_DIR, "..", "tagentacle")


def load_config(config_path: str) -> dict:
    """Load launch configuration from TOML file."""
    if tomllib is None:
        print("Warning: tomllib not available. Using fallback hardcoded config.")
        return get_fallback_config()

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def get_fallback_config() -> dict:
    """Fallback config when TOML parser is not available."""
    return {
        "daemon": {"addr": "127.0.0.1:19999"},
        "nodes": [
            {
                "name": "mcp_server_node",
                "package": "mcp_server_pkg",
                "command": "python server.py",
                "description": "Weather MCP Server",
            },
            {
                "name": "weather_agent_node",
                "package": "agent_pkg",
                "command": "python client.py",
                "description": "Agent calling weather tools",
                "depends_on": ["mcp_server_node"],
                "startup_delay": 2,
            },
        ],
        "parameters": {
            "TAGENTACLE_DAEMON_URL": "tcp://127.0.0.1:19999",
        },
    }


async def run_process(cmd: str, cwd: str, name: str, env: dict = None):
    """Run a subprocess with output logging."""
    print(f"[{name}] Starting: {cmd}")
    merged_env = {**os.environ, **(env or {})}
    process = await asyncio.create_subprocess_shell(
        cmd, cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=merged_env,
    )

    async def log_output():
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            print(f"[{name}] {line.decode().strip()}")

    asyncio.create_task(log_output())
    return process


def resolve_package_dir(package_name: str) -> str:
    """Resolve package name to its directory."""
    pkg_dir = os.path.join(EXAMPLES_DIR, package_name)
    if os.path.isdir(pkg_dir):
        return pkg_dir
    raise FileNotFoundError(f"Package directory not found: {pkg_dir}")


async def main():
    # Load config
    config_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(LAUNCH_DIR, "system_launch.toml")
    if os.path.exists(config_path):
        config = load_config(config_path)
        print(f"--- Tagentacle Bringup: loaded {config_path} ---")
    else:
        config = get_fallback_config()
        print(f"--- Tagentacle Bringup: using fallback config (no {config_path}) ---")

    # Extract parameters for env injection
    params = config.get("parameters", {})
    inject_env = {k: str(v) for k, v in params.items() if isinstance(v, str)}

    # SDK path injection
    sdk_path = os.path.join(ROOT_DIR)
    inject_env["PYTHONPATH"] = sdk_path + (f":{inject_env.get('PYTHONPATH', '')}" if inject_env.get("PYTHONPATH") else "")

    processes = []

    # 1. Start Daemon
    daemon_addr = config.get("daemon", {}).get("addr", "127.0.0.1:19999")
    if os.path.isdir(RUST_CORE_DIR):
        daemon = await run_process(
            f"cargo run -- daemon --addr {daemon_addr}",
            RUST_CORE_DIR, "DAEMON"
        )
        processes.append(("DAEMON", daemon))
        await asyncio.sleep(3)
    else:
        print("[BRINGUP] Rust core not found, assuming Daemon is already running.")

    # 2. Launch nodes in order (respecting depends_on)
    nodes = config.get("nodes", [])
    launched = set()

    for node_cfg in nodes:
        name = node_cfg["name"]
        package = node_cfg["package"]
        command = node_cfg["command"]
        depends = node_cfg.get("depends_on", [])
        delay = node_cfg.get("startup_delay", 1)

        # Wait for dependencies
        for dep in depends:
            if dep not in launched:
                print(f"[{name}] Waiting for dependency '{dep}'...")
                await asyncio.sleep(delay)

        pkg_dir = resolve_package_dir(package)
        proc = await run_process(command, pkg_dir, name, env=inject_env)
        processes.append((name, proc))
        launched.add(name)

        if delay > 0:
            await asyncio.sleep(delay)

    # 3. Wait for agent to finish (last node)
    if processes:
        last_name, last_proc = processes[-1]
        print(f"[BRINGUP] Waiting for '{last_name}' to complete...")
        await last_proc.wait()

    # 4. Graceful shutdown
    print("--- Bringup: Shutting down all nodes ---")
    for name, proc in reversed(processes):
        try:
            if proc.returncode is None:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
                print(f"[{name}] terminated.")
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass

    print("--- Bringup complete ---")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBringup interrupted.")

