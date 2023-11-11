# Description
Backend service for `interview-ai` application responsible for establishing websocket connection with client and communicating with the GPT endpoint.

## Running Locally
Add OpenAI API key into the `.env` file first, then run

    docker compose up --build

to spin up the server

## Testing
Run `test_ws.py` in the test directory to test websocket connection with the chat endpoint. Messages between server and client will be logged to the console.





