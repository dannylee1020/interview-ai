import json
import os
import openai
import asyncio

from fastapi.testclient import TestClient
from app.main import app


def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/wc/healthcheck") as websocket:
        response = websocket.receive_json()
        websocket.send_json({"message": "from client"})
        print(response)


def test_chat():
    client = TestClient(app)
    with client.websocket_connect("ws://localhost:8000/chat") as websocket:
        while True:
            websocket.send_text("Hello! It's nice to meet you")
            message = websocket.receive_text()
            print(message)

            websocket.send_text("What's the most used backend langauge in your team?")
            message = websocket.receive_text()
            print(message)




if __name__ == "__main__":
    asyncio.run(test_chat())
