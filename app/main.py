import os
import openai
from fastapi import FastAPI

from app.routers import chat, transcribe

app = FastAPI()

app.include_router(chat.router)
app.include_router(transcribe.router)


@app.get("/healthcheck")
def health_check():
    return {"Hello": "World"}
