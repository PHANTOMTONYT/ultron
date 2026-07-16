import asyncio
import json
from pathlib import Path
from aiohttp import web, WSMsgType

class WebSocketServer:
    def __init__(self, host="localhost", port=8765, static_dir: str = None):
        self.host = host
        self.port = port
        self.static_dir = Path(static_dir) if static_dir else None
        self.clients = set()
        self.callbacks = {} # event_type -> list of callback functions
        self.runner = None

    def register_callback(self, event_type: str, callback):
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        self.callbacks[event_type].append(callback)

    async def start(self):
        app = web.Application()
        app.router.add_get("/ws", self.handler)
        if self.static_dir:
            app.router.add_get("/", self.serve_index)
            app.router.add_static("/", self.static_dir, show_index=False)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        print(f"Server: Listening on http://{self.host}:{self.port} (WebSocket at /ws)")

    async def serve_index(self, request):
        return web.FileResponse(self.static_dir / "renderer" / "index.html")

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
            print("Server: Stopped.")

    async def handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.clients.add(ws)
        print(f"WebSocket: Client connected from {request.remote}")

        try:
            async for message in ws:
                if message.type != WSMsgType.TEXT:
                    continue
                try:
                    data = json.loads(message.data)
                    event_type = data.get("type")
                    if not event_type:
                        continue

                    # Handle internal callbacks
                    if event_type in self.callbacks:
                        for callback in self.callbacks[event_type]:
                            if asyncio.iscoroutinefunction(callback):
                                asyncio.create_task(callback(data))
                            else:
                                callback(data)

                except json.JSONDecodeError:
                    print(f"WebSocket: Received invalid JSON: {message.data}")
                except Exception as e:
                    print(f"WebSocket: Error handling message: {e}")

        finally:
            self.clients.discard(ws)
            print("WebSocket: Client disconnected")

        return ws

    async def broadcast(self, message_dict: dict):
        if not self.clients:
            return

        message_str = json.dumps(message_dict)
        # Gather all sends to run in parallel
        await asyncio.gather(
            *[client.send_str(message_str) for client in self.clients],
            return_exceptions=True
        )

    def broadcast_sync(self, message_dict: dict):
        """
        Non-async wrapper to schedule a broadcast.
        """
        asyncio.create_task(self.broadcast(message_dict))
