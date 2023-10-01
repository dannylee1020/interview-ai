import os
import json

from fastapi import APIRouter
from pydantic import BaseModel
import openai

PROMPT_FILEPATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "prompt", "prompt.json")
)
openai.api_key = os.environ.get("OPENAI_API_KEY")
router = APIRouter()


class Request(BaseModel):
    message: str
    model: str = None


@router.post("/chat")
async def send_chat(request: Request):
    prompt = []
    with open(PROMPT_FILEPATH, "r") as f:
        lines = json.load(f)
    prompt.extend(lines)
    full_message = prompt + [{"role": "user", "content": request.message}]

    completion = openai.ChatCompletion.create(
        model=request.model if request.model is not None else "gpt-3.5-turbo",
        messages=full_message,
        stream=True,
    )

    responses = []

    for chunk in completion:
        responses.append(chunk.choices[0].delta.get("content"))

    return {"response": responses}
