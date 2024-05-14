import asyncio
import copy
import io
import json
import logging
import os
import random
import re
import uuid
from datetime import datetime, timezone

import httpx
import openai
import tiktoken
from anthropic import AsyncAnthropicBedrock
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from groq import AsyncGroq
from openai import AsyncOpenAI
from pgvector.psycopg import register_vector

from app import queries
from app.utils import connections, helper

logging.basicConfig(level=logging.INFO)

MODEL_MAPPING = {
    "gpt-3.5": "gpt-3.5-turbo",
    "gpt-4o": "gpt-4o",
    "groq": "llama3-70b-8192",
    "claude-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
    "claude-sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
}

openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


async def chat_completion(messages: list, model: str, stream: bool = False):
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


async def query_qna(
    company: str = None,
    difficulty: str = None,
    topic: str = None,
    language: str = None,
):
    difficulty = difficulty.lower() if difficulty else "medium"
    topic = topic.lower() if topic else None
    where = (
        f"WHERE difficulty = '{difficulty}' and language = '{language}' and '{topic}' = ANY(tags)"
        if topic
        else f"WHERE difficulty = '{difficulty}' and language = '{language}'"
    )

    conn = connections.create_db_conn()
    db_results = conn.execute(
        f"""
            SELECT
                q.*,
                s.hints,
                sc.code
            FROM questions q
            JOIN solution s
                ON q.qid = s.qid
            JOIN solution_code sc
                ON q.qid = sc.qid
            {where}
            ORDER BY random()
            LIMIT 2
        """
    ).fetchall()

    res = []
    for r in db_results:
        data = {}
        data["question"] = r["problem"]
        data["hints"] = r["hints"]
        data["solution"] = r["code"]
        res.append(data)

    return res


async def count_token(messages: list, model: str):
    if "gpt" not in model:
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
    conn = connections.create_db_conn()
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    register_vector(conn)

    for c in conv:
        conn.execute(
            "INSERT INTO context (id, user_id, created_at, role, content) VALUES (%s, %s, %s, %s, %s)",
            (
                uuid.uuid4(),
                helper.convert_to_uuid(user_id),
                datetime.now(timezone.utc),
                c["role"],
                c["content"],
            ),
        )
    conn.commit()
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

    conn = connections.create_db_conn()
    sim_v = conn.execute(
        queries.get_similar_vectors,
        (
            vector,
            limit,
        ),
    ).fetchall()
    conn.close()

    return sim_v
