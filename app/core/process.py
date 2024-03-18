import asyncio
import io
import json
import logging
import os
import re

import httpx
import openai
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from groq import AsyncGroq
from openai import AsyncOpenAI

from app.utils import helper

logging.basicConfig(level=logging.INFO)
openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

model_mapping = {
    "gpt-3.5": "gpt-3.5-turbo",
    "gpt-4": "gpt-4-turbo-preview",
    "groq": "mixtral-8x7b-32768",
}


async def chat_completion(messages: list, model: str, stream: bool = False):
    logging.info("Sending request to the chat completion endpoint...")

    if "gpt" in model:
        response = await openai_client.chat.completions.create(
            model=model_mapping[model],
            messages=messages,
            stream=stream,
            temperature=0.5,
        )

        if stream:
            return response

        return response.choices[0].message.content

    elif "groq" in model:
        groq_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

        response = await groq_client.chat.completions.create(
            model=model_mapping[model],
            messages=messages,
            stream=stream,
            temperature=0.5,
        )

        if stream:
            return response
        return response.choices[0].message.content


async def speech_to_text(data):
    buffer = io.BytesIO(data)
    buffer.name = "audio.ogg"
    buffer.seek(0)

    logging.info("Sending request to the speech-to-text endpoint...")
    transcript = await openai_client.audio.transcriptions.create(
        model="whisper-1", file=buffer
    )

    buffer.close()
    return transcript.text


async def text_to_speech(text):
    dest = os.path.expanduser("~") + "/Downloads/tts.ogg"
    logging.info("Sending request to the text-to-speech endpoint...")
    res = await openai_client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        response_format="opus",
        input=text,
    )

    return res.content


async def extract_text(type: str, res: str):
    if type == "problem":
        conv_ext = re.compile(r"(.*?)Problem", re.DOTALL)
        matches = conv_ext.match(res)
        conv = matches.group(1).strip()
        # process text
        audio_bytes = await text_to_speech(conv)
        # extract problem from model response
        coding_text = re.search(r"Problem[\s\S]+?--", res).group(0)
    elif type == "solution":
        conv_ext = re.compile(r"(.*?)Solution", re.DOTALL)
        matches = conv_ext.match(res)
        conv = matches.group(1).strip()
        # process text
        audio_bytes = await text_to_speech(conv)
        # extract problem from model response
        coding_text = re.search(r"Solution[\s\S]+?--", res).group(0)

    return audio_bytes, coding_text


# TODO: need to update to fit llama if we want to use this function
async def summarize_context(context: list):
    prompt = "Could you summarize this conversations between user and assistant without losing context? \n"
    context.append({"role": "user", "content": prompt})
    response = await openai_client.chat.completions.create(
        model="gpt-3.5-turbo", messages=context, stream=False
    )
    new_context = [{"role": "system", "content": response.choices[0].message.content}]
    return new_context
