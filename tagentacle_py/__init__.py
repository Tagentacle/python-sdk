import asyncio
import json
import os
import uuid
from typing import Callable, Dict, Any, List

class Node:
    def __init__(self, node_id: str):
        self.node_id = node_id
        # Get Daemon URL (default tcp://127.0.0.1:19999)
        url = os.environ.get("TAGENTACLE_DAEMON_URL", "tcp://127.0.0.1:19999")
        if url.startswith("tcp://"):
            url = url[6:]
        self.host, port_str = url.split(":")
        self.port = int(port_str)
        
        self.reader = None
        self.writer = None
        # topic -> List[async-callbacks]
        self.subscribers: Dict[str, List[Callable]] = {}
        # service -> callback
        self.services: Dict[str, Callable] = {}
        # request_id -> Future
        self.pending_requests: Dict[str, asyncio.Future] = {}

    async def connect(self):
        """Connect to Tagentacle Daemon bus and register existing subscriptions and services."""
        print(f"Connecting to Tagentacle Daemon at {self.host}:{self.port}...")
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        print(f"Node '{self.node_id}' connected.")
        
        # Batch register pre-defined subscriptions
        for topic in self.subscribers.keys():
            await self._register_subscription(topic)
        
        # Batch register pre-defined services
        for service in self.services.keys():
            await self._register_service(service)

    def subscribe(self, topic: str):
        """Decorator: Subscribe to a specified Topic and register an async callback."""
        def decorator(func: Callable):
            if topic not in self.subscribers:
                self.subscribers[topic] = []
                # If already connected, register immediately (for dynamic subscription scenarios)
                if self.writer:
                    asyncio.create_task(self._register_subscription(topic))
            self.subscribers[topic].append(func)
            return func
        return decorator

    async def _register_subscription(self, topic: str):
        """Send subscription message to Daemon."""
        msg = {
            "op": "subscribe",
            "topic": topic,
            "node_id": self.node_id
        }
        await self._send_json(msg)

    async def publish(self, topic: str, payload: Any):
        """Publish message to a specified Topic."""
        msg = {
            "op": "publish",
            "topic": topic,
            "sender": self.node_id,
            "payload": payload
        }
        await self._send_json(msg)

    def service(self, service_name: str):
        """Decorator: Provide a specified Service and register an async callback."""
        def decorator(func: Callable):
            if service_name not in self.services:
                self.services[service_name] = func
                # If already connected, register immediately
                if self.writer:
                    asyncio.create_task(self._register_service(service_name))
            return func
        return decorator

    async def _register_service(self, service_name: str):
        """Send service advertisement message to Daemon."""
        msg = {
            "op": "advertise_service",
            "service": service_name,
            "node_id": self.node_id
        }
        await self._send_json(msg)

    async def call_service(self, service_name: str, payload: Any):
        """Call service synchronously and wait for response."""
        request_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self.pending_requests[request_id] = future
        
        msg = {
            "op": "call_service",
            "service": service_name,
            "request_id": request_id,
            "payload": payload,
            "caller_id": self.node_id
        }
        await self._send_json(msg)
        
        try:
            return await future
        finally:
            self.pending_requests.pop(request_id, None)

    async def _send_json(self, data: Dict):
        """Send a single line JSON (with newline)."""
        if self.writer:
            line = json.dumps(data) + "\n"
            self.writer.write(line.encode())
            await self.writer.drain()

    async def spin(self):
        """Keep running and listen for all push messages from the bus."""
        if not self.reader:
            raise RuntimeError("Node is not connected. Call await node.connect() first.")
        
        try:
            while not self.reader.at_eof():
                line = await self.reader.readline()
                if not line:
                    break
                
                try:
                    msg = json.loads(line.decode())
                    op = msg.get("op")
                    
                    if op == "message":
                        topic = msg.get("topic")
                        if topic in self.subscribers:
                            for callback in self.subscribers[topic]:
                                asyncio.create_task(callback(msg))
                    
                    elif op == "call_service":
                        service_name = msg.get("service")
                        if service_name in self.services:
                            asyncio.create_task(self._handle_service_call(msg))
                    
                    elif op == "service_response":
                        request_id = msg.get("request_id")
                        if request_id in self.pending_requests:
                            self.pending_requests[request_id].set_result(msg.get("payload"))
                            
                except json.JSONDecodeError:
                    continue
        except asyncio.CancelledError:
            pass
        finally:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            print(f"Node '{self.node_id}' disconnected.")

    async def _handle_service_call(self, msg: Dict):
        """Handle inbound service requests."""
        service_name = msg.get("service")
        request_id = msg.get("request_id")
        caller_id = msg.get("caller_id")
        payload = msg.get("payload")
        
        handler = self.services.get(service_name)
        if handler:
            try:
                # Call handler function (await if it is async)
                if asyncio.iscoroutinefunction(handler):
                    response_payload = await handler(payload)
                else:
                    response_payload = handler(payload)
                
                # Send back the response
                resp = {
                    "op": "service_response",
                    "service": service_name,
                    "request_id": request_id,
                    "payload": response_payload,
                    "caller_id": caller_id
                }
                await self._send_json(resp)
            except Exception as e:
                print(f"Error handling service {service_name}: {e}")

# Provide simplified exports
__all__ = ["Node"]
