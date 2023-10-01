import os

from fastapi import APIRouter
from pydantic import BaseModel
import openai

openai.api_key = os.environ.get("OPENAI_API_KEY")
router = APIRouter()


class Prompt(BaseModel):
    message: str


@router.post("/chat")
async def send_chat(prompt: Prompt):
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt.message}],
        stream=True,
    )

    responses = []

    for chunk in completion:
        responses.append(chunk.choices[0].delta.get("content"))

    return {"response": responses}
