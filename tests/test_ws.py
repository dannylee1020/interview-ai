import asyncio
import base64
import json
import ssl
import time

import respx
import websockets
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.utils import helper

TEST_MAIN_CLIENT = "test-session-id-123:client-main"
TEST_CODE_CLIENT = "test-session-id-789:client-code"
TEST_ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzYWE2NTk3NC02MjUxLTQxMTQtYTE2NC0zNDBiY2JhZmE0MWUiLCJpYXQiOjE3MDg2MTYxNDEsImVtYWlsIjoidGVzdDEyM0BnbWFpbC5jb20iLCJleHAiOjE3MDg2MTc5NDF9.5L5TgNNMbJKLkOnhzF1zeXl7oOsiHDGgVooEHShtbx8"
# TEST_MODEL = "groq"
TEST_MODEL = "gpt-3.5"
# TEST_MODEL = "llama2"
# REMOTE_SERVER_BASE_URL = (
#     "ws://interview-ai-load-balancer-1661127222.us-east-1.elb.amazonaws.com:8000"
# )
REMOTE_SERVER_BASE_URL = (
    "wss://interview-ai-load-balancer-1661127222.us-east-1.elb.amazonaws.com:443"
)
LOCAL_SERVER_BASE_URL = "ws://localhost:8000"


def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/wc/healthcheck") as websocket:
        response = websocket.receive_json()
        websocket.send_json({"message": "from client"})
        print(response)


async def test_main():
    # url = f"{LOCAL_SERVER_BASE_URL}/chat/?token={TEST_ACCESS_TOKEN}&id={TEST_MAIN_CLIENT}&model={TEST_MODEL}"
    url = f"{REMOTE_SERVER_BASE_URL}/chat/?token={TEST_ACCESS_TOKEN}&id={TEST_MAIN_CLIENT}&model={TEST_MODEL}"
    base_path = "./files"
    audio_opus = base_path + "/sample_voice.ogg"
    speech_bytes = open(audio_opus, "rb").read()
    test_text = "I am excited to be in this interview. What is today's agenda?"

    async with websockets.connect(
        url, ssl=ssl.SSLContext(ssl.PROTOCOL_TLS)
    ) as websocket:
        while True:
            await websocket.send(speech_bytes)
            await websocket.send(test_text)
            data = await websocket.recv()

            with open(base_path + "/result.ogg", "wb") as f:
                f.write(data)

            break


async def test_latency():
    res = []

    for i in range(20):
        s = time.time()
        await test_main()
        e = time.time()

        res.append(e - s)

    print(res)
    print(round(sum(res) / len(res), 2))


async def run_multi_clients_test(client_id):
    url = f"{LOCAL_SERVER_BASE_URL}/test/clients/?id={client_id}&model={TEST_MODEL}"
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


async def run_single_client_test(client_id):
    url = f"{LOCAL_SERVER_BASE_URL}/test/clients/?id={client_id}&model={TEST_MODEL}"
    base_path = "./files"
    audio_opus = base_path + "/sample_voice.ogg"
    speech_bytes = open(audio_opus, "rb").read()

    async with websockets.connect(url) as websocket:
        while True:
            await websocket.send(speech_bytes)
            conv = await websocket.recv()

            try:
                problem = await asyncio.wait_for(websocket.recv(), timeout=1)
            except:
                problem = ""
                pass

            print(conv)
            print("")
            print(problem)

            break


if __name__ == "__main__":
    asyncio.run(test_main())
    # asyncio.run(test_latency())
    # asyncio.run(test_code())
    # asyncio.run(run_single_client_test(TEST_MAIN_CLIENT))
