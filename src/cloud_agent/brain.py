import os
import asyncio
from typing import List, Dict
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from tools.gsheets_tool import (
    fetch_billing_schema,
    query_billing_data,
    get_current_month_cost,
    get_cost_trend,
    get_max_min_cost_period,
    get_cost_forecast,
    detect_cost_anomalies,
)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL   = "llama-3.3-70b-versatile"


async def setup():
    print("Initializing Groq LLM...")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in .env file")
    model = ChatGroq(
        api_key=GROQ_API_KEY,
        model_name=GROQ_MODEL,
        temperature=0.7,
        timeout=30,
    )
    print(f"Groq LLM ready! Using model: {GROQ_MODEL}")
    return model


def classify_route(text: str) -> str:
    q = text.lower()
    if any(k in q for k in [
        "cost", "billing", "spend", "budget", "invoice", "finance",
        "how much", "price", "expensive", "cheap", "forecast",
        "anomaly", "anomalies", "trend", "monthly cost", "yearly cost",
        "last month", "this month", "last year", "this year",
    ]):
        return "finops"
    if any(k in q for k in [
        "uptime", "sla", "downtime", "outage", "incident",
        "status", "availability", "response time", "latency",
        "reliability", "monitor", "gcp status", "is gcp up",
        "is gcp down", "cloud status", "up or down",
    ]):
        return "uptime"
    if any(k in q for k in [
        "pod", "pods", "kubernetes", "k8s", "deployment", "deployments",
        "container", "cpu", "memory", "logs", "grafana", "prometheus",
        "loki", "crashloop", "resources", "namespace", "node",
    ]):
        return "health"
    return "default"


def _build_finops_agent(model):
    from datetime import datetime
    today = datetime.now().strftime("%B %d, %Y")
    system_prompt = f"""Today is {today}. You are the FinOps Agent for the CloudOps platform.

DATA SOURCE: Google Sheets billing dataset (GCP, AWS, Azure costs Jan 2023 to Apr 2026).

TOOL MAPPING:
- Schema / what data exists           → fetch_billing_schema
- General cost query with filters     → query_billing_data
- Current month spend                 → get_current_month_cost
- Monthly trend over time             → get_cost_trend
- Highest / lowest cost + reasons     → get_max_min_cost_period
- Predict future costs                → get_cost_forecast
- Detect billing spikes / anomalies   → detect_cost_anomalies

RULES:
- Call fetch_billing_schema first if unsure what data exists.
- Only report data from tools. Never fabricate numbers.
- Format costs with $ and commas (e.g. $12,345.67).
- Explain anomalies in plain business language.
- Never show raw JSON or stack traces."""

    return create_react_agent(model, [
        fetch_billing_schema, query_billing_data, get_current_month_cost,
        get_cost_trend, get_max_min_cost_period, get_cost_forecast, detect_cost_anomalies,
    ], prompt=system_prompt)


def _build_uptime_agent(model):
    from src.cloud_agent.helper_function import (
        get_mysoftware_sla, get_monitor_status,
        get_monitor_incidents, get_monitor_response_times,
    )
    from datetime import datetime
    today = datetime.now().strftime("%B %d, %Y")
    system_prompt = f"""Today is {today}. You are the Monitoring Agent for GCP (Google Cloud Platform).

MONITOR: GCP Status Feed | ID: {os.getenv("MONITOR_ID")} | URL: https://status.cloud.google.com/incidents.json

TOOL MAPPING:
- SLA / uptime % / availability       → get_mysoftware_sla
- Current status (UP/DOWN/PAUSED)     → get_monitor_status
- Incidents / outages / downtime      → get_monitor_incidents (set days as needed)
- Response time / latency             → get_monitor_response_times (set hours as needed)

RULES:
- Only report data from tools. Never fabricate.
- Explain incidents as GCP service disruptions in plain language.
- Never show raw JSON or stack traces."""

    return create_react_agent(model, [
        get_mysoftware_sla, get_monitor_status,
        get_monitor_incidents, get_monitor_response_times,
    ], prompt=system_prompt)


def _build_health_agent(model):
    from src.cloud_agent.helper_function import (
        get_all_deployments_json, get_all_pod_resources_json,
        get_pod_logs_json, list_datasources,
    )
    from datetime import datetime
    today = datetime.now().strftime("%B %d, %Y")
    system_prompt = f"""Today is {today}. You are the Infrastructure Health Agent for the CloudOps platform.

DATA SOURCES: Prometheus (metrics via Grafana), Loki (logs via Grafana).
NAMESPACE: {os.getenv("NAMESPACE", "default")}

TOOL MAPPING:
- List all deployments                → get_all_deployments_json
- Pod CPU/memory/network/storage      → get_all_pod_resources_json
- Pod or container logs               → get_pod_logs_json
- List connected datasources          → list_datasources

RULES:
- Only report data from tools. Never fabricate metrics.
- Summarize pod health as Healthy / Warning / Critical.
- Convert bytes to MB/GB, raw cores to millicores where helpful.
- Never show raw JSON or stack traces."""

    return create_react_agent(model, [
        get_all_deployments_json, get_all_pod_resources_json,
        get_pod_logs_json, list_datasources,
    ], prompt=system_prompt)


async def chat(user_input: str, model, history: List[Dict] = None) -> str:
    print(f"User: {user_input}")
    history = history or []

    messages = []
    for item in history:
        role    = item.get("role", "user").lower() if isinstance(item, dict) else item[0]
        content = item.get("content", "")          if isinstance(item, dict) else item[1]
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role in ("assistant", "ai"):
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_input))

    route = classify_route(user_input)
    print(f"Route: {route}")

    try:
        if route == "finops":
            agent = _build_finops_agent(model)
        elif route == "uptime":
            agent = _build_uptime_agent(model)
        elif route == "health":
            agent = _build_health_agent(model)
        else:
            print("Routing to default LLM...")
            response = await model.ainvoke(messages)
            return response.content

        result = await agent.ainvoke({"messages": messages})
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content
        return "The agent did not return a response. Please try again."

    except Exception as e:
        return f"Error in {route} agent: {str(e)}"


if __name__ == "__main__":
    async def main():
        print("Starting Cloud Operation Agent CLI...")
        model = await setup()
        history = []
        print("\nChat with CloudOps Agent (type 'exit' to quit)")
        print("Try: 'What is my cost this month?' / 'Is GCP up?' / 'Show pod CPU usage'\n")

        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                print("Bye!")
                break
            if not user_input:
                continue
            response = await chat(user_input, model, history)
            print(f"Bot: {response}\n")
            history.append({"role": "user",     "content": user_input})
            history.append({"role": "assistant", "content": response})

    asyncio.run(main())