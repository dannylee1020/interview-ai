import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer

from app.core import authenticate as auth
from app.models import shared as shared_model
from app.models import user as model
from app.queries import queries
from app.utils import connections

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/user")

r = connections.create_redis_conn()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@router.get(
    "/profile",
    status_code=200,
    response_model=model.UserProfile,
    responses={
        200: {
            "model": model.UserProfile,
            "description": "user profile successfully returned",
        },
        401: {
            "model": shared_model.Message,
            "description": "could not validate user credential",
        },
    },
)
def get_profile(access_token: Annotated[str, Depends(oauth2_scheme)]):
    user, err = auth.get_current_user(access_token)
    if err:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    return model.UserProfile(
        email=user["email"],
        name=user["name"],
    )


@router.get(
    "/preference/get",
    status_code=200,
    response_model=model.UserPreference,
    responses={
        200: {
            "model": model.UserPreference,
            "description": "user preference successfully returned",
        },
        401: {
            "model": shared_model.Message,
            "description": "could not validate user credential",
        },
    },
)
def get_preference(access_token: Annotated[str, Depends(oauth2_scheme)]):
    d_token, err = auth.decode_jwt(access_token, refresh=False)
    if err:
        raise HTTPException(status_code=401, detail="Invalid access token")

    user_id = d_token["sub"]
    conn = connections.create_db_conn()
    pref = conn.execute(
        "SELECT theme, language, model FROM preference WHERE user_id = %s",
        (user_id,),
    ).fetchone()

    logging.info(pref)

    if not pref:
        return model.UserPreference(
            theme="light",
            language="python",
            model="claude-sonnet",
        )

    return model.UserPreference(
        theme=pref["theme"],
        language=pref["language"],
        model=pref["model"],
    )


@router.post("/preference/save")
def save_preference(
    access_token: Annotated[str, Depends(oauth2_scheme)],
    pref: model.UserPreference,
):
    d_token, err = auth.decode_jwt(access_token, refresh=False)
    if err:
        raise HTTPException(status_code=401, detail="Invalid access token")

    user_id = d_token["sub"]
    conn = connections.create_db_conn()
    conn.execute(
        queries.upsert_preference,
        (
            uuid.uuid4(),
            user_id,
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
            pref.theme,
            pref.language,
            pref.model,
        ),
    )
    conn.commit()
    conn.close()

    return JSONResponse(
        status_code=200,
        content={"message": "User preference successfully saved"},
    )


@router.get(
    "/preference/get",
    status_code=200,
    response_model=model.UserPreference,
    responses={
        200: {
            "model": model.UserPreference,
            "description": "user preference successfully returned",
        },
        401: {
            "model": shared_model.Message,
            "description": "could not validate user credential",
        },
    },
)
def get_preference(access_token: Annotated[str, Depends(oauth2_scheme)]):
    d_token, err = auth.decode_jwt(access_token, refresh=False)
    if err:
        raise HTTPException(status_code=401, detail="Invalid access token")

    user_id = d_token["sub"]
    conn = connections.create_db_conn()
    pref = conn.execute(
        "SELECT theme, language, model FROM preference WHERE user_id = %s",
        (user_id,),
    ).fetchone()
    conn.close()

    return model.UserPreference(
        theme=pref["theme"],
        language=pref["language"],
        model=pref["model"],
    )


@router.post("/preference/save")
def save_preference(
    access_token: Annotated[str, Depends(oauth2_scheme)],
    pref: model.UserPreference,
):
    d_token, err = auth.decode_jwt(access_token, refresh=False)
    if err:
        raise HTTPException(status_code=401, detail="Invalid access token")

    user_id = d_token["sub"]
    conn = connections.create_db_conn()
    conn.execute(
        queries.upsert_preference,
        (
            uuid.uuid4(),
            user_id,
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
            pref.theme,
            pref.language,
            pref.model,
        ),
    )
    conn.commit()
    conn.close()

    return JSONResponse(
        status_code=200,
        content={"message": "User preference successfully saved"},
    )


@router.get(
    "/deactivate",
    status_code=200,
    response_model=shared_model.Message,
    responses={
        200: {
            "model": shared_model.Message,
            "description": "account successfully deactivated",
        },
        401: {
            "model": shared_model.Message,
            "description": "could not validate user credential",
        },
    },
)
def deactivate_user(access_token: Annotated[str, Depends(oauth2_scheme)]):
    data, err = auth.decode_jwt(access_token, refresh=False)
    if err:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    conn = connections.create_db_conn()
    conn.execute(
        queries.deactivate_user,
        ("deactivated", datetime.now(timezone.utc), data["email"]),
    )
    conn.commit()
    conn.close()

    # delete refresh token from cache
    r.delete(f"rt:whitelist:{data['sub']}")

    return JSONResponse(
        status_code=200,
        content={"message": "Account successfully deactivated"},
    )
