import openai
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.routers import chat
from app.utils import helper

app = FastAPI()

origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)

# # For tesitng
# html = helper.get_html()


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
