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

from app.core import authenticate as auth
from app.models import auth as model
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


@router.post(
    "/signup",
    status_code=201,
    response_model=model.Message,
    responses={
        500: {
            "model": model.Message,
            "description": "Internal server error",
        },
        201: {
            "model": model.Message,
            "description": "Returns signup successful message",
        },
        200: {
            "model": model.Message,
            "description": "Email already in use",
        },
    },
)
def signup_user(
    email: Annotated[str, Form()],
    name: Annotated[str, Form()],
    password: Annotated[str, Form()],
    username: Annotated[str, Form()],
):
    uid = uuid.uuid4()

    conn = pg_conn.create_db_conn()
    user_email = conn.execute(
        "select * from users where email = %s", (email,)
    ).fetchone()
    user_username = conn.execute(
        "select * from users where username = %s", (username,)
    ).fetchone()

    if user_email and user_email["provider"] == "native":
        return JSONResponse(
            status_code=200,
            content={"message": "Email already in use"},
        )

    if user_username:
        return JSONResponse(
            status_code=200,
            content={"message": "Username already in use"},
        )

    try:
        pw_hash = auth.hash_password(password)
        v = auth.verify_password(pw_hash, password)

        if not v:
            raise HTTPException(
                status_code=500,
                detail="Internal error: password does not match the supplied hash",
            )

        conn.execute(
            queries.signup_user,
            (uid, email, pw_hash, datetime.now(timezone.utc), "native", username, name),
        )
        conn.commit()
        conn.close()

        return JSONResponse(
            status_code=201,
            content={"message": "user successfully created"},
        )

    except psycopg.Error as e:
        logging.error("Error executing sql statement")
        conn.close()
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post(
    "/login",
    status_code=201,
    response_model=model.Token,
    responses={
        201: {
            "model": model.Token,
            "description": "Returns access and refresh token",
        },
        401: {
            "model": model.Message,
            "description": "Returns HTTP exception for incorrect authentication",
        },
    },
)
def login_user(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> model.Token:
    """
    Validates user credential. When user is verified, invalidates user's
    refresh token and returns new access and refresh token

    """
    # maybe need to distinguish between
    # user record not existing and wrong?
    user = auth.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
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

    return model.Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


# ? Is there a way to send separate status_code for
# ? when user is created vs user is just logging in?
@router.post(
    "/login/oauth",
    status_code=201,
    responses={
        201: {
            "model": model.Token,
            "description": "user successfully validated and return tokens",
        },
        500: {"description": "Internal server error"},
    },
)
def oauth_user(cred: model.OAuthCred):
    """
    signup user and login if first time user.
    login user if returning user.
    """
    # validate token with provider
    err = auth.verify_provider_token(cred.provider, cred.token)
    if err:
        raise HTTPException(status_code=401, detail="Provider token not valid")

    uid = uuid.uuid4()

    conn = pg_conn.create_db_conn()
    user = conn.execute(
        "select * from users where email = %s", (cred.email,)
    ).fetchone()

    # if first time user, create a record in the DB first
    if not user or user["provider"] == "native":
        conn.execute(
            queries.signup_user,
            (
                uid,
                cred.email,
                None,
                datetime.now(timezone.utc),
                cred.provider,
                None,
                cred.name,
            ),
        )
        conn.commit()
        conn.close()

    payload = {
        "sub": str(uid),
        "iat": datetime.now(timezone.utc),
        "email": cred.email,
    }

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRATION_MIN)
    new_access_token = auth.create_access_token(payload, access_token_expires)
    new_refresh_token = auth.create_refresh_token(payload)

    r.delete(f"rt:whitelist:{uid}")
    r.set(f"rt:whitelist:{uid}", new_refresh_token)

    return model.Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.get(
    "/logout",
    status_code=200,
    responses={
        200: {"model": model.Message, "description": "User successfully logs out"},
        401: {
            "model": model.Message,
            "description": "Unauthorized. Refresh token not valid",
        },
    },
)
def logout_user(refresh_token: Annotated[str, Depends(oauth2_scheme)]):
    d_token, err = auth.decode_jwt(refresh_token, refresh=True)
    if err:
        raise HTTPException(
            status_code=401,
            detail="refresh token not valid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # invalidate refresh token by removing from cache
    r.delete(f"rt:whitelist:{d_token['sub']}")

    return JSONResponse(content={"message": "user successfully logged out"})


@router.get(
    "/token/refresh",
    status_code=200,
    responses={
        200: {
            "model": model.Token,
            "description": "Returns a new set of access and refresh token",
        },
        401: {
            "model": model.Message,
            "description": "Refresh token is not valid",
        },
    },
)
def refresh_token(refresh_token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Check if refresh token exists in the cache server.
    If token doesn't exist or expired, redirect user to login.
    If valid, return new access and refresh token.
    """
    d_token, err = auth.decode_jwt(refresh_token, refresh=True)
    if err:
        raise HTTPException(
            status_code=401,
            detail=f"refresh token not valid, please pass in valid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # check whitelist in cache to validate token
    valid = r.get(f"rt:whitelist:{d_token['sub']}")
    if not valid:
        r.delete(f"rt:whitelist:{d_token['sub']}")
        raise HTTPException(
            status_code=401,
            detail=f"refresh token not valid, please login again",
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

    r.delete(f"rt:whitelist:{d_token['sub']}")
    r.set(f"rt:whitelist:{d_token['sub']}", new_refresh_token)

    return model.Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.put(
    "/reset-password",
    status_code=201,
    responses={
        201: {
            "model": model.Message,
            "description": "Returns when password is successfully updated",
        },
        401: {
            "model": model.Message,
            "description": "user using provider, can't reset password",
        },
        500: {"model": model.Message, "description": "password verification failed"},
    },
)
def reset_password(cred: model.ResetPassword):
    # see if this user email is associated with native login
    conn = pg_conn.create_db_conn()
    user = conn.execute(
        "select * from users where email = %s and provider = %s",
        (cred.email, "native"),
    ).fetchone()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="This user uses provider for login. Can't reset password",
        )

    pw_hash = auth.hash_password(cred.new_password)
    v = auth.verify_password(pw_hash, cred.new_password)

    if not v:
        raise HTTPException(
            status_code=500,
            detail="Internal error: password does not match the supplied hash",
        )

    conn.execute(
        queries.reset_password, (pw_hash, datetime.now(timezone.utc), cred.email)
    )
    conn.commit()
    conn.close()

    return JSONResponse(
        status_code=201,
        content={"message": "password updated successfully"},
    )


@router.get("/profile")
def get_profile(access_token: Annotated[str, Depends(oauth2_scheme)]):
    user, err = auth.get_current_user(access_token)
    if err:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    return model.UserProfile(
        email=user["email"],
        name=user["name"],
        username=user["username"],
    )


# @router.post("/deactivate")