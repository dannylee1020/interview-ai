import asyncio
import json
import logging
import os
import re
import time
from calendar import timegm
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
import openai
import respx
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException
from openai import AsyncOpenAI

from app.core.authenticate import decode_jwt
from app.core.process import chat_completion, speech_to_text, text_to_speech
from app.utils import conn_manager, helper

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/chat")
manager = conn_manager.ConnectionManager()


PROMPT_FILEPATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompt", "prompt.json")
)


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

    The id has the followin format - session_id:client_id
    where clilent_id has two fixed values: client-main and client-code

    session_id helps server to identify which clients belong in the same session
    client_id helps identify what data to send to each client in the same session
    """
    # validate token for authorization
    d_token, err = decode_jwt(token, refresh=False)

    if err:
        raise WebSocketException(code=401, reason="invalid token")

    session_id = id.split(":")[0]
    client_id = id.split(":")[1]

    context = manager.client_context.get(client_id, [])

    logging.info("Opening websocket channel...")
    await manager.connect(session_id, client_id, ws)

    if context == []:
        prompt = helper.get_prompt(PROMPT_FILEPATH)
        context.extend(prompt)

    try:
        while True:
            audio_data = await manager.receive_bytes(ws)

            logging.info("Received data from client...")
            # speech -> text
            transcript = await speech_to_text(audio_data)
            context.append({"role": "user", "content": transcript})

            response = await chat_completion(
                context, model=model or "gpt-3.5-turbo", stream=False
            )
            context.append({"role": "assistant", "content": response})

            # send coding question portion to the relevant client
            if client_id == "client-code":
                if "Problem" in response:
                    coding_text = re.search(r"Problem[\s\S]+?--", response).group(0)
                    logging.info(coding_text)

                    await manager.send_text(coding_text, ws)

                    interview_text = re.compile(r"(.*?)Problem 1", re.DOTALL)
                    matches = interview_text.match(response)
                    interview_ext = matches.group(1).strip()
                    logging.info(interview_ext)

                    speech_bytes = await text_to_speech(interview_ext)
                    logging.info("Sending data back to client...")

                    # * as long as we make session-id unique, having fixed client-ids
                    # * for each client shouldn't be a problem
                    main_ws = manager.active_connections.get(session_id).get(
                        "client-main"
                    )

                    if main_ws != None:
                        await manager.send_bytes(speech_bytes, main_ws)
            else:
                # text -> speech
                speech_bytes = await text_to_speech(response)
                logging.info("Sending data back to client...")

                # ? Stream audio to frontend to "fake" the latency?
                await manager.send_bytes(speech_bytes, ws)

            if len(context) > 50:
                context = context[25:]

    except openai.AuthenticationError as e:
        print("Error authenticating. Check your OpenAI API key")
        manager.disconnect(session_id, client_id, ws)
    except WebSocketDisconnect as e:
        await manager.disconnect(session_id, client_id, ws)
        context.clear()
        logging.info("WebsocketDisconnect raised")
    except Exception as e:
        await manager.disconnect(session_id, client_id, ws)
        logging.info(f"Unexpected exception raised: {str(e)}")


@router.websocket("/test/multiple-clients/")
async def ws_chat_audio_test(ws: WebSocket, id: str | None = None):
    """
    testing-only endpoint that mocks the response from chat completion api
    and tests for sending different messages to multiple clients
    """

    context = manager.client_context.get(client_id, [])

    logging.info("Opening websocket channel...")
    await manager.connect(session_id, client_id, ws)

    if context == []:
        prompt = helper.get_prompt(PROMPT_FILEPATH)
        context.extend(prompt)

    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "Let's dive right into the techincal interview. Problem 1: Two Sum --"
                }
            }
        ]
    }

    try:
        while True:
            audio_data = await manager.receive_bytes(ws)

            logging.info("Received data from client...")
            # speech -> text
            transcript = await speech_to_text(audio_data)
            context.append({"role": "user", "content": transcript})

            with respx.mock:
                respx.post("https://api.openai.com/v1/chat/completions").respond(
                    json=mock_response
                )
                response = await chat_completion(context, stream=False)

            context.append({"role": "assistant", "content": response})

            # send coding question portion to the relevant client
            if client_id == "client-code":
                if "Problem" in response:
                    coding_text = re.search(r"Problem[\s\S]+?--", response).group(0)
                    await manager.send_text(coding_text, ws)

                    interview_text = re.compile(r"(.*?)Problem 1", re.DOTALL)
                    matches = interview_text.match(response)
                    interview_ext = matches.group(1).strip()

                    speech_bytes = await text_to_speech(interview_ext)
                    logging.info("Sending data back to client...")

                    main_ws = manager.active_connections.get(session_id).get(
                        "client-main"
                    )

                    if main_ws != None:
                        await manager.send_bytes(speech_bytes, main_ws)
            else:
                # text -> speech
                speech_bytes = await text_to_speech(response)
                logging.info("Sending data back to client...")

                await manager.send_bytes(speech_bytes, ws)

    except openai.AuthenticationError as e:
        print("Error authenticating. Check your OpenAI API key")
        manager.disconnect(session_id, client_id, ws)
    except WebSocketDisconnect as e:
        await manager.disconnect(session_id, client_id, ws)
        context.clear()
        logging.info("WebsocketDisconnect raised")
    except Exception as e:
        await manager.disconnect(session_id, client_id, ws)
        logging.info(f"Unexpected exception raised: {str(e)}")
