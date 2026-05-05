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

from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

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

    # FinOps — cost/billing questions
    if any(k in q for k in [
        "cost", "billing", "spend", "budget", "invoice", "finance",
        "how much", "price", "expensive", "cheap", "forecast",
        "anomaly", "anomalies", "trend", "monthly cost", "yearly cost",
        "last month", "this month", "last year", "this year",
    ]):
        return "finops"

    # Uptime — HTTP monitor / UptimeRobot questions
    if any(k in q for k in [
        "uptime", "sla", "downtime", "outage",
        "response time", "latency", "reliability",
        "monitor", "gcp status", "is gcp up", "is gcp down",
        "cloud status", "up or down", "status.cloud.google.com",
    ]):
        return "uptime"

    # Health — GCP service health via Prometheus/Grafana
    # Broad set of keywords covering GCP services, health, incidents
    if any(k in q for k in [
        # GCP service names
        "compute engine", "cloud storage", "bigquery", "cloud run",
        "cloud sql", "cloud functions", "kubernetes engine", "gke",
        # Health/metric concepts
        "health", "health score", "service health", "service status",
        "services", "gcp services", "what services",
        "incident", "incidents", "active incident",
        "severity", "high severity", "medium severity", "low severity",
        "degraded", "affected",
        # Prometheus/Grafana concepts
        "prometheus", "grafana", "metrics", "datasource",
        "uptime percent", "uptime percentage",
        # Generic infra terms kept for completeness
        "pod", "pods", "kubernetes", "k8s", "deployment",
        "container", "cpu", "memory", "logs", "namespace", "node",
    ]):
        return "health"

    return "default"


def _build_finops_agent(model):
    from datetime import datetime
    today = datetime.now().strftime("%B %d, %Y")
    system_prompt = f"""Today is {today}. You are the FinOps Agent for the CloudOps platform.

DATA SOURCE: Google Sheets billing dataset (GCP, AWS, Azure costs Jan 2023 to Apr 2026).

TOOL SELECTION — follow this strictly:
1. "this month" / "current month" / "how much this month"  → get_current_month_cost (no parameters)
2. "trend" / "over time" / "monthly comparison"            → get_cost_trend
3. "highest" / "lowest" / "most expensive month"           → get_max_min_cost_period
4. "forecast" / "predict" / "future cost"                  → get_cost_forecast
5. "anomaly" / "spike" / "unusual" / "unexpected"          → detect_cost_anomalies
6. "what data" / "schema" / "what services exist"          → fetch_billing_schema
7. Specific year / provider / service / breakdown          → query_billing_data

RESPONSE FORMAT — always structure answers like this:
**Summary**
One sentence answer with the key number.

**Breakdown**
- Item 1: value
- Item 2: value

**Insight**
One sentence of useful context or trend observation.

RULES:
- Never call query_billing_data for current month — use get_current_month_cost
- Only report data from tools. Never fabricate numbers.
- Always use USD with commas e.g. 12,345.67 (do NOT use dollar signs)
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
- SLA / uptime % / availability  → get_mysoftware_sla
- Current status (UP/DOWN)       → get_monitor_status
- Incidents / outages            → get_monitor_incidents (set days as needed)
- Response time / latency        → get_monitor_response_times (set hours as needed)

RESPONSE FORMAT:
**Status**
Current state in one line.

**Details**
Key metrics and numbers.

**Recent Activity**
Incidents or response time highlights if relevant.

RULES:
- Only report data from tools. Never fabricate.
- Describe incidents in plain English as GCP service disruptions.
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
    system_prompt = f"""Today is {today}. You are the GCP Infrastructure Health Agent.

DATA SOURCE: Prometheus metrics via Grafana API (local setup).

IMPORTANT: If a tool returns an "error" key, report it clearly to the user as:
"I was unable to fetch [data type]. Error: [error message]"
Never fall back to generic knowledge when a tool returns an error.

AVAILABLE METRICS:
- gcp_service_uptime_percent    — uptime % per service
- gcp_service_health_score      — health score 0-100
- gcp_incident_active           — active incidents with severity/region/status
- gcp_incident_duration_minutes — duration in minutes

SERVICES: compute_engine, cloud_storage, bigquery, cloud_run, cloud_sql,
          kubernetes_engine, cloud_functions

TOOL MAPPING:
- List GCP services              → get_all_deployments_json
- Uptime % and health scores     → get_all_pod_resources_json
- Active incidents               → get_pod_logs_json
- List Grafana datasources       → list_datasources

RESPONSE FORMAT:
**Service Health Overview**
| Service | Uptime | Health Score | Status |
|---------|--------|--------------|--------|
| ...     | ...    | ...          | ...    |

**Active Incidents**
List any active incidents with severity and duration.

**Summary**
One line overall assessment.

HEALTH CLASSIFICATION:
- Healthy  = uptime >= 99.0%
- Degraded = uptime 95.0% to 98.99%
- Critical = uptime < 95.0%

RULES:
- Call get_all_pod_resources_json for health/uptime questions
- Call get_pod_logs_json for incident questions
- If tool returns error key → report it, do not guess
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
    print(f"Route → {route}")

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
        print("Try: 'What is my cost this month?' / 'Is GCP up?' / 'What GCP services do we have?'\n")

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