import logging
import os
import uuid
from calendar import timegm
from datetime import datetime, timedelta, timezone
from typing import Annotated

import argon2
import psycopg
import redis
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from pydantic import BaseModel

from app.core import authenticate as auth
from app.queries import queries
from app.utils import postgres_conn as pg_conn

ACCESS_TOKEN_EXPIRATION_MIN = 30

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/auth")


r = redis.Redis(
    host=os.environ.get("REDIS_HOST"),
    port=os.environ.get("REDIS_PORT"),
    password=os.environ.get("REDIS_PW"),
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class TokenData(BaseModel):
    sub: str
    iat: str
    exp: str


class ResetPassword(BaseModel):
    email: str
    new_password: str


class RefreshToken(BaseModel):
    token: str


class Message(BaseModel):
    message: str


@router.post(
    "/signup",
    status_code=201,
    response_model=Message,
    responses={
        500: {"model": Message, "description": "Internal server error"},
        201: {"model": Message, "description": "Returns signup successful message"},
    },
)
def signup_user(email: Annotated[str, Form()], password: Annotated[str, Form()]):
    user = auth.get_user(email)
    uid = uuid.uuid4()

    if user != None:
        return JSONResponse(
            content={
                "message": "This email is already in use. Log in if you already have an account"
            }
        )

    try:
        pw_hash = auth.hash_password(password)
        auth.verify_password(pw_hash, password)

        conn = pg_conn.create_db_conn()
        conn.execute(
            queries.signup_user,
            (uid, email, pw_hash, datetime.now(timezone.utc)),
        )
        conn.commit()
        conn.close()

        return JSONResponse(content={"message": "user successfully created"})

    except argon2.exceptions.VerifyMismatchError as e:
        logging.error("Password does not match the supplied hash")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    except psycopg.Error as e:
        logging.error("Error executing sql statement")
        conn.close()
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post(
    "/login",
    status_code=201,
    response_model=Token,
    responses={
        201: {
            "model": Token,
            "description": "Returns access and refresh token",
        },
        401: {
            "model": Message,
            "description": "Returns HTTP exception for incorrect authentication",
        },
    },
)
def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """
    Validates user credential. When user is verified, invalidates user's
    refresh token and returns new access and refresh token

    """
    user = auth.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrenct username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = {
        "sub": str(user["id"]),
        "iat": datetime.now(timezone.utc),
        "email": user["email"],
    }

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRATION_MIN)
    new_access_token = auth.create_access_token(payload, access_token_expires)
    new_refresh_token = auth.create_refresh_token(payload)

    # delete exisitng RT if exists
    r.delete(f"rt:whitelist:{user['id']}")
    # add new RT to cache
    r.set(f"rt:whitelist:{user['id']}", new_refresh_token)

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.get(
    "/logout",
    status_code=200,
    responses={
        200: {"model": Message, "description": "User successfully logs out"},
        500: {"model": Message, "description": "Internal server error"},
    },
)
def logout_user(token: Annotated[str, Depends(oauth2_scheme)]):
    d_token = auth.decode_jwt(token, refresh=False)
    # invalidate token by removing from cache
    r.delete(f"rt:whitelist:{d_token['sub']}")

    return JSONResponse(content={"message": "user successfully logged out"})


@router.get(
    "/token/refresh",
    status_code=200,
    responses={
        200: {
            "model": Token,
            "description": "Returns a new set of access and refresh token",
        },
        401: {
            "model": Message,
            "description": "Refresh token is not valid, please login again",
        },
    },
)
def refresh_token(refresh_token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Check if refresh token exists in the cache server.
    If token doesn't exist or expired, redirect user to login.
    If valid, return new access and refresh token.
    """
    d_token = auth.decode_jwt(refresh_token, refresh=True)

    valid = r.get(f"rt:whitelist:{d_token['sub']}")

    if not valid or d_token["exp"] < timegm(datetime.now(timezone.utc).utctimetuple()):
        # invalidate the token
        r.delete(f"rt:whitelist:{d_token['sub']}")
        return HTTPException(
            status_code=401,
            detail="refresh token not valid, please login again",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = {
        "sub": d_token["sub"],
        "iat": datetime.now(timezone.utc),
        "email": d_token["email"],
    }
    new_access_token = auth.create_access_token(
        payload, expires_in=timedelta(minutes=ACCESS_TOKEN_EXPIRATION_MIN)
    )
    new_refresh_token = auth.create_refresh_token(payload)

    # delete the old token and add new token to cache
    r.delete(f"rt:whitelist:{d_token['sub']}")
    r.set(f"rt:whitelist:{d_token['sub']}", new_refresh_token)

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.put(
    "/reset-password",
    status_code=201,
    responses={
        201: {
            "model": Message,
            "description": "Returns when password is successfully updated",
        },
        500: {"model": Message, "description": "Internal server error"},
    },
)
def reset_password(cred: ResetPassword):
    try:
        pw_hash = auth.hash_password(cred.new_password)
        auth.verify_password(pw_hash, cred.new_password)

        conn = pg_conn.create_db_conn()
        conn.execute(
            queries.reset_password, (pw_hash, datetime.now(timezone.utc), cred.email)
        )
        conn.commit()
        conn.close()

    except Exception as e:
        return HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        )

    return JSONResponse(content={"message": "password updated successfully"})


# @router.get("/profile")

# @router.post("/deactivate")
