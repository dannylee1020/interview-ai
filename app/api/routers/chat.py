import asyncio
import io
import json
import logging
import os
import queue

import openai
from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI

from app.core.process import (
    chat_completion,
    speech_to_text,
    summarize_context,
    text_to_speech,
)
from app.utils import conn_manager, helper

logging.basicConfig(level=logging.INFO)
router = APIRouter()
manager = conn_manager.ConnectionManager()

PROMPT_FILEPATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompt", "prompt.json")
)


@router.websocket("/chat/audio")
async def ws_audio_chat(websocket: WebSocket):
    """
    This endpoint sends and receives audio bytes
    The endpoint is responsible for STT and TTS,
    communication with GPT endpoint and the frontend.
    """
    context = []

    logging.info("Opening websocket channel...")
    await manager.connect(websocket)

    if context == []:
        prompt = helper.get_prompt(PROMPT_FILEPATH)
        context.extend(prompt)

    try:
        while True:
            audio_data = await websocket.receive_bytes()
            logging.info("Received data from client...")
            # speech -> text
            transcript = await speech_to_text(audio_data)
            context.append({"role": "user", "content": transcript})

            response = await chat_completion(context, stream=False)
            context.append({"role": "assistant", "content": response})

            # text -> speech
            speech_bytes = await text_to_speech(response)
            logging.info(context)
            logging.info("Sending data back to client...")
            await manager.send_bytes(speech_bytes, websocket)

            # ? Is summarizing necessary? Can I just set a limit of how far to look back?
            # run summarizer
            if len(context) > 25:
                c = await summarize_context(context)
                context = c
                logging.info(context)
    except openai.AuthenticationError as e:
        print("Error authenticating. Check your OpenAI API key")
    except WebSocketDisconnect as e:
        manager.disconnect(websocket)
        context = []
        await manager.broadcast(f"websocket disconneted {str(e)}")
    except Exception as e:
        manager.disconnect(websocket)
        await manager.broadcast(f"Error in websocket connection: {str(e)}")


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """
    This endpoint receives messages from websocket,
    sends the message to the GPT endpoint,
    and sends the response from GPT back to the client.
    """
    logging.info("Opening websocket channel..")
    await manager.connect(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            logging.info("Received message from client..")

            stream = await chat_completion(message, stream=True)

            logging.info("Sending the message back to the client...")
            async for part in stream:
                message = part.choices[0].delta.content or ""
                await manager.send_message(message, websocket)
    except openai.AuthenticationError as e:
        print("Error authenticating. Check your OpenAI API key")
    except WebSocketDisconnect as e:
        manager.disconnect(websocket)
        await manager.broadcast(f"websocket disconneted {str(e)}")
    except Exception as e:
        manager.disconnect(websocket)
        await manager.broadcast(f"Error in websocket connection: {str(e)}")
