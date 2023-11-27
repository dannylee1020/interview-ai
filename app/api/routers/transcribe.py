import os

from fastapi import APIRouter, UploadFile, File
import openai

openai.api_key = os.environ.get("OPENAI_API_KEY")
router = APIRouter()


@router.post("/transcribe")
async def do_transcribe(audio_file: UploadFile = File(...)):
    filepath = os.path.join(os.path.dirname(__file__), "..", "files", "audio_file.mp3")

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
