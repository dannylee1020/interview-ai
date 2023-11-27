import os
import openai
from fastapi import FastAPI, WebSocket

from app.api.routers import chat


app = FastAPI()

app.add_websocket_route("/testwc", chat.router)
app.add_websocket_route("/chat", chat.router)


@app.get("/healthcheck")
def health_check():
    return {"Hello": "World"}


@app.websocket("/wc/healthcheck")
async def wc_health_check(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"message": "from server"})
    response = await websocket.receive_json()
    print(response)
    await websocket.close()
