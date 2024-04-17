import os

import psycopg
import pytest
import redis
from psycopg.rows import dict_row


@pytest.fixture(scope="session")
def db_conn():
    dbname = "master"
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
    host = "127.0.0.1"
    port = "6379"
    password = "redispw"

    r = redis.Redis(
        host=host,
        port=port,
        password=password,
    )

    return r
