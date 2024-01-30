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

r = redis.Redis(host="redis_dev", port=6379, db=0)
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


@router.post("/signup", status_code=201)
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


@router.post("/login", status_code=201)
def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """
    Validates user credential, then invalidates user's refresh token.
    Finally returns newly created access and refresh token back to user
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


@router.get("/logout", status_code=200)
def logout_user(token: Annotated[str, Depends(oauth2_scheme)]):
    d_token = auth.decode_jwt(token, refresh=False)
    # invalidate token by removing from cache
    r.delete(f"rt:whitelist:{d_token['sub']}")

    return JSONResponse(content={"message": "user successfully logged out"})


@router.post("/token/refresh", status_code=200)
# def refresh_token(refresh_token: RefreshToken):
def refresh_token(refresh_token: Annotated[str, Depends(oauth2_scheme)]):
    """
    check if refresh token exists in the cache server.
    if token doesn't exist or expired, make user login again.
    if valid, returns a newly created access and refresh token back to user.
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


@router.post("/reset-password", status_code=201)
def reset_password(cred: ResetPassword):
    pw_hash = auth.hash_password(cred.new_password)
    auth.verify_password(pw_hash, cred.new_password)

    conn = pg_conn.create_db_conn()
    conn.execute(
        queries.reset_password, (pw_hash, datetime.now(timezone.utc), cred.email)
    )
    conn.commit()
    conn.close()

    return JSONResponse(content={"message": "password updated successfully"})


# @router.get("/profile")

# @router.post("/deactivate")
