import streamlit as st
import openai
import os
import json


def app():
    st.title("Interview.ai Prototype")

    openai.api_key = os.environ.get("OPENAI_API_KEY")

    if "openai_model" not in st.session_state:
        st.session_state["openai_model"] = "gpt-3.5-turbo"

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if input := st.chat_input("what's up?"):
        st.session_state.messages.append({"role": "user", "content": input})

        prompt = []
        with open("../prompt/prompt.json", "r") as f:
            lines = json.load(f)
        prompt.extend(lines)

        with st.chat_message("user"):
            st.markdown(input)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            combined = prompt + [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ]

            for response in openai.ChatCompletion.create(
                model=st.session_state["openai_model"],
                messages=combined,
                stream=True,
            ):
                full_response += response.choices[0].delta.get("content", "")
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)

        st.session_state.messages.append(
            {"role": "assistant", "content": full_response}
        )
