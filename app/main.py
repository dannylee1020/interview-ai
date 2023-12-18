import openai
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from app.api.routers import chat

app = FastAPI()

app.include_router(chat.router)


## For tesitng
# @app.get("/")
# async def get():
#     return HTMLResponse(html)


@app.get("/healthcheck")
async def health_check():
    return {"Hello": "World"}


@app.websocket("/wc/healthcheck")
async def wc_health_check(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"message": "from server"})
    response = await websocket.receive_json()
    print(response)
    await websocket.close()
