import os
import asyncio
from typing import List, Dict
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"


async def setup():
    """Initialize Groq LLM."""
    print("🚀 Initializing Groq LLM...")

    if not GROQ_API_KEY:
        raise ValueError("❌ GROQ_API_KEY not set in .env file")

    model = ChatGroq(
        api_key=GROQ_API_KEY,
        model_name=GROQ_MODEL,
        temperature=0.7,
        timeout=30,
    )

    print(f"✅ Groq LLM ready! Using model: {GROQ_MODEL}")
    return model


def _is_uptime_query(text: str) -> bool:
    """Detect if the user is asking about uptime / monitoring."""
    keywords = [
        "uptime", "sla", "downtime", "outage", "incident",
        "status", "availability", "response time", "latency",
        "reliability", "monitor", "gcp", "google cloud",
        "google cloud platform", "status.cloud.google.com",
        "is gcp up", "is gcp down", "cloud status",
    ]
    return any(k in text.lower() for k in keywords)


def _build_uptime_agent(model):
    """Build a LangGraph react agent wired to all Uptime Robot tools."""
    from src.cloud_agent.helper_function import (
        get_mysoftware_sla,
        get_monitor_status,
        get_monitor_incidents,
        get_monitor_response_times,
    )
    from datetime import datetime

    today = datetime.now().strftime("%B %d, %Y")
    system_prompt = f"""Today's date is {today}. You are the Monitoring Agent for GCP (Google Cloud Platform).

MONITOR: GCP Status Feed | ID: {os.getenv("MONITOR_ID")} | URL: https://status.cloud.google.com/incidents.json

SCOPE: Only this GCP status monitor. Politely refuse questions about other monitors or services.

TOOL MAPPING — always pick the right tool:
- SLA / uptime / availability / reliability   → get_mysoftware_sla
- Current status (up / down / paused)         → get_monitor_status
- Incidents / outages / downtime events        → get_monitor_incidents  (set days as needed)
- Response time / latency / performance        → get_monitor_response_times (set hours as needed)

RULES:
- Only report data returned by tools. Never fabricate or guess.
- When reporting incidents, explain them in plain language as GCP service disruptions.
- Format results clearly for non-technical users.
- On errors, summarize in plain language. Never show raw JSON or stack traces."""

    tools = [
        get_mysoftware_sla,
        get_monitor_status,
        get_monitor_incidents,
        get_monitor_response_times,
    ]

    return create_react_agent(model, tools, prompt=system_prompt)


async def chat(user_input: str, model, history: List[Dict] = None) -> str:
    """
    Route the user query to the correct agent or plain LLM.

    Args:
        user_input: The user's message
        model: The Groq ChatGroq model
        history: Chat history (list of dicts with 'role' and 'content')

    Returns:
        Model's response text
    """
    print(f"📨 User: {user_input}")
    history = history or []

    # Build shared message list from history
    messages = []
    for item in history:
        if isinstance(item, dict):
            role = item.get("role", "user").lower()
            content = item.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role in ("assistant", "ai"):
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_input))

    try:
        # --- Uptime / monitoring questions ---
        if _is_uptime_query(user_input):
            print("📡 Routing to Uptime agent...")
            agent = _build_uptime_agent(model)
            result = await agent.ainvoke({"messages": messages})

            # Pull the last non-empty AIMessage from the result
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage) and msg.content:
                    print(f"✅ Bot (uptime): {msg.content}")
                    return msg.content

            return "The uptime agent did not return a response. Please try again."

        # --- Default: plain Groq LLM ---
        print("💬 Routing to default LLM...")
        response = await model.ainvoke(messages)
        print(f"✅ Bot: {response.content}")
        return response.content

    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        print(error_msg)
        return error_msg


# ----------------------------
# CLI TEST (for debugging)
# ----------------------------
if __name__ == "__main__":
    async def main():
        print("🚀 Starting Cloud Operation Agent CLI...")
        model = await setup()

        history = []
        print("\n💬 Chat with Groq LLM (type 'exit' to quit)\n")

        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                print("Bye! 👋")
                break

            if not user_input:
                continue

            response = await chat(user_input, model, history)
            print(f"Bot: {response}\n")

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})

    asyncio.run(main())