import streamlit as st
import requests

st.set_page_config(page_title="Calendar AI Assistant", page_icon="📅")
st.title("📅 AI Calendar Booking Assistant")

API_URL = "http://localhost:8501/invoke"

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Input form
with st.form("user_input_form", clear_on_submit=True):
    user_input = st.text_input("Enter your request:", placeholder="e.g., Postpone today's meeting to tomorrow 10 am")
    submitted = st.form_submit_button("Send")

# Handle input and append new messages before rendering
if submitted and user_input.strip():
    # Add user message
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    try:
        with st.spinner("Thinking..."):
            response = requests.post(API_URL, json={"user_input": user_input})
            result = response.json()

            if result["status"] == "success":
                full_result = result["result"]
                if isinstance(full_result, dict) and "messages" in full_result:
                    # Get last assistant message
                    final_message = ""
                    for msg in reversed(full_result["messages"]):
                        if msg.get("type") == "ai" and msg.get("content"):
                            final_message = msg["content"]
                            break
                else:
                    final_message = str(full_result)

                st.session_state.chat_history.append({"role": "assistant", "content": final_message})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Error: {result['message']}"} )
    except Exception as e:
        st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Request failed: {str(e)}"})

# 💬 Now render chat after all updates (including assistant reply)
# 💬 Render chat with latest message at the top
for message in reversed(st.session_state.chat_history):
    role = message["role"]
    content = message["content"]
    with st.chat_message("🧑‍💻 User" if role == "user" else "🤖 Assistant"):
        st.markdown(content)