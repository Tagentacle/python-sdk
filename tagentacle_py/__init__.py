import asyncio
import json
import os
from typing import Callable, Dict, Any, List

class Node:
    def __init__(self, node_id: str):
        self.node_id = node_id
        # 获取 Daemon URL (默认 tcp://127.0.0.1:19999)
        url = os.environ.get("TAGENTACLE_DAEMON_URL", "tcp://127.0.0.1:19999")
        if url.startswith("tcp://"):
            url = url[6:]
        self.host, port_str = url.split(":")
        self.port = int(port_str)
        
        self.reader = None
        self.writer = None
        # topic -> List[async-callbacks]
        self.subscribers: Dict[str, List[Callable]] = {}

    async def connect(self):
        """连接到 Tagentacle Daemon 总线并注册已有订阅"""
        print(f"Connecting to Tagentacle Daemon at {self.host}:{self.port}...")
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        print(f"Node '{self.node_id}' connected.")
        
        # 批量注册预先定义的订阅
        for topic in self.subscribers.keys():
            await self._register_subscription(topic)

    def subscribe(self, topic: str):
        """装饰器：订阅指定 Topic 并注册异步回调"""
        def decorator(func: Callable):
            if topic not in self.subscribers:
                self.subscribers[topic] = []
                # 如果已经在连接状态，立即单独注册 (针对动态订阅场景)
                if self.writer:
                    asyncio.create_task(self._register_subscription(topic))
            self.subscribers[topic].append(func)
            return func
        return decorator

    async def _register_subscription(self, topic: str):
        """向 Daemon 发送订阅消息"""
        msg = {
            "op": "subscribe",
            "topic": topic,
            "node_id": self.node_id
        }
        await self._send_json(msg)

    async def publish(self, topic: str, payload: Any):
        """发布消息到指定 Topic"""
        msg = {
            "op": "publish",
            "topic": topic,
            "sender": self.node_id,
            "payload": payload
        }
        await self._send_json(msg)

    async def _send_json(self, data: Dict):
        """发送单行 JSON (带换行符)"""
        if self.writer:
            line = json.dumps(data) + "\n"
            self.writer.write(line.encode())
            await self.writer.drain()

    async def spin(self):
        """保持运行并监听来自总线的所有推送消息"""
        if not self.reader:
            raise RuntimeError("Node is not connected. Call await node.connect() first.")
        
        try:
            while not self.reader.at_eof():
                line = await self.reader.readline()
                if not line:
                    break
                
                try:
                    msg = json.loads(line.decode())
                    if msg.get("op") == "message":
                        topic = msg.get("topic")
                        if topic in self.subscribers:
                            # 触发回调
                            for callback in self.subscribers[topic]:
                                asyncio.create_task(callback(msg))
                except json.JSONDecodeError:
                    continue
        except asyncio.CancelledError:
            pass
        finally:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            print(f"Node '{self.node_id}' disconnected.")

# 提供简化的导出
__all__ = ["Node"]
