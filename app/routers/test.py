import logging
import re

import openai
import respx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException
from fastapi.responses import HTMLResponse

from app.core.process import chat_completion, speech_to_text, text_to_speech
from app.utils import connections, helper
from prompt import prompt

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/test")
manager = connections.ConnectionManager()


@router.websocket("/client/")
async def ws_chat_audio_test(
    ws: WebSocket,
    id: str | None = None,
    model: str | None = None,
    code: bool | None = None,
):
    """
    testing-only endpoint that mocks the response from chat completion api
    and tests for sending different messages to multiple clients
    """

    question = """
        Problem 1: Longest Substring Without Repeating Characters

        Given a string s, find the length of the longest substring without repeating characters.

        Example 1:

        Input: s = "abcabcbb"
        Output: 3
        Explanation: The answer is "abc", with the length of 3.
        Example 2:

        Input: s = "bbbbb"
        Output: 1
        Explanation: The answer is "b", with the length of 1.
        Example 3:

        Input: s = "pwwkew"
        Output: 3
        Explanation: The answer is "wke", with the length of 3.

    """

    exist_ws = manager.active_connections.get(id)
    if exist_ws:
        raise WebSocketException(code=403, reason="websocket connection already open")

    logging.info("Opening websocket channel...")
    await manager.connect(id, ws)

    context = manager.client_context.get(id, [])
    if context == []:
        context.extend(prompt.system_prompt)

    # openai_response = {
    #     "choices": [
    #         {
    #             "message": {
    #                 "content": f"Let's dive right into the techincal interview. {question} --"
    #                 # "content": "Hello! thanks for joining this interview today."
    #             }
    #         }
    #     ]
    # }

    # llama_response = [
    #     {
    #         "generated_text": f"Let's dive right into the technical interview. {question} --"
    #     }
    # ]

    try:
        while True:
            # audio_data = await manager.receive_bytes(ws)

            # logging.info("Received data from client...")
            # # speech -> text
            # transcript = await speech_to_text(audio_data)
            # context.append({"role": "user", "content": transcript})

            # if "gpt" in model:
            #     with respx.mock:
            #         respx.post("https://api.openai.com/v1/chat/completions").respond(
            #             json=openai_response
            #         )
            #         response = await chat_completion(context, model=model, stream=False)
            # else:
            #     with respx.mock:
            #         respx.post(
            #             "https://h73fzi2bqis5md8e.us-east-1.aws.endpoints.huggingface.cloud"
            #         ).respond(json=llama_response)

            #         response = await chat_completion(context, model=model, stream=False)

            req = await manager.receive(ws)
            req_message = req["text"]
            context.append({"role": "user", "content": req_message})

            response = await chat_completion(context, model=model, stream=False)
            context.append({"role": "assistant", "content": response})

            # * implement using single client
            if "Problem" in response:
                # extract conversation before problem
                conv_ext = re.compile(r"(.*?)Problem", re.DOTALL)
                matches = conv_ext.match(response)
                conv = matches.group(1).strip()
                # send conversation first
                await manager.send_text(conv, ws)
                # extract problem from model response
                coding_text = re.search(r"Problem[\s\S]+?--", response).group(0)
                # send coding question
                await manager.send_text(coding_text, ws)

            elif "Solution" in response:
                # extract conversation before problem
                conv_ext = re.compile(r"(.*?)Solution", re.DOTALL)
                matches = conv_ext.match(response)
                conv = matches.group(1).strip()
                # send conversation first
                await manager.send_text(conv, ws)
                # extract problem from model response
                coding_text = re.search(r"Solution[\s\S]+?--", response).group(0)
                # send coding question
                await manager.send_text(coding_text, ws)

            else:
                await manager.send_text(response, ws)

    except openai.AuthenticationError as e:
        print("Error authenticating. Check your OpenAI API key")
        manager.disconnect(id, ws)
    except WebSocketDisconnect as e:
        await manager.disconnect(id, ws)
        context.clear()
        logging.info("WebsocketDisconnect raised")
    except Exception as e:
        await manager.disconnect(id, ws)
        logging.info(f"Unexpected exception raised: {str(e)}")
        print(context)


client_a = """
<!DOCTYPE html>
<html>
<head>
    <title>Chat</title>
</head>
<body>
    <h1>WebSocket Chat</h1>
    <form action="" onsubmit="sendMessage(event)">
        <input type="text" id="messageText" autocomplete="off"/>
        <button>Send</button>
    </form>
    <ul id='messages'>
    </ul>
    <script>
        var ws = new WebSocket("ws://localhost:8000/test/client/?id=client-a-id&model=gpt-3.5");

        ws.onmessage = function(event) {
            appendMessage("Interviewer", event.data);
        };

        function sendMessage(event) {
            var input = document.getElementById("messageText");
            var message = input.value;

            appendMessage("Candidate", message);

            ws.send(message);
            input.value = '';
            event.preventDefault();
        }

        function appendMessage(sender, message) {
            var messages = document.getElementById('messages');
            var messageNode = document.createElement('li');
            var messageContent = document.createTextNode(sender + ": " + message);
            messageNode.appendChild(messageContent);
            messages.appendChild(messageNode);
        }
    </script>
</body>
</html>
"""

client_b = """
<!DOCTYPE html>
<html>
<head>
    <title>Chat</title>
</head>
<body>
    <h1>WebSocket Chat</h1>
    <form action="" onsubmit="sendMessage(event)">
        <input type="text" id="messageText" autocomplete="off"/>
        <button>Send</button>
    </form>
    <ul id='messages'>
    </ul>
    <script>
        var ws = new WebSocket("ws://localhost:8000/test/client/?id=client-a-id&model=gpt-3.5");

        ws.onmessage = function(event) {
            appendMessage("Interviewer", event.data);
        };

        function sendMessage(event) {
            var input = document.getElementById("messageText");
            var message = input.value;

            appendMessage("Candidate", message);

            ws.send(message);
            input.value = '';
            event.preventDefault();
        }

        function appendMessage(sender, message) {
            var messages = document.getElementById('messages');
            var messageNode = document.createElement('li');
            var messageContent = document.createTextNode(sender + ": " + message);
            messageNode.appendChild(messageContent);
            messages.appendChild(messageNode);
        }
    </script>
</body>
</html>
"""


@router.get("/client_a")
async def get():
    return HTMLResponse(client_a)


@router.get("/client_b")
async def get():
    return HTMLResponse(client_b)
