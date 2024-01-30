import json
import subprocess

import ffmpeg


def convert_to_opus(source_path, opus_path):
    # Run ffmpeg command to convert MP3 to Opus
    subprocess.run(
        ["ffmpeg", "-i", source_path, "-b:a", "64k", "-vbr", "on", opus_path]
    )


def get_prompt(filepath: str):
    with open(filepath, "r") as f:
        lines = json.load(f)

    return lines
