import asyncio
import copy
import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

import openai
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
)
from fastapi.security import OAuth2PasswordBearer

from app.core import process
from app.core.authenticate import decode_jwt
from app.models import chat as model
from app.utils import connections, helper
from prompt import prompt

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/chat")
manager = connections.ConnectionManager()

VOICE_TYPES = ["alloy", "echo", "fable", "nova", "shimmer"]


@router.websocket("/")
async def ws_chat_audio(
    ws: WebSocket,
    token: str,
    model: str | None = None,
    company: str | None = None,
    topic: str | None = None,
    difficulty: str | None = None,
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

    id = d_token["sub"]
    exist_ws = manager.active_connections.get(id)
    if exist_ws:
        raise WebSocketException(code=403, reason="websocket connection already open")

    voice = random.choice(VOICE_TYPES)
    model = "gpt-4o"

    # fetch language preference
    conn = connections.create_db_conn()
    lang = conn.execute(
        "SELECT language FROM preference WHERE user_id = %s",
        (id,),
    ).fetchone()
    conn.close()

    # query problems and solutions to feed into the model
    qna_data = await process.query_qna(
        difficulty=difficulty,
        topic=topic,
        language=lang["language"] if lang else None,
    )
    # construct list for model injection
    questions = [q["question"] for q in qna_data]
    solutions = [q["solution"] for q in qna_data]

    context = []
    context.extend(prompt.system_prompt)

    logging.info("Opening websocket channel...")
    await manager.connect(id, ws)

    try:
        while True:
            combined = ""
            text = ""
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

                Both problems and solutions are queried from DB and get injected at runtime.
            """
            if "Problem" in response:
                logging.info("extracting problem...")
                try:
                    audio_bytes, _ = await process.extract_tts(
                        type="problem",
                        res=response,
                        voice=voice,
                    )
                    question = questions.pop(0)
                    context.append({"role": "assistant", "content": question})
                except IndexError as e:
                    logging.info("Index error.. falling back to direct injection")
                    if "Problem 1" in response:
                        question = qna_data[0]["question"]
                    else:
                        question = qna_data[1]["question"]
                except Exception as e:
                    logging.info("Error extracting problem...")
                    continue
                await manager.send_bytes(audio_bytes, ws)
                await manager.send_text(question, ws)
            elif "Solution" in response:
                logging.info("extracting solution...")
                try:
                    audio_bytes, _ = await process.extract_tts(
                        type="solution",
                        res=response,
                        voice=voice,
                    )
                    solution = solutions.pop(0)
                    context.append({"role": "assistant", "content": solution})

                    await manager.send_bytes(audio_bytes, ws)
                except IndexError as e:
                    if "Solution 1" in response:
                        solution = qna_data[0]["solution"]
                    else:
                        solution = qna_data[1]["solution"]
                except Exception as e:
                    logging.info("Error extracting solution. Retrying...")
                    pattern = re.compile(r"(.*?)```(.*?)```(.*)", re.DOTALL)
                    matches = pattern.search(response)
                    solution = matches.group(2).strip()

                    text_prev = matches.group(1).strip() if matches.group(1) else ""
                    text_post = matches.group(3).strip() if matches.group(3) else ""
                    combined_text = text_prev + f" {text_post}"
                    audio_bytes = await process.text_to_speech(combined_text, voice)
                    await manager.send_bytes(audio_bytes, ws)
                await manager.send_text(solution, ws)
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
