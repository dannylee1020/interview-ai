import asyncio
import copy
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

import httpx
import openai
import tiktoken
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from groq import AsyncGroq
from openai import AsyncOpenAI
from pgvector.psycopg import register_vector

from app import queries
from app.utils import connections, helper
from prompt import prompt

logging.basicConfig(level=logging.INFO)
openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

model_mapping = {
    "gpt-3.5": "gpt-3.5-turbo",
    "gpt-4": "gpt-4-turbo-preview",
    "groq": "mixtral-8x7b-32768",
}


async def chat_completion(messages: list, model: str, stream: bool = False):
    logging.info(f"Sending request to {model} chat completion endpoint...")

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
    if "--" not in res:
        res = res + " --"

    if type == "problem":
        conv_ext = re.compile(r"(.*?)Problem.*?--(.*?)$", re.DOTALL)
        matches = conv_ext.search(res)

        conv_1 = matches.group(1).strip()
        conv_2 = matches.group(2).strip() if matches.group(2) else ""
        # process text
        conv = conv_1 + f" {conv_2}"
        audio_bytes = await text_to_speech(conv)
        # extract problem from model response
        coding_text = re.search(r"Problem[\s\S]+?--", res).group(0)
    elif type == "solution":
        conv_ext = re.compile(r"(.*?)Solution.*?--(.*?)$", re.DOTALL)
        matches = conv_ext.search(res)
        conv_1 = matches.group(1).strip()
        conv_2 = matches.group(2).strip() if matches.group(2) else ""

        # process text
        conv = conv_1 + f" {conv_2}"
        audio_bytes = await text_to_speech(conv)
        # extract problem from model response
        coding_text = re.search(r"Solution[\s\S]+?--", res).group(0)

    return audio_bytes, coding_text


async def count_token(messages: list, model: str):
    if model == "groq":
        total_tokens = 0
        enc = tiktoken.get_encoding("cl100k_base")
        for m in messages:
            num_tokens = len(enc.encode(m["content"]))
            total_tokens += num_tokens
        return total_tokens

    enc = tiktoken.encoding_for_model(model)
    tokens_per_message = (
        4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
    )
    num_tokens = 0
    for m in messages:
        num_tokens += tokens_per_message
        for key, value in m.items():
            num_tokens += len(enc.encode(value))
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


async def save_vector(context: list, user_id: str):
    conv = copy.deepcopy(context)
    conn = connections.create_db_conn(dbname="vectors", autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS context (id uuid PRIMARY KEY, user_id text, created_at timestamptz, role text, content text);"
    )

    register_vector(conn)

    for c in conv:
        conn.execute(
            "INSERT INTO context (id, user_id, created_at, role, content) VALUES (%s, %s, %s, %s, %s)",
            (
                uuid.uuid4(),
                user_id,
                datetime.now(timezone.utc),
                c["role"],
                c["content"],
            ),
        )
    conn.close()


async def get_embedding(input: str):
    emb = await openai_client.embeddings.create(
        model="text-embedding-ada-002",
        input=input,
        encoding_format="float",
    )

    return emb.data[0].embedding


async def search_vector(input: str, limit: int):
    vector = await get_embedding(input)

    conn = connections.create_db_conn(dbname="vectors", autocommit=True)
    sim_v = conn.execute(
        queries.get_similar_vectors,
        (
            vector,
            limit,
        ),
    ).fetchall()
    conn.close()

    return sim_v
