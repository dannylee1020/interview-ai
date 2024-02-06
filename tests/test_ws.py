import asyncio
import json

import respx
import websockets
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.utils import helper

TEST_MAIN_CLIENT = "test-session-id-123:client-main"
TEST_CODE_CLIENT = "test-session-id-789:client-code"
REMOTE_SERVER_BASE_URL = (
    "ws://interview-ai-load-balancer-1328148868.us-east-1.elb.amazonaws.com:8000"
)
LOCAL_SERVER_BASE_URL = "ws://localhost:8000"
TEST_ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4NzFhYWUxZS0zMGQyLTQzMDgtYjk3Ni0xMTE5YjNiODkxZGUiLCJpYXQiOjE3MDcxMDUzMTksImVtYWlsIjoidGVzdDY2NkB0ZXN0LmNvbSIsImV4cCI6MTcwNzEwNTQzOX0.0iwLEUTAaoTnHEdjTppeIyBuAe2pMcoqRx2rpBtF5ho"


def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/wc/healthcheck") as websocket:
        response = websocket.receive_json()
        websocket.send_json({"message": "from client"})
        print(response)


async def test_main():
    url = (
        f"{LOCAL_SERVER_BASE_URL}/chat/?token={TEST_ACCESS_TOKEN}&id={TEST_MAIN_CLIENT}"
    )
    base_path = "./files"
    audio_opus = base_path + "/sample_voice.ogg"
    speech_bytes = open(audio_opus, "rb").read()

    async with websockets.connect(url) as websocket:
        while True:
            await websocket.send(speech_bytes)
            data = await websocket.recv()

            with open(base_path + "/result.ogg", "wb") as f:
                f.write(data)

            break


async def run_test(client_id):
    url = f"{LOCAL_SERVER_BASE_URL}/chat/test/?id={client_id}"
    base_path = "./files"
    audio_opus = base_path + "/sample_voice.ogg"
    speech_bytes = open(audio_opus, "rb").read()

    async with websockets.connect(url) as websocket:
        while True:
            await websocket.send(speech_bytes)
            data = await websocket.recv()

            if client_id.split(":")[1] == "client-code":
                print(data)
            else:
                with open(base_path + "/result.ogg", "wb") as f:
                    f.write(data)

            break


async def test_code():
    test_clients = ["test-session-id:client-main", "test-session-id:client-code"]
    tasks = [run_test(client) for client in test_clients]

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(test_main())
    # asyncio.run(test_code())
