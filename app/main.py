import openai
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from app.routers import auth, chat, test, user
from app.utils import helper

app = FastAPI()

origins = ["http://localhost:3000"]


app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(test.router)


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
