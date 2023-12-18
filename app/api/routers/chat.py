import asyncio
import json
import logging
import os

import openai
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI

from app.core.process import chat_completion, speech_to_text, text_to_speech
from app.utils import conn_manager, helper

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/chat")
manager = conn_manager.ConnectionManager()

PROMPT_FILEPATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompt", "prompt.json")
)


# * probably use path or query parameter to handle multiple clients
# * connecting to this endpoint
@router.websocket("/{client_id}")
async def ws_audio_chat(websocket: WebSocket, client_id: str):
    """
    This endpoint sends and receives audio bytes
    The endpoint is responsible for STT and TTS,
    communication with GPT endpoint and the frontend.
    """
    context = manager.client_context.get(client_id, [])

    logging.info("Opening websocket channel...")
    await manager.connect(client_id, websocket)

    if context == []:
        prompt = helper.get_prompt(PROMPT_FILEPATH)
        context.extend(prompt)

    try:
        ws = manager.active_connections.get(client_id)
        if ws is None:
            logging.info("Can't find active client connection to the websocket")
            await ws.close()
            return

        while True:
            audio_data = await manager.receive_bytes(ws)

            logging.info("Received data from client...")
            # speech -> text
            transcript = await speech_to_text(audio_data)
            context.append({"role": "user", "content": transcript})

            response = await chat_completion(context, stream=False)
            context.append({"role": "assistant", "content": response})

            # text -> speech
            speech_bytes = await text_to_speech(response)
            logging.info("Sending data back to client...")
            await manager.send_bytes(speech_bytes, ws)

            if len(context) > 50:
                context = context[25:]
    except openai.AuthenticationError as e:
        print("Error authenticating. Check your OpenAI API key")
        manager.disconnect(client_id, ws)
    except WebSocketDisconnect as e:
        await manager.disconnect(client_id, ws)
        context.clear()
        logging.info("WebsocketDisconnect raised")
    except Exception as e:
        await manager.disconnect(client_id, ws)
        logging.info(f"Unexpected exception raised: {str(e)}")


# @router.websocket("/test")
# async def websocket_chat(websocket: WebSocket):
#     """
#     This endpoint is for testing only
#     """
#     context = []
#     logging.info("Opening websocket channel..")
#     # await manager.connect(websocket)
#     await websocket.accept()

#     if context == []:
#         prompt = helper.get_prompt(PROMPT_FILEPATH)
#         context.extend(prompt)

#     try:
#         while True:
#             message = await websocket.receive_text()
#             logging.info("Received message from client..")

#             new_message = [{"role": "user", "content": message}]
#             context.extend(new_message)

#             stream = await chat_completion(context, stream=False)

#             res = [{"role": "assistant", "content": stream}]
#             context.extend(res)

#             logging.info("Sending the message back to the client...")
#             await websocket.send_text(stream)

#             if len(context) > 50:
#                 context = context[25:]

#             # async for part in stream:
#             #     message = part.choices[0].delta.content or ""
#             #     await manager.send_text(message, websocket)

#     except openai.AuthenticationError as e:
#         print("Error authenticating. Check your OpenAI API key")
#     except WebSocketDisconnect as e:
#         print("Websocket disconnected")
#         # manager.disconnect(websocket)
#         # await websocket.close()
#     except Exception as e:
#         # manager.disconnect(websocket)
#         await websocket.close()
