import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

import openai
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException

from app.core.authenticate import decode_jwt
from app.core.process import chat_completion, speech_to_text, text_to_speech
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

    # validate token for authorization
    d_token, err = decode_jwt(token, refresh=False)
    if err:
        raise WebSocketException(code=401, reason="invalid token")

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
            data = await manager.receive(ws)
            msg = data.get("msg")
            code = data.get("code")

            if msg:
                logging.info("Received audio from client...")
                transcript = await speech_to_text(msg)
                context.append({"role": "user", "content": transcript})
            if code:
                logging.info("Received code from client...")
                context.append({"role": "user", "content": code})

            response = await chat_completion(context, model=model, stream=False)
            context.append({"role": "assistant", "content": response})

            if "Problem" in response:
                # extract conversation before problem
                conv_ext = re.compile(r"(.*?)Problem", re.DOTALL)
                matches = conv_ext.match(response)
                conv = matches.group(1).strip()
                # send conversation first
                speech_bytes = await text_to_speech(conv)
                await manager.send_bytes(speech_bytes, ws)
                # extract problem from model response
                coding_text = re.search(r"Problem[\s\S]+?--", response).group(0)
                # send coding problem
                await manager.send_text(coding_text, ws)

            elif "Solution" in response:
                # extract conversation before problem
                conv_ext = re.compile(r"(.*?)Solution", re.DOTALL)
                matches = conv_ext.match(response)
                conv = matches.group(1).strip()
                # send conversation first
                speech_bytes = await text_to_speech(conv)
                await manager.send_bytes(speech_bytes, ws)
                # extract problem from model response
                coding_text = re.search(r"Solution[\s\S]+?--", response).group(0)
                # send working solution
                await manager.send_text(coding_text, ws)

            else:
                speech_bytes = await text_to_speech(response)
                await manager.send_bytes(speech_bytes, ws)

    except openai.AuthenticationError as e:
        print("Error authenticating. Check your OpenAI API key")
        manager.disconnect(id, ws)
    except WebSocketDisconnect as e:
        await manager.disconnect(id, ws)
        context.clear()
        logging.info("WebsocketDisconnect raised")
    except Exception as e:
        await manager.disconnect(id, ws)
        logging.info(f"Unexpected exception raised: {str(e)}")
