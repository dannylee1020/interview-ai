import os
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient
import openai
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)

PROMPT_FILEPATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "prompt", "prompt.json")
)
client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
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
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    logging.info("Opening the websocket channel..")
    await manager.connect(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            logging.info("Received message from client..")

            prompt = []
            with open(PROMPT_FILEPATH, "r") as f:
                lines = json.load(f)
            prompt.extend(lines)

            full_message = prompt + [{"role": "user", "content": message}]

            logging.info("Sending request to the GPT endpoint...")
            stream = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=full_message,
                stream=True,
            )

            logging.info("Sending the message back to the client...")
            async for part in stream:
                message = part.choices[0].delta.content or ""
                await manager.send_message(message, websocket)

    except openai.AuthenticationError as e:
        print("Error authenticating. Check your OpenAI API key")
    except WebSocketDisconnect as e:
        manager.disconnect(websocket)
        await manager.broadcast(f"websocket disconneted {str(e)}")
    except Exception as e:
        manager.disconnect(websocket)
        await manager.broadcast(f"Error in websocket connection: {str(e)}")
