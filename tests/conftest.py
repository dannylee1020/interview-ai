import os

import psycopg
import pytest
import redis
from psycopg.rows import dict_row


@pytest.fixture(scope="session")
def db_conn():
    dbname = "postgres"
    password = "postgres"
    user = "postgres"
    host = "127.0.0.1"
    port = "5432"

    conn = psycopg.connect(
        dbname=dbname,
        user=user,
        host=host,
        port=port,
        password=password,
        row_factory=dict_row,
    )

    return conn


@pytest.fixture(scope="session")
def redis_conn():
    r = redis.Redis(
        host=os.environ.get("REDIS_HOST"),
        port=os.environ.get("REDIS_PORT"),
        password=os.environ.get("REDIS_PW"),
    )

    return r
