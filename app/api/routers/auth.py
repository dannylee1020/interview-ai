import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import argon2
import psycopg
import redis
from fastapi import APIRouter, Depends, HTTPException
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
    uid = uuid.uuid4()

    if user != None:
        return JSONResponse(
            content={
                "message": "This email is already in use. Log in if you already have an account"
            }
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
    new_access_token = auth.create_access_token(payload, access_token_expires)

    blacklisted = r.get(f"blacklist:{user['id']}")

    if not blacklisted:
        w_token = r.get(f"whitelist:{user['id']}")

        if not w_token or auth.decode_jwt(w_token)["exp"] < datetime.now(timezone.utc):
            r.set("whitelist", f"{user['id']}:{new_access_token}")
            return Token(access_token=new_access_token, token_type="bearer")

        return Token(access_token=w_token, token_type="bearer")

    r.set("whitelist", f"{user['id']}:{new_access_token}")
    return Token(access_token=new_access_token, token_type="bearer")


@router.get("/logout")
def logout_user(token: Annotated[str, Depends(oauth2_scheme)]):
    token_data = auth.decode_jwt(token)
    user_id = token_data["sub"]

    r.set("blacklist", f"{user_id}:{token}")
    r.delete("whitelist", f"{user_id}:{token}")

    return JSONResponse(content={"message": "user successfully logged out"})


# ! this should only be accessible through the reset email sent out by us
@router.post("/reset-password")
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


# @router.post("/token/refresh")

# @router.get("/profile")

# @router.post("/deactivate")
