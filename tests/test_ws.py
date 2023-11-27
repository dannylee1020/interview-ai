import json
import os
import asyncio
import websockets
from websockets.sync.client import connect

from fastapi.testclient import TestClient
from app.main import app


def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/wc/healthcheck") as websocket:
        response = websocket.receive_json()
        websocket.send_json({"message": "from client"})
        print(response)


def test_client():
    client = TestClient(app)
    with client.websocket_connect("ws://localhost:8000/chat") as websocket:
        while True:
            websocket.send_text("Hello! It's nice to meet you")
            message = websocket.receive_text()
            print(message)


async def test_server():
    url = "ws://localhost:8000/chat"
    # url = "ws://interview-ai-load-balancer-1328148868.us-east-1.elb.amazonaws.com:8000/chat"
    async with websockets.connect(url) as websocket:
        while True:
            await websocket.send("Hello It's nice to meet you")
            message = await websocket.recv()
            print(message)


if __name__ == "__main__":
    asyncio.run(test_server())
