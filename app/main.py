import openai
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from app.routers import auth, chat, user
from app.utils import helper

app = FastAPI()

app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(user.router)


@app.get("/healthcheck")
async def health_check():
    return {"Hello": "World"}
