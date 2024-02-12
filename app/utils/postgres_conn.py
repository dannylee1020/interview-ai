import logging
import os

import psycopg
from psycopg.rows import dict_row

logging.basicConfig(level=logging.INFO)


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
