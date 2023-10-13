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


@router.websocket("/testwc")
async def test_websocket(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"messsage": "sending test message!"})
    response = await websocket.receive_json()
    print(f"This is server: {response}")
    await websocket.close()


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    try:
        await websocket.accept()

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
                await websocket.send_json(message)

    except WebSocketDisconnect as e:
        print(f"websocket disconnected: {str(e)}")
        await websocket.close(code=1000, reason=None)
    except Exception as e:
        print(f"Error in Websocket connnection : {str(e)}")
        await websocket.close(code=1011, reason="internal Error")


# connection manager class for handling mutiple client connections

# # class ConnectionManager:
# #     def __init__(self):
# #         self.active_connections: list[WebSocket] = []

# #     async def connect(self, websocket: Websocket):
# #         await websocket.accept()
# #         self.active_connections.append(websocket)

# #     def disconnect(self, websocket: Websocket):
# #         self.active_connections.remove(websocket)

# #     async def send_message(self, message: str, websocket: WebSocket):
# #         await websocket.send_text(message)


# # manager = ConnectionManager()
