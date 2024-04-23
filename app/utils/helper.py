import json
import subprocess
import uuid

import ffmpeg
from jinja2 import Template

from prompt import prompt


def convert_to_opus(source_path, opus_path):
    # Run ffmpeg command to convert MP3 to Opus
    subprocess.run(
        ["ffmpeg", "-i", source_path, "-b:a", "64k", "-vbr", "on", opus_path]
    )


def format_llama_prompt(messages: list):
    formatted_messages = "<s>[INST] <<SYS>> <</SYS>>"
    for i, message in enumerate(messages):
        role = message["role"]
        content = message["content"]

        if role == "system":
            formatted_messages = f"<s>[INST]<<SYS>>\n{content}\n<</SYS>>"
        if i == 1 and role == "user":
            formatted_messages = formatted_messages + f"\n\n{content} [/INST]"
        if i != 1 and role == "user":
            formatted_messages = formatted_messages + f"\n\n<s>[INST] {content} [/INST]"
        if role == "assistant":
            formatted_messages = formatted_messages + f"\n\n{content} </s>"

    return formatted_messages


def convert_to_uuid(id: str):
    return uuid.UUID(id)


def render_template(template, data):
    template = Template(template)
    rendered_string = template.render(data=data)

    return rendered_string
