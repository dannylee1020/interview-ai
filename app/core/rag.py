import os
import uuid
from datetime import datetime, timezone

import tiktoken
from openai import AsyncOpenAI
from pgvector.psycopg import register_vector

from app.queries import queries
from app.utils import connections, helper

openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


async def query_qna(
    company: str = None,
    difficulty: str = None,
    topic: str = None,
    language: str = None,
):
    difficulty = difficulty.lower() if difficulty else "medium"
    topic = topic.lower() if topic else None
    language = language.lower() if language else "python"

    topic_queries = queries.get_tag_queries(topic)
    where = (
        f"WHERE difficulty = '{difficulty}' and language = '{language}' and {topic_queries}"
        if topic
        else f"WHERE difficulty = '{difficulty}' and language = '{language}'"
    )

    logging.info(where)

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


async def _get_embedding(input: str):
    emb = await openai_client.embeddings.create(
        model="text-embedding-ada-002",
        input=input,
        encoding_format="float",
    )

    return emb.data[0].embedding


async def search_vector(input: str, limit: int):
    vector = await _get_embedding(input)

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
