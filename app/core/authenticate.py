import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Tuple

import argon2
import httpx
import jwt
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from google.auth.transport import requests
from google.oauth2 import id_token

from app.queries import queries
from app.utils import connections as pg_conn

JWT_SECRET_KEY = str(os.environ.get("JWT_SECRET_KEY"))
REFRESH_SECRET_KEY = str(os.environ.get("REFRESH_SECRET_KEY"))
ALGORITHM = "HS256"

ph = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

logging.basicConfig(level=logging.INFO)


def hash_password(pw):
    return ph.hash(pw)


def verify_password(hash, pw) -> bool:
    try:
        ph.verify(hash, pw)
        return True
    except argon2.exceptions.VerifyMismatchError:
        logging.error("Password verification failed")
        return False


def authenticate_user(id: str, password: str):
    conn = pg_conn.create_db_conn()
    user = conn.execute("select * from users where email = %s", (id,)).fetchone()
    conn.close()

    if not user:
        return False
    if not verify_password(user["encrypted_password"], password):
        return False
    return user


def encode_jwt(data: dict, refresh: bool):
    if refresh:
        return jwt.encode(data, REFRESH_SECRET_KEY, algorithm=ALGORITHM)

    return jwt.encode(data, JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_jwt(token: str, refresh: bool) -> Tuple[str, bool]:
    """
    if token is expired, pyjwt will throw exception
    """
    try:
        if refresh:
            return (
                jwt.decode(
                    token,
                    REFRESH_SECRET_KEY,
                    algorithms=[ALGORITHM],
                ),
                False,
            )

        return (
            jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[ALGORITHM],
            ),
            False,
        )
    except jwt.PyJWTError:
        return None, True


def create_access_token(data: dict, expires_in: timedelta | None = None):
    to_encode = data.copy()
    if expires_in:
        expire = datetime.now(timezone.utc) + expires_in
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = encode_jwt(to_encode, refresh=False)

    return encoded_jwt


def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=90)
    to_encode.update({"exp": expire})
    refresh_token = encode_jwt(to_encode, refresh=True)

    return refresh_token


def verify_provider_token(provider: str, token: str) -> bool:
    """
    False means no error. True means error
    """
    if os.environ.get("TEST_ENV") == "true":
        return False

    if provider == "github":
        client_id = os.environ.get("GITHUB_CLIENT_ID")
        client_secret = os.environ.get("GITHUB_CLIENT_SECRET")

        headers = {
            "Accept": "application/vnd.github+json",
        }
        http_auth = (client_id, client_secret)
        res = httpx.post(
            f"https://api.github.com/applications/{client_id}/token",
            json={"access_token": token},
            headers=headers,
            auth=http_auth,
        )

        if res.status_code != 200:
            return True

        return False
    else:
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        try:
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)
            return False

        except ValueError:
            return True


def get_current_user(token) -> Tuple[str, bool]:
    payload, err = decode_jwt(token, refresh=False)
    if err:
        return None, True

    user_email = payload["email"]
    if user_email is None:
        return None, True

    conn = pg_conn.create_db_conn()
    user = conn.execute(
        "select * from users where email = %s", (user_email,)
    ).fetchone()
    conn.close()

    if user is None:
        return None, True

    return user, False
