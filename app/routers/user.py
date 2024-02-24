import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.core import authenticate as auth
from app.models import auth as model

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/user")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


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
