import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Tuple

import jwt
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.queries import queries
from app.utils import postgres_conn as pg_conn

JWT_SECRET_KEY = str(os.environ.get("JWT_SECRET_KEY"))
REFRESH_SECRET_KEY = str(os.environ.get("REFRESH_SECRET_KEY"))
ALGORITHM = "HS256"

ph = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

logging.basicConfig(level=logging.INFO)


def hash_password(pw):
    return ph.hash(pw)


def verify_password(hash, pw):
    return ph.verify(hash, pw)


def get_user(identifier: str):
    conn = pg_conn.create_db_conn()
    user = conn.execute(queries.get_user, (identifier,)).fetchone()
    conn.close()

    return user


def authenticate_user(email: str, password: str):
    user = get_user(email)

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


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    cred_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload, err = decode_jwt(token, refresh=False)
    if err:
        raise cred_exception

    user_email = payload["email"]
    if user_email is None:
        raise cred_exception

    user = auth.get_user(user_email)
    if user is None:
        raise cred_exception

    return user
