import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import argon2
import psycopg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from pydantic import BaseModel

from app.core import authenticate as auth
from app.queries import queries
from app.utils import postgres_conn as pg_conn

ACCESS_TOKEN_EXPIRATION_MIN = 30

# TODO: need to implement remote cache server instead of data structures on memory
BLACKLIST = {}
WHITELIST = {}

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/auth")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
uid = uuid.uuid4()


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    sub: str
    iat: str
    exp: str


class Auth(BaseModel):
    email: str
    password: str


class ResetPassword(BaseModel):
    email: str
    new_password: str


@router.post("/signup", status_code=200)
def signup_user(auth_data: Auth):
    user = auth.get_user(auth_data.email)

    if user != None:
        return JSONResponse(
            content={"message": "An account already exists under this email"}
        )

    try:
        pw_hash = auth.hash_password(auth_data.password)
        auth.verify_password(pw_hash, auth_data.password)

        conn = pg_conn.create_db_conn()
        conn.execute(
            queries.signup_user,
            (uid, auth_data.email, pw_hash, datetime.now(timezone.utc)),
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


@router.post("/login")
def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
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
    access_token = auth.create_access_token(payload, access_token_expires)

    # ? create a refresh token and save it in database?

    # * save the token into cache
    WHITELIST[user["id"]] = access_token

    return Token(access_token=access_token, token_type="bearer")


@router.get("/logout")
def logout_user(token: Annotated[str, Depends(oauth2_scheme)]):
    token_data = auth.decode_jwt(token)
    user_id = token_data["sub"]

    BLACKLIST[user_id] = token

    return JSONResponse(content={"message": "user successfully logged out"})


# * sending reset email can probably happen in the frontend
# ! this should only be accessible through the reset email sent out by us
@router.post("/reset-password")
def reset_password(cred: ResetPassword):
    pw_hash = auth.hash_password(cred.new_password)
    auth.verify_password(pw_hash, cred.new_password)

    conn.execute(
        queries.reset_password, (pw_hash, datetime.now(timezone.utc), cred.email)
    )
    conn.commit()
    conn.close()

    return JSONResponse(content={"message": "password updated successfully"})


# @router.post("/token/refresh")

# @router.get("/profile")

# @router.post("/deactivate")
