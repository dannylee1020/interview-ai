from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        self.client_context: dict[list] = {}

    async def connect(self, session_id: str, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id][client_id] = websocket

    async def disconnect(self, session_id: str, client_id: str, websocket: WebSocket):
        del self.active_connections[session_id][client_id]

    async def send_text(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def send_bytes(self, data: bytes, websocket: WebSocket):
        await websocket.send_bytes(data)

    async def receive_text(self, websocket: WebSocket):
        msg = await websocket.receive_text()
        return msg

    async def receive_bytes(self, websocket: WebSocket):
        data = await websocket.receive_bytes()
        return data

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)