import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

import openai
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException

from app.core import process
from app.core.authenticate import decode_jwt
from app.utils import connections, helper
from prompt import prompt

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/chat")
manager = connections.ConnectionManager()


@router.websocket("/")
async def ws_chat_audio(
    ws: WebSocket,
    token: str,
    id: str | None = None,
    model: str | None = None,
):
    """
    This endpoint sends and receives audio bytes
    The endpoint is responsible for STT and TTS,
    communication with GPT endpoint and the frontend.

    The id is the session_id of a user that is unique per user.
    """

    # # validate token for authorization
    # d_token, err = decode_jwt(token, refresh=False)
    # if err:
    #     raise WebSocketException(code=401, reason="invalid token")

    # check if websocket already exists
    exist_ws = manager.active_connections.get(id)
    if exist_ws:
        raise WebSocketException(code=403, reason="websocket connection already open")

    logging.info("Opening websocket channel...")
    await manager.connect(id, ws)

    context = manager.client_context.get(id, [])
    if context == []:
        context.extend(prompt.system_prompt)

    try:
        while True:
            combined = ""
            text = ""

            audio = await manager.receive_bytes(ws)
            logging.info("Received audio from client...")
            if not audio:
                raise WebSocketException(code=401, reason="no audio data received")
            # check if code is being sent, expire after 2 seconds
            try:
                async with asyncio.timeout(1.0):
                    text = await manager.receive_text(ws)
            except TimeoutError:
                text = ""
                logging.info("No text received...")
                pass

            transcript = await process.speech_to_text(audio)
            combined += transcript
            combined += f" {text}"

            chat_response = asyncio.create_task(
                process.chat_completion(context, model=model, stream=False)
            )

            logging.info(combined)
            context.append({"role": "user", "content": combined})

            # response = await chat_completion(context, model=model, stream=False)
            response = await chat_response
            logging.info(f"GPT response: {response}")
            context.append({"role": "assistant", "content": response})

            if "Problem" in response:
                audio_bytes, coding_text = await process.extract_text(
                    type="problem", res=response
                )
                await manager.send_bytes(audio_bytes, ws)
                await manager.send_text(coding_text, ws)
            elif "Solution" in response:
                audio_bytes, coding_text = await process.extract_text(
                    type="solution", res=response
                )
                await manager.send_bytes(audio_bytes, ws)
                await manager.send_text(coding_text, ws)
            else:
                audio_bytes = await process.text_to_speech(response)
                await manager.send_bytes(audio_bytes, ws)

    except openai.AuthenticationError as e:
        print("Error authenticating. Check your OpenAI API key")
        await manager.disconnect(id, ws)
    except WebSocketDisconnect as e:
        await manager.disconnect(id, ws)
        context.clear()
        logging.info("WebsocketDisconnect raised")
    except WebSocketException as e:
        await manager.disconnect(id, ws)
        logging.error(e)
    except Exception as e:
        await manager.disconnect(id, ws)
        logging.info(f"Unexpected exception raised: {str(e)}")
