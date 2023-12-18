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


def get_html():
    html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                #chat {
                    height: 300px; /* Fixed height for the chat window */
                    overflow-y: auto; /* Enable vertical scrolling */
                    border: 1px solid #ccc;
                    padding: 10px;
                }
            </style>
            <title>WebSocket Client</title>
        </head>
        <body>
            <input type="text" id="messageInput" placeholder="Type your message">
            <button onclick="sendMessage()">Send</button>
            <div id="chat"></div>

            <script>
                const socket = new WebSocket('ws://0.0.0.0:8000/chat/test');

                socket.onmessage = function(event) {
                    console.log(event)
                    const data = ""
                    displayMessage(`Assistant: ${event.data}`);
                };

                function sendMessage() {
                    const messageInput = document.getElementById('messageInput');
                    const message = messageInput.value;
                    if (message) {
                        socket.send(message);
                        displayMessage(`You: ${message}`);
                        messageInput.value = '';
                    }
                }

                function displayMessage(message) {
                    const chatDiv = document.getElementById('chat');
                    chatDiv.innerHTML += `<p>${message}</p>`;
                    chatDiv.scrollTop = chatDiv.scrollHeight; // Auto-scroll to the bottom
                }
            </script>
        </body>
        </html>
    """

    return html
