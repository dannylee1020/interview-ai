import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
)
from fastapi.security import OAuth2PasswordBearer

from app.core import process, rag
from app.core.authenticate import decode_jwt
from app.models import chat as model
from app.utils import connections, helper
from prompt import prompt

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/chat")
manager = connections.ConnectionManager()

VOICE_TYPES = ["alloy", "echo", "fable", "nova", "shimmer"]
MODEL = "gpt-4o"


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
    model = MODEL
    # validate token for authorization
    d_token, err = decode_jwt(token, refresh=False)
    if err:
        raise WebSocketException(code=401, reason="invalid token")

    id = d_token["sub"]
    exist_ws = manager.active_connections.get(id)
    if exist_ws:
        raise WebSocketException(code=403, reason="websocket connection already open")

    voice = random.choice(VOICE_TYPES)
    # fetch language preference
    conn = connections.create_db_conn()
    lang = conn.execute(
        "SELECT language FROM preference WHERE user_id = %s",
        (id,),
    ).fetchone()
    conn.close()

    # query problems and solutions to feed into the model
    qna_data = await rag.query_qna(
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

            response = await process.chat_completion(
                context,
                model=model,
                stream=False,
            )
            logging.info(f"Model response: {response}")
            context.append({"role": "assistant", "content": response})

            """
                problems and solutions get extracted from the response and sent as text
                rest of the tokens are extracted and converted to audio bytes and sent

                Both problems and solutions are queried from DB and get injected at runtime.
            """
            if "Problem" in response:
                logging.info("extracting problem...")
                audio_bytes, _ = await process.extract_tts(
                    type="problem",
                    res=response,
                    voice=voice,
                )
                try:
                    if "Problem 1" in response:
                        question = qna_data[0]["question"]
                    elif "Problem 2" in response:
                        question = qna_data[1]["question"]
                    else:
                        raise Exception("Model doesn't adhere to problem placeholder")
                    await manager.send_bytes(audio_bytes, ws)
                    await manager.send_text(question, ws)
                except Exception as e:
                    logging.info(f"Error extracting problem: {e}")
                    websocket.close()
                    raise WebSocketDisconnect()

                    # ? terminate ws connection here for frontend to refresh the page?)

            elif "Solution" in response:
                logging.info("extracting solution...")
                audio_bytes, _ = await process.extract_tts(
                    type="solution",
                    res=response,
                    voice=voice,
                )
                try:
                    if "Solution 1" in response:
                        solution = qna_data[0]["solution"]
                    elif "Solution 2" in response:
                        solution = qna_data[1]["solution"]
                    else:
                        logging.info(
                            "Error extracting solution. falling back to direct extraction"
                        )
                        audio_bytes, solution = (
                            await process.extract_unformatted_solution(response)
                        )
                    await manager.send_bytes(audio_bytes, ws)
                    await manager.send_text(solution, ws)
                except Exception as e:
                    logging.info(f"Exception raised while extracting solution: {e}")
                    raise WebSocketDisconnect()
                    # ? disconnect ws connection and make client refresh the page?
            else:
                audio_bytes = await process.text_to_speech(response, voice)
                await manager.send_bytes(audio_bytes, ws)
    except WebSocketDisconnect as e:
        logging.info(f"disconnect error: {e}")
        logging.info("Saving vectors to DB before disconnecting")
        await rag.save_vector(context[1:], d_token["sub"])
        await manager.disconnect(id, ws)
    except Exception as e:
        logging.info(f"Unexpected exception raised: {str(e)}")
        await manager.disconnect(id, ws)
