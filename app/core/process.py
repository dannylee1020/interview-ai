import asyncio
import io
import json
import logging
import os
import re

import httpx
import openai
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI

from app.utils import helper

logging.basicConfig(level=logging.INFO)
openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

model_mapping = {
    "gpt-3.5": "gpt-3.5-turbo",
    "gpt-4": "gpt-4-turbo-preview",
    "llama": "llama",
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

    else:
        url = "https://h73fzi2bqis5md8e.us-east-1.aws.endpoints.huggingface.cloud"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {os.environ.get('HF_ACCESS_TOKEN')}",
            "Content-Type": "application/json",
        }

        llama_prompt = helper.format_llama_prompt(messages)
        payload = {
            "inputs": llama_prompt,
            "parameters": {"max_new_tokens": 150},
        }

        async with httpx.AsyncClient() as c:
            res = await c.post(url, headers=headers, json=payload)

            pattern = r"[^a-zA-Z0-9\s.,!?\-']"

            data = res.json()
            res_text = data[0]["generated_text"]
            cleaned_text = re.sub(pattern, "", res_text)

            return cleaned_text


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


# TODO: need to update to fit llama if we want to use this function
async def summarize_context(context: list):
    prompt = "Could you summarize this conversations between user and assistant without losing context? \n"
    context.append({"role": "user", "content": prompt})
    response = await openai_client.chat.completions.create(
        model="gpt-3.5-turbo", messages=context, stream=False
    )
    new_context = [{"role": "system", "content": response.choices[0].message.content}]
    return new_context
