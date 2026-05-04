import streamlit as st
import asyncio
import threading
import collections
from src.cloud_agent.brain import chat, setup
import base64

def get_base64_jpeg(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return ""

img_data = get_base64_jpeg("static/images/coeLogo.jpg")
Login_info = {"admin": "passMITPU@123"}


@st.cache_resource
def get_cached_model():
    """Initialize Groq model once and cache it."""
    return asyncio.run(setup())


def _run_agent(prompt, model, history, holder, event):
    """Background thread to get LLM response."""
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        holder["response"] = loop.run_until_complete(
            chat(prompt, model, history)
        )
    except Exception as e:
        holder["response"] = f"❌ Error: {str(e)[:200]}"
    finally:
        if loop is not None:
            loop.close()
        event.set()


def check_login():
    """Simple login check."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔐 Login")
        user = st.text_input("Username")
        passwd = st.text_input("Password", type="password")

        if st.button("Login"):
            if user in Login_info and Login_info[user] == passwd:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Invalid credentials")
        return False
    return True


# CSS Styling
st.markdown(
    f"""
    <style>
    .top-left-logo {{
        position: fixed;
        top: 100px;
        left: 10px;
        z-index: 1000;
    }}
    .top-right-logo {{
        position: fixed;
        top: 100px;
        right: 10px;
        z-index: 1000;
    }}
    .top-left-logo img, .top-right-logo img {{
        width: 80px;
        height: auto;
        cursor: pointer;
    }}
    .top-left-logo img:hover, .top-right-logo img:hover {{
        opacity: 0.85;
    }}
    div[data-testid="stButton"].stop-btn button {{
        background-color: #353740;
        color: white;
        border: 1px solid #565869;
        border-radius: 20px;
        padding: 0.4rem 1.2rem;
        font-size: 0.9rem;
    }}
    div[data-testid="stButton"].stop-btn button:hover {{
        background-color: #444654;
        border-color: #8e8ea0;
    }}
    </style>
    <div class="top-left-logo">
        <img src="https://cdn.onedesign.dnv.com/onedesigncdn/3.7.0/images/DNV_logo_RGB.svg" alt="DNV Logo">
    </div>
    {'<div class="top-right-logo"><img src="data:image/jpeg;base64,' + img_data + '" alt="COE Logo"></div>' if img_data else ''}
    """,
    unsafe_allow_html=True
)

st.title("☁️ Cloud Operational Agent")
st.divider()

if check_login():
    # Initialize model
    model = get_cached_model()

    st.markdown(
        """
        **Chat with Groq LLM** powered by free API!
        
        Just say "Hi" to test, or ask questions about:
        - Cloud operations
        - Kubernetes
        - Monitoring
        - Cost analysis
        
        *(Tools & data fetching coming soon)*
        """
    )

    # Session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "generating" not in st.session_state:
        st.session_state.generating = False

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # User input
    if prompt := st.chat_input("Type 'Hi' to test...", disabled=st.session_state.generating):
        st.session_state.generating = True
        st.session_state.pending_prompt = prompt
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    # Generate response
    if st.session_state.generating:
        prompt = st.session_state.get("pending_prompt", "")
        history = [msg for msg in st.session_state.messages[:-1]]

        result_holder = {}
        done_event = threading.Event()
        worker = threading.Thread(
            target=_run_agent,
            args=(prompt, model, history, result_holder, done_event),
            daemon=True,
        )
        worker.start()

        # Thinking animation
        with st.chat_message("assistant"):
            thinking_placeholder = st.empty()

        thinking_steps = [
            "🤔 Thinking...",
            "⚙️  Processing...",
            "💭 Generating response...",
        ]

        step = 0
        while not done_event.wait(timeout=1):
            thinking_placeholder.markdown(thinking_steps[step % len(thinking_steps)])
            step += 1

        # Display response
        response = result_holder.get("response", "No response")
        thinking_placeholder.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.generating = False
        st.session_state.pop("pending_prompt", None)
        st.rerun()
