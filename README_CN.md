# Tagentacle Python SDK

> **ROS for AI Agent** — 轻量级消息总线 SDK，用于构建多智能体系统，原生集成 MCP。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Tagentacle Python SDK 提供双层 API，将 Python 程序连接到 [Tagentacle](https://github.com/Tagentacle/tagentacle) 消息总线守护进程。

## 安装

Tagentacle 使用 [uv](https://docs.astral.sh/uv/) 作为唯一支持的 Python 包管理器。

```bash
# 安装 uv（如尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆并同步 SDK
cd tagentacle-py
uv sync
```

## 快速开始

### 发布 / 订阅

```python
import asyncio
from tagentacle_py import Node

async def main():
    node = Node("my_node")
    await node.connect()

    @node.subscribe("/chat/global")
    async def on_message(msg):
        print(f"[{msg['sender']}] {msg['payload']}")

    await node.publish("/chat/global", {"text": "Hello!"})
    await node.spin()

asyncio.run(main())
```

### 服务调用

```python
import asyncio
from tagentacle_py import Node

async def main():
    # 服务端
    server = Node("math_server")

    @server.service("/math/add")
    async def add(payload):
        return {"sum": payload["a"] + payload["b"]}

    await server.connect()
    spin_task = asyncio.create_task(server.spin())

    # 客户端
    client = Node("math_client")
    await client.connect()
    client_spin = asyncio.create_task(client.spin())

    result = await client.call_service("/math/add", {"a": 10, "b": 20})
    print(result)  # {"sum": 30}

asyncio.run(main())
```

## 双层 API

### 简单 API：`Node`

轻量级节点，快速集成，无生命周期管理。

```python
from tagentacle_py import Node

node = Node("my_node")
await node.connect()
await node.publish("/topic", {"data": 42})
result = await node.call_service("/service", {"query": "hello"})
await node.spin()
```

| 方法 | 说明 |
|------|------|
| `connect()` | 连接到 Tagentacle Daemon |
| `disconnect()` | 优雅断开连接 |
| `publish(topic, payload)` | 发布消息到 Topic |
| `subscribe(topic)` | 装饰器：注册 Topic 回调 |
| `service(name)` | 装饰器：注册 Service 处理器 |
| `call_service(name, payload, timeout)` | RPC 风格的服务调用 |
| `spin()` | 主循环——分发消息 |

### 生命周期 API：`LifecycleNode`

完整的生命周期管理节点，适用于 Agent 开发，灵感来自 ROS 2 托管节点。

```python
from tagentacle_py import LifecycleNode

class MyAgent(LifecycleNode):
    def on_configure(self, config):
        self.api_key = config.get("api_key", "")

    def on_activate(self):
        @self.subscribe("/tasks")
        async def handle(msg):
            print(f"任务：{msg['payload']}")

    def on_shutdown(self):
        print("清理资源...")

agent = MyAgent("agent_1")
await agent.bringup({"api_key": "sk-..."})
await agent.spin()
```

**生命周期状态：**

```
UNCONFIGURED → configure() → INACTIVE → activate() → ACTIVE
                                       ← deactivate() ←
INACTIVE/ACTIVE → shutdown() → FINALIZED
```

| 方法 | 说明 |
|------|------|
| `configure(config)` | 注入配置，调用 `on_configure()` |
| `activate()` | 转为 ACTIVE 状态，调用 `on_activate()` |
| `deactivate()` | 转为 INACTIVE 状态，调用 `on_deactivate()` |
| `shutdown()` | 终结并断开连接，调用 `on_shutdown()` |
| `bringup(config)` | 便捷方法：connect + configure + activate |

## MCP 集成

### 客户端传输（Agent → MCP Server）

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

### 服务端传输（MCP Server 挂载到总线）

```python
from tagentacle_py import Node
from tagentacle_py.mcp import tagentacle_server_transport
from mcp.server.lowlevel import Server

mcp_server = Server("my-server")
# ... 使用 @mcp_server.call_tool() 注册工具 ...

node = Node("mcp_server_node")
await node.connect()
spin_task = asyncio.create_task(node.spin())

async with tagentacle_server_transport(node) as (read, write):
    await mcp_server.run(read, write, mcp_server.create_initialization_options())
```

### MCP-Publish 桥接器

内置 MCP Server，将 `publish_to_topic` 暴露为 MCP Tool：

```python
from tagentacle_py.mcp.publish_bridge import MCPPublishBridge

bridge = MCPPublishBridge("bridge_node", topic_allowlist=["/alerts", "/logs"])
await bridge.start()
```

## 秘钥管理

秘钥从 `config/secrets.toml`（已 git-ignored）加载，通过环境变量（bringup launcher 注入）或 `LifecycleNode.config["secrets"]` 传递给节点。

```python
class MyAgent(LifecycleNode):
    def on_configure(self, config):
        # 秘钥从 secrets.toml 自动加载
        self.api_key = config.get("secrets", {}).get("OPENAI_API_KEY", "")
        # 或从环境变量获取（由 bringup launcher 设置）
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
```

参见 `examples/src/bringup_pkg/config/secrets.toml.example` 获取模板。

## 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `TAGENTACLE_DAEMON_URL` | `tcp://127.0.0.1:19999` | Daemon 地址 |
| `TAGENTACLE_SECRETS_FILE` | _（无）_ | secrets.toml 路径 |

## 环境与工作空间

每个 Tagentacle 包都是一个 **uv 项目**，拥有独立的 `.venv`，支持每个节点使用不同的 Python 版本。

### 包结构

```
my_pkg/
├── pyproject.toml      # uv 项目配置（依赖声明）
├── tagentacle.toml     # Tagentacle 包清单
├── .venv/              # 由 `uv sync` 创建（git-ignored）
├── main.py             # 节点代码
└── .gitignore
```

### 工作空间初始化

```bash
# 安装工作空间内所有包的依赖
tagentacle setup dep --all /path/to/workspace

# 自动执行：
#   1. 查找所有包含 tagentacle.toml 的目录
#   2. 在有 pyproject.toml 的包中执行 uv sync
#   3. 创建 install/ 结构（.venv 符号链接）
#   4. 生成 install/setup_env.bash
```

生成的工作空间布局：

```
workspace/
├── install/
│   ├── setup_env.bash              # source 此脚本加载所有环境
│   └── src/
│       ├── agent_pkg/.venv → ...   # 符号链接到实际 .venv
│       └── mcp_server_pkg/.venv → ...
└── examples/
    └── src/
        ├── agent_pkg/.venv/        # 真实 venv（uv sync 创建）
        └── mcp_server_pkg/.venv/
```

### 运行节点

```bash
# 运行单个包（自动激活其 .venv）
tagentacle run --pkg examples/src/agent_pkg

# 启动完整拓扑（每个节点独立 venv）
tagentacle launch examples/src/bringup_pkg/launch/system_launch.toml
```

### 清理

```bash
# 移除 install/ 结构
tagentacle setup clean --workspace /path/to/workspace
```

## 项目结构

```
tagentacle-py/
├── pyproject.toml               # uv 项目：SDK 依赖
├── uv.lock                      # 锁定的依赖版本
├── tagentacle_py/
│   ├── __init__.py              # Node, LifecycleNode, LifecycleState
│   └── mcp/
│       ├── __init__.py          # 公开导出
│       ├── transport.py         # Client/Server 传输层
│       └── publish_bridge.py    # MCP-Publish 桥接器节点
├── examples/                        # 示例工作空间
│   └── src/                         # 包放在此处
│       ├── agent_pkg/               # MCP 客户端 Agent 示例
│       │   ├── pyproject.toml
│       │   └── tagentacle.toml
│       ├── mcp_server_pkg/          # MCP 天气服务器示例
│       │   ├── pyproject.toml
│       │   └── tagentacle.toml
│       └── bringup_pkg/             # 系统 Bringup 启动器
│           ├── pyproject.toml
│           ├── tagentacle.toml
│           ├── config/secrets.toml.example
│           └── launch/system_launch.toml
└── install/                         # 由 setup dep --all 生成
    ├── setup_env.bash
    └── src/<pkg>/.venv → ...
```

## 许可证

MIT
