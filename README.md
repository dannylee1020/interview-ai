# About
Backend service for `interview-ai` application responsible for establishing websocket connection with client and communicating with the GPT endpoint.

## Running Locally
- Add OpenAI API  key into the `.env` file.
- Install Taskfile by running `brew install go-task/tap/go-task`.
- Run `task up` to spin up the server
- Run `task down` to tear down the running container

## Testing
Install poetry and run `poetry install` in the root directory.

Initialize virtual environment by running `poetry shell`.

Run `task test` to test websocket connection with the chat endpoint. Messages between server and client will be logged to the console.





