import os
import datetime
from io import BytesIO

from fastapi import FastAPI, UploadFile, File
from typing import Annotated
from pydantic import BaseModel
import openai

openai.api_key = os.environ.get("OPENAI_API_KEY")
app = FastAPI()


class Prompt(BaseModel):
    message: str


@app.get("/healthcheck")
def health_check():
    return {"Hello": "World"}


@app.post("/chat")
def send_chat(prompt: Prompt):
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt.message}],
        stream=True,
    )

    responses = []

    for chunk in completion:
        responses.append(chunk.choices[0].delta.get("content"))
    return {"response": responses}


@app.post("/transcribe")
def do_transcribe(audio_file: UploadFile = File(...)):
    filepath = os.path.join(os.path.dirname(__file__), "files", "audio_file.mp3")

    with open(filepath, "wb") as out_file:
        data = audio_file.file.read()
        out_file.write(data)

    contents = open(filepath, "rb")
    transcript = openai.Audio.transcribe("whisper-1", contents)

    try:
        os.remove(filepath)
        print(f"File {filepath} deleted successfully")
    except OSError as e:
        print(f"Error deleting {filepath}: {e}")

    return transcript
