import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer

from app.core import authenticate as auth
from app.models import user as model
from app.queries import queries
from app.utils import connections

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/user")

r = connections.create_redis_conn()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@router.get("/profile")
def get_profile(access_token: Annotated[str, Depends(oauth2_scheme)]):
    user, err = auth.get_current_user(access_token)
    if err:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    return model.UserProfile(
        email=user["email"],
        name=user["name"],
    )


@router.get("/deactivate")
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
