import os
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient
import openai

PROMPT_FILEPATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "prompt", "prompt.json")
)
openai.api_key = os.environ.get("OPENAI_API_KEY")
router = APIRouter()


# connection manager class for handling mutiple client connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            request = await websocket.receive_json()

            user_message = request.get("message")
            model = request.get("model", "gpt-3.5-turbo")
            prompt = []
            with open(PROMPT_FILEPATH, "r") as f:
                lines = json.load(f)
            prompt.extend(lines)

            full_message = prompt + [{"role": "user", "content": request["message"]}]
            completion = openai.ChatCompletion.create(
                model=model,
                messages=full_message,
                stream=True,
            )

            for chunk in completion:
                message = chunk.choices[0].delta.get("content")
                await manager.send_message(message, websocket)

    except WebSocketDisconnect as e:
        manager.disconnect(websocket)
        await manager.broadcast(f"websocket disconneted {str(e)}")
    except Exception as e:
        manager.disconnect(websocket)
        await manager.broadcast(f"Error in websocket connection: {str(e)}")
