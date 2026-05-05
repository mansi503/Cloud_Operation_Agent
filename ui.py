import streamlit as st
import asyncio
import threading
import base64
from src.cloud_agent.brain import chat, setup


def get_base64_jpeg(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return ""


def escape_dollars(text: str) -> str:
    """Prevent Streamlit from rendering $ as LaTeX math delimiters."""
    return text.replace("$", "\\$")


img_data = get_base64_jpeg("static/images/coeLogo.jpg")
Login_info = {"admin": "passMITPU@123"}


@st.cache_resource
def get_cached_model():
    return asyncio.run(setup())


def _run_agent(prompt, model, history, holder, event):
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        holder["response"] = loop.run_until_complete(
            chat(prompt, model, history)
        )
    except Exception as e:
        holder["response"] = f"Error: {str(e)[:200]}"
    finally:
        if loop is not None:
            loop.close()
        event.set()


def check_login():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔐 Login")
        user   = st.text_input("Username")
        passwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if user in Login_info and Login_info[user] == passwd:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Invalid credentials")
        return False
    return True


# st.markdown(
#     f"""
#     <style>
#     .top-left-logo {{
#         position: fixed; top: 100px; left: 10px; z-index: 1000;
#     }}
#     .top-right-logo {{
#         position: fixed; top: 100px; right: 10px; z-index: 1000;
#     }}
#     .top-left-logo img, .top-right-logo img {{
#         width: 80px; height: auto; cursor: pointer;
#     }}
#     .top-left-logo img:hover, .top-right-logo img:hover {{
#         opacity: 0.85;
#     }}
#     </style>
#     <div class="top-left-logo">
#         <img src="https://cdn.onedesign.dnv.com/onedesigncdn/3.7.0/images/DNV_logo_RGB.svg" alt="DNV Logo">
#     </div>
#     {'<div class="top-right-logo"><img src="data:image/jpeg;base64,' + img_data + '" alt="COE Logo"></div>' if img_data else ''}
#     """,
#     unsafe_allow_html=True,
# )

st.title("☁️ Cloud Operational Agent")
st.divider()

if check_login():
    model = get_cached_model()

    st.markdown(
        """
        Ask me anything about your cloud infrastructure:
        - 💰 **FinOps** — *"What is my cost this month?"*, *"Forecast next 3 months"*
        - 📡 **Uptime** — *"Is GCP up?"*, *"Show me the SLA"*
        - 🏥 **Health** — *"What GCP services do we have?"*, *"Show service health scores"*
        """
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "generating" not in st.session_state:
        st.session_state.generating = False

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input(
        "Ask about costs, GCP health, uptime...",
        disabled=st.session_state.generating,
    ):
        st.session_state.generating = True
        st.session_state.pending_prompt = prompt
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    if st.session_state.generating:
        prompt  = st.session_state.get("pending_prompt", "")
        history = [msg for msg in st.session_state.messages[:-1]]

        result_holder = {}
        done_event    = threading.Event()
        worker = threading.Thread(
            target=_run_agent,
            args=(prompt, model, history, result_holder, done_event),
            daemon=True,
        )
        worker.start()

        with st.chat_message("assistant"):
            thinking_placeholder = st.empty()

        thinking_steps = ["🤔 Thinking...", "⚙️ Processing...", "💭 Generating response..."]
        step = 0
        while not done_event.wait(timeout=1):
            thinking_placeholder.markdown(thinking_steps[step % len(thinking_steps)])
            step += 1

        response = result_holder.get("response", "No response")

        # Escape $ to prevent LaTeX rendering
        display_response = escape_dollars(response)

        thinking_placeholder.markdown(display_response)
        st.session_state.messages.append({"role": "assistant", "content": display_response})
        st.session_state.generating = False
        st.session_state.pop("pending_prompt", None)
        st.rerun()