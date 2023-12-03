import asyncio
import io
import json
import logging
import os
import subprocess
import tempfile

import numpy as np
import openai
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI

from app.utils import conn_manager, helper

PROMPT_FILEPATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "prompt", "prompt.json")
)
logging.basicConfig(level=logging.INFO)
client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


async def chat_completion(message: str, stream: bool):
    prompt = []
    with open(PROMPT_FILEPATH, "r") as f:
        lines = json.load(f)
    prompt.extend(lines)
    full_message = prompt + [{"role": "user", "content": message}]

    logging.info("Sending request to the chat completion endpoint...")

    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=full_message,
        stream=stream,
    )

    if stream:
        return response

    return response.choices[0].message.content


async def speech_to_text(data):
    buffer = io.BytesIO(data)
    buffer.name = "audio.ogg"
    buffer.seek(0)

    logging.info("Sending request to the speech-to-text endpoint...")
    transcript = await client.audio.transcriptions.create(
        model="whisper-1", file=buffer
    )

    buffer.close()
    return transcript.text


async def text_to_speech(text):
    dest = os.path.expanduser("~") + "/Downloads/tts.ogg"
    logging.info("Sending request to the text-to-speech endpoint...")
    res = await client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        response_format="opus",
        input=text,
    )

    return res.content
