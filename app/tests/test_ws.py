import json
import os
import openai

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
        websocket.send_json(
            {
                "message": "Hello! it's nice to meet you",
                "model": "gpt-3.5-turbo",
            }
        )

        while True:
            message = websocket.receive_text()
            if not message:
                break
            print(message)


if __name__ == "__main__":
    test_chat()
    # test_websocket()
