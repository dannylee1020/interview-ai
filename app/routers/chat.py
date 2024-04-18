import asyncio
import copy
import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

import openai
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core import process
from app.core.authenticate import decode_jwt
from app.utils import connections, helper
from prompt import prompt

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/chat")
manager = connections.ConnectionManager()

VOICE_TYPES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


@router.websocket("/")
async def ws_chat_audio(
    ws: WebSocket,
    token: str,
    id: str | None = None,
    model: str | None = None,
    company: str | None = None,
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

    context = []
    if "claude" not in model:
        context.extend(prompt.system_prompt)

    # query problems from DB and feed into the model
    questions = await process.query_questions(difficulty="easy")

    problem = ""
    solution = ""
    voice = random.choice(VOICE_TYPES)

    logging.info("Opening websocket channel...")
    await manager.connect(id, ws)

    try:
        while True:
            combined = ""
            text = ""
            ## start counting for tokens
            # count_tokens = asyncio.create_task(process.count_token(context, model))

            audio = await manager.receive_bytes(ws)
            logging.info("Received audio from client...")
            if not audio:
                raise WebSocketException(code=401, reason="no audio data received")
            # check if code is being sent, expire after 1 second
            try:
                async with asyncio.timeout(1.0):
                    logging.info("Receiving text...")
                    text = await manager.receive_text(ws)
            except TimeoutError:
                text = ""
                logging.info("No text received...")
                pass

            transcript = await process.speech_to_text(audio)
            combined += transcript
            combined += f" {text}"

            logging.info(f"User response: {combined}")
            context.append({"role": "user", "content": combined})

            # num_tokens = await count_tokens
            # logging.info(f"Tokens in context: {num_tokens}")
            # if num_tokens > 25000:
            #     logging.info("Truncating conversation context...")
            #     prev_context = context[len(context) - 20, len(context)]
            #     context = []
            #     if "claude" not in model:
            #         context.extend(prompt.system_prompt)
            #     context.extend(questions)
            #     context.extend(prev_context)

            # calling chat async
            chat_response = asyncio.create_task(
                process.chat_completion(
                    context,
                    model=model,
                    stream=False,
                )
            )

            response = await chat_response
            logging.info(f"Model response: {response}")
            context.append({"role": "assistant", "content": response})

            """
                problems and solutions get extracted from the response and sent as text
                rest of the tokens are extracted and converted to audio bytes and sent

                For problem, problems are injected to the model response at each step
                For solution, model is responsible for generation
            """
            if "Problem" in response:
                # dummy text to keep user assistant order correctly
                context.append({"role": "user", "content": "--"})
                # handle when there is no more questions in the list
                try:
                    question = questions.pop()
                    context.append({"role": "assistant", "content": question})
                except Exception:
                    # send this response and continue the conversation
                    res = "That's it for today's interview. Did you have any questions on any of the problems or interview in general?"
                    audio_bytes = await process.text_to_speech(res, voice)
                    context.append({"role": "assistant", "content": res})

                    await manager.send_bytes(audio_bytes, ws)
                    continue

                # extract response and convert into audio
                try:
                    audio_bytes, _ = await process.extract_tts(
                        type="problem",
                        res=response,
                        voice=voice,
                    )
                # retry in case of bad formatting from model
                except Exception as e:
                    logging.info("Error extracting problem. Retrying...")
                    res = await chat_response
                    audio_bytes, _ = await process.extract_tts(
                        type="problem",
                        res=res,
                        voice=voice,
                    )
                # prevent server from sending same problem multiple times
                if problem == question:
                    await manager.send_bytes(audio_bytes, ws)
                else:
                    problem = copy.deepcopy(question)
                    await manager.send_bytes(audio_bytes, ws)
                    await manager.send_text(question, ws)
            elif "Solution" in response:
                try:
                    audio_bytes, coding_text = await process.extract_tts(
                        type="solution",
                        res=response,
                        voice=voice,
                    )
                # retry in case of bad formatting from model
                except Exception as e:
                    logging.info("Error extracting solution. Retrying...")
                    res = await chat_response
                    audio_bytes, coding_text = await process.extract_tts(
                        type="solution",
                        res=res,
                        voice=voice,
                    )
                # prevent server from sending same solution multiple times
                if solution == coding_text:
                    await manager.send_bytes(audio_bytes, ws)
                else:
                    solution = copy.deepcopy(coding_text)
                    await manager.send_bytes(audio_bytes, ws)
                    await manager.send_text(coding_text, ws)
            else:
                audio_bytes = await process.text_to_speech(response, voice)
                await manager.send_bytes(audio_bytes, ws)

    except WebSocketDisconnect as e:
        logging.info("Saving vectors to DB before disconnecting")
        await process.save_vector(context[1:], d_token["sub"])
        await manager.disconnect(id, ws)
        logging.info("WebsocketDisconnect raised")
    except Exception as e:
        await manager.disconnect(id, ws)
        logging.info(f"Unexpected exception raised: {str(e)}")
