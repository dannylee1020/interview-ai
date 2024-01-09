import logging
import os

from fastapi import APIRouter
from pydantic import BaseModel
from supabase import Client, create_client

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/auth")

url = os.environ.get("DB_URL")
key = os.environ.get("DB_API_KEY")

supabase = create_client(url, key)


class User(BaseModel):
    email: str
    password: str


@router.post("/")
def auth_users(user: User):
    res = supabase.auth.sign_up({"email": user.email, "password": user.password})

    return {"message": "successfully created a user"}
