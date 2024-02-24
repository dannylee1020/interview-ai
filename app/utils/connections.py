import logging
import os
from collections import defaultdict

import psycopg
import redis
from fastapi import WebSocket
from psycopg.rows import dict_row

logging.basicConfig(level=logging.INFO)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        self.client_context: dict[list] = {}

    async def connect(self, session_id: str, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id][client_id] = websocket

    async def disconnect(self, session_id: str, client_id: str, websocket: WebSocket):
        del self.active_connections[session_id][client_id]

    async def send_text(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def send_bytes(self, data: bytes, websocket: WebSocket):
        await websocket.send_bytes(data)

    async def receive_text(self, websocket: WebSocket):
        msg = await websocket.receive_text()
        return msg

    async def receive_bytes(self, websocket: WebSocket):
        data = await websocket.receive_bytes()
        return data

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)


def create_db_conn():
    dbname = os.environ.get("DB_NAME")
    password = os.environ.get("DB_PASSWORD")
    user = os.environ.get("DB_USER")
    host = os.environ.get("DB_HOST")
    port = os.environ.get("DB_PORT")

    try:
        conn = psycopg.connect(
            dbname=dbname,
            user=user,
            host=host,
            port=port,
            password=password,
            row_factory=dict_row,
        )

        return conn

    except psycopg.Error as e:
        logging.error(f"Unable to connect to the database: {e}")

        return None


def create_redis_conn():
    try:
        r = redis.Redis(
            host=os.environ.get("REDIS_HOST"),
            port=os.environ.get("REDIS_PORT"),
            password=os.environ.get("REDIS_PW"),
        )

        return r

    except Exception as e:
        logging.error(f"Unable to connect to Redis: {e}")
        return None
