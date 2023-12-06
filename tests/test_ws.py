import asyncio
import json
import os

import websockets
from fastapi.testclient import TestClient
from websockets.sync.client import connect

from app.main import app
from app.utils import helper


def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/wc/healthcheck") as websocket:
        response = websocket.receive_json()
        websocket.send_json({"message": "from client"})
        print(response)


async def test_audio_chat():
    url = "ws://interview-ai-load-balancer-1328148868.us-east-1.elb.amazonaws.com:8000/chat/audio"
    base_path = "./files"
    audio_opus = base_path + "/sample_voice.ogg"
    speech_bytes = open(audio_opus, "rb").read()

    async with websockets.connect(url) as websocket:
        while True:
            await websocket.send(speech_bytes)
            data = await websocket.recv()

            with open(base_path + "/result.ogg", "wb") as f:
                f.write(data)

            await websocket.close()
            break


async def test_chat():
    url = "ws://interview-ai-load-balancer-1328148868.us-east-1.elb.amazonaws.com:8000/chat"
    async with websockets.connect(url) as websocket:
        while True:
            await websocket.send("Hello! It's nice to meet you!")
            message = await websocket.recv()
            print(message)
            await websocket.close()
            break


if __name__ == "__main__":
    # asyncio.run(test_chat())
    asyncio.run(test_audio_chat())
