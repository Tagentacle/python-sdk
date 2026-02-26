# Tagentacle Python SDK（已归档）

> **⚠️ 此仓库已拆分为两个独立包，请使用下方的新仓库。**

---

## 新仓库

Tagentacle Python SDK 已按照 **1-repo-1-package** 布局拆分为两个独立包：

| 包名 | 仓库 | 说明 |
|---|---|---|
| `tagentacle-py-core` | [python-sdk-core](https://github.com/Tagentacle/python-sdk-core) | `Node`、`LifecycleNode`、包工具函数 |
| `tagentacle-py-mcp` | [python-sdk-mcp](https://github.com/Tagentacle/python-sdk-mcp) | MCP 传输层、`TagentacleMCPServer` |

```bash
# 安装核心 SDK
pip install tagentacle-py-core

# 安装 MCP 集成（依赖核心包）
pip install tagentacle-py-mcp
```

或在项目中使用 uv：
```bash
uv add tagentacle-py-core
uv add tagentacle-py-mcp   # 如需 MCP 集成
```

---

## python-sdk-core

提供双层 API，将 Python 程序连接到 [Tagentacle](https://github.com/Tagentacle/tagentacle) 消息总线守护进程。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## 安装

Tagentacle 使用 [uv](https://docs.astral.sh/uv/) 作为唯一支持的 Python 包管理器。

```bash
# 安装 uv（如尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆并同步核心 SDK
git clone https://github.com/Tagentacle/python-sdk-core
cd python-sdk-core
uv sync

# 克隆并同步 MCP 集成
git clone https://github.com/Tagentacle/python-sdk-mcp
cd python-sdk-mcp
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

## python-sdk-mcp

提供 MCP 传输层和内置 `TagentacleMCPServer`，依赖 `tagentacle-py-core`。

详见 [python-sdk-mcp](https://github.com/Tagentacle/python-sdk-mcp)。

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

### Tagentacle MCP Server（总线交互工具）

内置 MCP Server，将**所有总线交互能力**暴露为 MCP Tool，使 Agent Node 可以通过标准 MCP 工具调用自主与整个 Tagentacle 总线交互：

```python
from tagentacle_py.mcp.tagentacle_mcp_server import TagentacleMCPServer

server = TagentacleMCPServer("bus_tools_node", allowed_topics=["/alerts", "/logs"])
await server.start()
```

**暴露的 MCP Tool：**

| 工具 | 说明 |
|------|------|
| `publish_to_topic` | 向 Topic 发布 JSON 消息 |
| `subscribe_topic` | 订阅 Topic 并开始接收消息 |
| `unsubscribe_topic` | 取消订阅 |
| `list_nodes` | 列出所有连接节点（调用 `/tagentacle/list_nodes`）|
| `list_topics` | 列出所有活跃 Topic（调用 `/tagentacle/list_topics`）|
| `list_services` | 列出所有已注册 Service（调用 `/tagentacle/list_services`）|
| `get_node_info` | 获取节点详情（调用 `/tagentacle/get_node_info`）|
| `call_bus_service` | 通过 RPC 调用总线上的任意 Service |
| `ping_daemon` | 检查 Daemon 健康状态（调用 `/tagentacle/ping`）|
| `describe_topic_schema` | 获取某个 Topic 的消息 JSON Schema 定义。使 LLM 可以在发布前按需查询 schema，避免上下文膨胀。 |

**动态展平工具** *（计划中）*：SDK 将提供 API，根据 Topic JSON Schema 定义自动生成展平参数的 MCP 工具。例如，注册 `/chat/input` 的 Schema `{text: string, sender: string}` 后，自动生成 `publish_chat_input(text, sender)` 工具——LLM 无需构造嵌套 JSON。

## Agent 架构：IO + Inference 分离

Tagentacle 采用 **Agent Node**（上下文工程 + agentic loop）与 **Inference Node**（无状态 LLM 网关）的分离设计：

### Agent Node = 完整的 Agentic Loop

Agent Node 是一个独立 Pkg，在内部完成整个 agentic loop：
- 订阅 Topic → 接收用户消息/事件通知
- 管理 context window（消息队列、上下文工程）
- 通过 Service RPC 调用 Inference Node 获取 completion
- 解析 `tool_calls` → 通过 MCP Transport 执行工具 → 回填结果 → 再推理

这个 loop 是紧耦合的顺序控制流，**不应**被拆分到多个 Node。

### Inference Node = 无状态 LLM 网关

独立的 Pkg（官方示例，位于 org 级别，非核心 SDK 组成部分），提供：
- Service（如 `/inference/chat`），接受 OpenAI 兼容格式
- 多个 Agent Node 可并发调用同一个 Inference Node

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

## 标准 Topic 与 Service

Daemon 提供 `/tagentacle/` 命名空间下的内置**系统 Topic 和 Service**：

### 保留命名空间

| 前缀 | 用途 |
|---|---|
| `/tagentacle/*` | 系统保留（Daemon 与 SDK 核心）|
| `/mcp/*` | MCP 协议（审计、RPC 隧道）|

### 标准 Topic

| Topic | 说明 |
|---|---|
| `/tagentacle/log` | 全局日志聚合（类比 ROS `/rosout`）|
| `/tagentacle/node_events` | 节点生命周期事件（上线/下线/状态转换）|
| `/tagentacle/diagnostics` | 节点健康心跳与资源报告 |
| `/mcp/traffic` | MCP JSON-RPC 审计流 |

### 标准 Service

| Service | 说明 |
|---|---|
| `/tagentacle/ping` | Daemon 健康检测 |
| `/tagentacle/list_nodes` | 列出所有已连接节点 |
| `/tagentacle/list_topics` | 列出所有活跃 Topic |
| `/tagentacle/list_services` | 列出所有已注册 Service |
| `/tagentacle/get_node_info` | 获取单个节点详情 |

所有标准 Service 也可通过 `TagentacleMCPServer` 作为 MCP Tool 访问。

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

## 仓库结构（拆分后）

```
python-sdk-core/              # → github.com/Tagentacle/python-sdk-core
├── pyproject.toml
├── tagentacle.toml
├── tagentacle_py_core/
│   └── __init__.py           # Node, LifecycleNode, LifecycleState
└── uv.lock

python-sdk-mcp/               # → github.com/Tagentacle/python-sdk-mcp
├── pyproject.toml
├── tagentacle.toml
├── server_node.py
├── tagentacle_py_mcp/
│   ├── __init__.py
│   ├── transport.py          # 客户端/服务端 MCP 传输
│   └── publish_bridge.py
└── uv.lock
```

此仓库的 `example_ws/` 保留了旧的 3 节点示例（agent + mcp_server + bringup）。完整的 5 节点聊天机器人系统请参考 [example-bringup](https://github.com/Tagentacle/example-bringup)。

## 路线图

### 已完成
- [x] **简单 API (`Node`)**：`connect`、`publish`、`subscribe`、`service`、`call_service`、`spin`。
- [x] **生命周期 API (`LifecycleNode`)**：`on_configure` / `on_activate` / `on_deactivate` / `on_shutdown`，`bringup()` 便捷方法。
- [x] **MCP 传输层**：`TagentacleClientTransport` 和 `TagentacleServerTransport` — 总线即传输层。
- [x] **Tagentacle MCP Server**：内置 MCP Server，暴露总线工具（`publish_to_topic`、`subscribe_topic`、`list_nodes`、`list_topics`、`list_services`、`call_bus_service`、`ping_daemon`、`describe_topic_schema`）。
- [x] **秘钥管理**：自动加载 `secrets.toml`，Bringup 环境变量注入。
- [x] **Bringup 工具函数**：`load_pkg_toml`、`discover_packages`、`find_workspace_root`。
- [x] **示例 Workspace**：`example_ws/src/` 包含 agent_pkg、mcp_server_pkg、bringup_pkg。

### 计划中
- [ ] **`get_logger()` 集成**：通过自定义 Python logging handler 自动发布节点日志到 `/tagentacle/log`（本地 stderr + 总线 publish）。
- [ ] **节点事件自动上报**：`LifecycleNode` 状态转换时自动发布到 `/tagentacle/node_events`。
- [ ] **诊断心跳**：`Node.spin()` 定时发布健康报告到 `/tagentacle/diagnostics`。
- [ ] **`describe_topic_schema` 工具**：按需查询 Topic JSON Schema — LLM 在发布前获取 schema，避免上下文膨胀。
- [ ] **展平 Topic 工具 API**：SDK 提供 API，根据 Topic JSON Schema 定义自动生成展平参数的 MCP 工具（如 `/chat/input` schema → `publish_chat_input(text, sender)` 展开参数）。
- [ ] **JSON Schema 校验**：客户端侧消息校验，在 SDK 层拦截不合格的 payload。
- [ ] **缓冲订阅**：订阅消息可选缓冲 — Agent 推理期间累积消息，推理完成后一次性消费。
- [ ] **Action 客户端/服务端**：长程异步任务 API，支持进度反馈（类比 ROS 2 Action）。
- [ ] **Parameter 客户端**：读写 Daemon 参数存储，订阅 `/tagentacle/parameter_events`。

## 许可证

MIT
