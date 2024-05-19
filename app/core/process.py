import asyncio
import copy
import io
import json
import logging
import os
import random
import re

from anthropic import AsyncAnthropicBedrock
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from groq import AsyncGroq
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)

MODEL_MAPPING = {
    "gpt-3.5": "gpt-3.5-turbo",
    "gpt-4o": "gpt-4o",
    "groq": "llama3-70b-8192",
    "claude-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
    "claude-sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
}

openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


async def chat_completion(messages: list, model: str = "gpt-4o", stream: bool = False):
    logging.info(f"Sending request to {model} chat completion endpoint...")

    if "gpt" in model:
        response = await openai_client.chat.completions.create(
            model=MODEL_MAPPING[model],
            messages=messages,
            stream=stream,
            temperature=0.3,
        )

        if stream:
            return response

        return response.choices[0].message.content

    elif "groq" in model:
        groq_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

        response = await groq_client.chat.completions.create(
            model=MODEL_MAPPING[model],
            messages=messages,
            stream=stream,
            temperature=0.2,
        )

        if stream:
            return response
        return response.choices[0].message.content

    elif "claude" in model:
        claude_client = AsyncAnthropicBedrock(
            aws_access_key=os.environ.get("AWS_BEDROCK_ACCESS_KEY"),
            aws_secret_key=os.environ.get("AWS_BEDROCK_SECRET_KEY"),
        )
        response = await claude_client.messages.create(
            model=MODEL_MAPPING[model],
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
            stream=stream,
        )

        if stream:
            return response
        return response.content[0].text


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


async def text_to_speech(text: str, voice: str):
    logging.info("Sending request to the text-to-speech endpoint...")
    res = await openai_client.audio.speech.create(
        model="tts-1",
        voice=voice,
        response_format="opus",
        input=text,
    )

    return res.content


async def extract_tts(type: str, res: str, voice: str):
    if type == "problem":
        conv_ext = re.compile(r"(.*?)<problem>(.*?)</problem>(.*)", re.DOTALL)
        matches = conv_ext.search(res)

        text_before = matches.group(1).strip() if matches.group(1) else ""
        text_after = matches.group(3).strip() if matches.group(3) else ""
        code = matches.group(2).strip()
        # process text
        conv = text_before + f" {text_after}"
        audio_bytes = await text_to_speech(conv, voice)
    elif type == "solution":
        conv_ext = re.compile(r"(.*?)<solution>(.*?)</solution>(.*)$", re.DOTALL)
        matches = conv_ext.search(res)
        text_before = matches.group(1).strip() if matches.group(1) else ""
        text_after = matches.group(3).strip() if matches.group(3) else ""
        code = matches.group(2).strip()

        # process text
        conv = text_before + f" {text_after}"
        audio_bytes = await text_to_speech(conv, voice)
    return audio_bytes, code


async def extract_unformatted_solution(response: str):
    pattern = re.compile(r"(.*?)```(.*?)```(.*)", re.DOTALL)
    matches = pattern.search(response)
    solution = matches.group(2).strip()

    text_prev = matches.group(1).strip() if matches.group(1) else ""
    text_post = matches.group(3).strip() if matches.group(3) else ""
    combined_text = text_prev + f" {text_post}"
    audio_bytes = await process.text_to_speech(combined_text, voice)

    return audio_bytes, solution
