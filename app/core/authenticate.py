import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from argon2 import PasswordHasher
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.queries import queries
from app.utils import postgres_conn as pg_conn

SECRET_KEY = str(os.environ.get("JWT_SECRET_KEY"))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRATION_MIN = 30

ph = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

logging.basicConfig(level=logging.INFO)


def hash_password(pw):
    return ph.hash(pw)


def verify_password(hash, pw):
    return ph.verify(hash, pw)


def get_user(email: str):
    conn = pg_conn.create_db_conn()
    user = conn.execute(queries.get_user, (email,)).fetchone()
    conn.close()

    return user


def authenticate_user(email: str, password: str):
    user = get_user(email)

    if not user:
        return False
    if not verify_password(user["encrypted_password"], password):
        return False
    return user


def encode_jwt(data):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def decode_jwt(token):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def create_access_token(data: dict, expires_in: timedelta | None = None):
    to_encode = data.copy()
    if expires_in:
        expire = datetime.now(timezone.utc) + expires_in
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = encode_jwt(to_encode)

    return encoded_jwt


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    cred_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_jwt(token)
        user_email = payload["email"]
        if user_email is None:
            raise cred_exception
    except JWTError:
        raise cred_exception

    user = auth.get_user(user_email)
    if user is None:
        raise cred_exception

    return user
