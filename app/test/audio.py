import openai
import os

openai.api_key = os.environ.get("OPENAI_API_KEY")
audio_file = open("/Users/dannylee/Downloads/sample_audio.mp3", "rb")

transcript = openai.Audio.transcribe("whisper-1", audio_file)

if __name__ == "__main__":
    print(transcript)
