from langchain.tools import tool
import os
import requests
from dotenv import load_dotenv
import httpx
import time
from datetime import datetime, timezone
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

BASE_URL  = os.getenv("MCP_GRAFANA_URL")
TOKEN     = os.getenv("MCP_GRAFANA_TOKEN")
NAMESPACE = os.getenv("NAMESPACE")

# ── Module-level cache ─────────────────────────────────────────────
_session_cache  = None
_prom_uid_cache = None


def _get_session() -> requests.Session:
    """Return a cached requests session with Grafana auth headers."""
    global _session_cache
    if _session_cache is None:
        s = requests.Session()
        s.headers.update({
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        })
        s.verify = False
        _session_cache = s
    return _session_cache


def _get_prom_uid() -> str:
    """Return cached Prometheus datasource UID, fetching once if needed."""
    global _prom_uid_cache
    if _prom_uid_cache is None:
        session     = _get_session()
        datasources = session.get(f"{BASE_URL}/api/datasources").json()
        prom_ds     = next((d for d in datasources if d.get("type") == "prometheus"), None)
        if not prom_ds:
            raise RuntimeError("No Prometheus datasource found in Grafana")
        _prom_uid_cache = prom_ds["uid"]
        print(f"[cache] Prometheus UID: {_prom_uid_cache}")
    return _prom_uid_cache


def _query_prometheus(queries: list, from_ms: int, to_ms: int) -> dict:
    """
    POST all PromQL queries to Grafana in one request.
    queries: list of dicts with keys: refId, expr, format, instant
    """
    session = _get_session()
    ds_uid  = _get_prom_uid()

    full_queries = [
        {
            "refId":      q["refId"],
            "datasource": {"uid": ds_uid, "type": "prometheus"},
            "expr":       q["expr"],
            "format":     q.get("format", "table"),
            "instant":    q.get("instant", True),
        }
        for q in queries
    ]

    payload = {
        "from":    str(from_ms),
        "to":      str(to_ms),
        "queries": full_queries,
    }

    resp = session.post(f"{BASE_URL}/api/ds/query", json=payload)
    resp.raise_for_status()
    return resp.json()


# ══════════════════════════════════════════════════════════════════
# UPTIME ROBOT TOOLS  (unchanged)
# ══════════════════════════════════════════════════════════════════

@tool
def get_mysoftware_sla() -> str:
    """Get the SLA / uptime percentage for GCP - status.cloud.google.com.
    Returns uptime ratios for last 7 days, last 30 days, and last 365 days,
    along with incident counts and total downtime. Use this tool whenever
    the user asks about SLA, uptime, availability, or reliability."""
    try:
        response = httpx.post(
            "https://api.uptimerobot.com/v2/getMonitors",
            data={
                "api_key": os.getenv("MYDNV_API_KEY_MAIN"),
                "format": "json",
                "custom_uptime_ratios": "7-30-365",
                "logs": "1",
                "logs_limit": "50",
            },
            timeout=30,
        )
        data     = response.json()
        monitors = data.get("monitors", [])
        if not monitors:
            return "No monitor data found for status.cloud.google.com."

        mon    = monitors[0]
        ratios = mon.get("custom_uptime_ratio", "N/A-N/A-N/A").split("-")
        uptime_7   = ratios[0] if len(ratios) > 0 else "N/A"
        uptime_30  = ratios[1] if len(ratios) > 1 else "N/A"
        uptime_365 = ratios[2] if len(ratios) > 2 else "N/A"

        logs         = mon.get("logs", [])
        incidents_7  = incidents_30  = incidents_365  = 0
        downtime_7   = downtime_30   = downtime_365   = 0
        now          = datetime.now().timestamp()

        for log_entry in logs:
            if log_entry.get("type", 0) == 1:
                duration = log_entry.get("duration", 0)
                log_time = log_entry.get("datetime", 0)
                age_days = (now - log_time) / 86400
                if age_days <= 7:
                    incidents_7  += 1;  downtime_7   += duration
                if age_days <= 30:
                    incidents_30 += 1;  downtime_30  += duration
                if age_days <= 365:
                    incidents_365 += 1; downtime_365 += duration

        def fmt_duration(secs):
            h, rem = divmod(int(secs), 3600)
            m, s   = divmod(rem, 60)
            parts  = []
            if h: parts.append(f"{h}h")
            if m: parts.append(f"{m}m")
            parts.append(f"{s}s")
            return " ".join(parts)

        return (
            f"SLA for GCP - status.cloud.google.com:\n"
            f"- Last 7 days:   {uptime_7}% uptime, {incidents_7} incidents, {fmt_duration(downtime_7)} down\n"
            f"- Last 30 days:  {uptime_30}% uptime, {incidents_30} incidents, {fmt_duration(downtime_30)} down\n"
            f"- Last 365 days: {uptime_365}% uptime, {incidents_365} incidents, {fmt_duration(downtime_365)} down"
        )
    except Exception as e:
        return f"Error fetching SLA data: {e}"


@tool
def get_monitor_status() -> str:
    """Get the current status of GCP - status.cloud.google.com monitor.
    Returns whether the site is UP, DOWN, or PAUSED, how long it has been
    in that state, and basic monitor details.
    Use this when the user asks about current status, is the site up/down, health check."""
    try:
        response = httpx.post(
            "https://api.uptimerobot.com/v2/getMonitors",
            data={
                "api_key": os.getenv("MYDNV_API_KEY_MAIN"),
                "format": "json",
                "monitors": os.getenv("MONITOR_ID"),
                "logs": "1",
                "logs_limit": "5",
            },
            timeout=30,
        )
        data     = response.json()
        monitors = data.get("monitors", [])
        if not monitors:
            return "No monitor data found."

        mon         = monitors[0]
        status_map  = {0: "Paused", 1: "Not checked yet", 2: "UP", 8: "Seems down", 9: "DOWN"}
        status_code = mon.get("status", -1)
        status      = status_map.get(status_code, "Unknown")
        friendly_name = mon.get("friendly_name", "Unknown")
        url           = mon.get("url", "Unknown")

        duration_str = "N/A"
        logs = mon.get("logs", [])
        if logs:
            last_change_ts = logs[0].get("datetime", 0)
            if last_change_ts:
                now     = datetime.now().timestamp()
                elapsed = int(now - last_change_ts)
                days    = elapsed // 86400
                hours   = (elapsed % 86400) // 3600
                minutes = (elapsed % 3600) // 60
                seconds = elapsed % 60
                parts   = []
                if days:    parts.append(f"{days} day{'s' if days != 1 else ''}")
                if hours:   parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                if minutes: parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                if seconds and not days:
                    parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                duration_str = ", ".join(parts) if parts else "just now"

        return (
            f"Monitor: {friendly_name}\n"
            f"URL: {url}\n"
            f"Current Status: **{status}**\n"
            f"Status Duration: {status} for {duration_str}\n"
            f"Check Interval: {mon.get('interval', 'N/A')}s"
        )
    except Exception as e:
        return f"Error fetching monitor status: {e}"


@tool
def get_monitor_incidents(days: int = 30) -> str:
    """Get incident history (downtime/up events) for GCP - status.cloud.google.com.
    Returns incidents with IDs, UTC timestamps, durations, cause codes, and reasons.
    Parameter 'days' controls how far back to look (default 30).
    Use this when user asks about incidents, outages, downtime events, or problems."""
    try:
        response = httpx.post(
            "https://api.uptimerobot.com/v2/getMonitors",
            data={
                "api_key": os.getenv("MYDNV_API_KEY_MAIN"),
                "format": "json",
                "monitors": os.getenv("MONITOR_ID"),
                "logs": "1",
                "logs_limit": "50",
                "log_types": "1-2",
            },
            timeout=30,
        )
        data     = response.json()
        monitors = data.get("monitors", [])
        if not monitors:
            return "No monitor data found."

        logs   = monitors[0].get("logs", [])
        now    = datetime.now().timestamp()
        cutoff = now - (days * 86400)

        incidents = []
        for log in logs:
            log_time = log.get("datetime", 0)
            if log_time < cutoff:
                continue

            log_id   = log.get("id", "N/A")
            log_type = log.get("type", 0)
            type_map = {1: "DOWN", 2: "UP (Resolved)", 98: "Started", 99: "Paused"}
            status   = type_map.get(log_type, f"Type {log_type}")
            duration = log.get("duration", 0)
            reason   = log.get("reason", {})

            if isinstance(reason, dict):
                reason_code   = reason.get("code", "")
                reason_detail = reason.get("detail", "N/A")
            else:
                reason_code   = ""
                reason_detail = str(reason)

            from datetime import timezone as tz
            dt_utc = datetime.fromtimestamp(log_time, tz=tz.utc)
            dt_str = dt_utc.strftime("%B %d, %Y, %I:%M %p (UTC)")

            dur_parts = []
            h, rem = divmod(int(duration), 3600)
            m, s   = divmod(rem, 60)
            if h: dur_parts.append(f"{h} hour{'s' if h != 1 else ''}")
            if m: dur_parts.append(f"{m} minute{'s' if m != 1 else ''}")
            if s: dur_parts.append(f"{s} second{'s' if s != 1 else ''}")
            dur_str = ", ".join(dur_parts) if dur_parts else "0s"

            cause = f"{reason_code} {reason_detail}".strip() if reason_code else reason_detail

            incidents.append(
                f"- Incident ID: {log_id}\n"
                f"  Status: {status}\n"
                f"  Time (UTC): {dt_str}\n"
                f"  Duration: {dur_str}\n"
                f"  Cause: {cause}"
            )

        if not incidents:
            return f"No incidents found in the last {days} day{'s' if days != 1 else ''} for GCP - status.cloud.google.com."

        return (
            f"Incidents for GCP - status.cloud.google.com (last {days} day{'s' if days != 1 else ''}):\n\n"
            + "\n\n".join(incidents)
        )
    except Exception as e:
        return f"Error fetching incidents: {e}"


@tool
def get_monitor_response_times(hours: int = 24) -> str:
    """Get response time data for GCP - status.cloud.google.com.
    Returns average, min, max response times and recent measurements.
    Parameter 'hours' controls lookback period (default 24).
    Use this when user asks about response time, latency, speed, or performance."""
    try:
        response = httpx.post(
            "https://api.uptimerobot.com/v2/getMonitors",
            data={
                "api_key": os.getenv("MYDNV_API_KEY_MAIN"),
                "format": "json",
                "monitors": os.getenv("MONITOR_ID"),
                "response_times": "1",
                "response_times_limit": "48",
            },
            timeout=30,
        )
        data     = response.json()
        monitors = data.get("monitors", [])
        if not monitors:
            return "No monitor data found."

        mon      = monitors[0]
        avg_resp = mon.get("average_response_time", "N/A")
        resp_times = mon.get("response_times", [])

        now    = datetime.now().timestamp()
        cutoff = now - (hours * 3600)

        recent = []
        values = []
        for rt in resp_times:
            rt_time = rt.get("datetime", 0)
            if rt_time >= cutoff:
                val    = rt.get("value", 0)
                dt_str = datetime.fromtimestamp(rt_time).strftime("%Y-%m-%d %H:%M")
                recent.append(f"  {dt_str}: {val}ms")
                if val:
                    values.append(val)

        summary  = f"Response Times for GCP - status.cloud.google.com (last {hours}h):\n"
        summary += f"- Overall Average: {avg_resp}ms\n"
        if values:
            summary += f"- Period Average: {sum(values) // len(values)}ms\n"
            summary += f"- Min: {min(values)}ms | Max: {max(values)}ms\n"
            summary += f"- Measurements: {len(values)}\n"
        if recent:
            summary += "Recent measurements:\n" + "\n".join(recent[:10])

        return summary
    except Exception as e:
        return f"Error fetching response times: {e}"


# ══════════════════════════════════════════════════════════════════
# PROMETHEUS / GRAFANA TOOLS  (cached + batched)
# ══════════════════════════════════════════════════════════════════

@tool
def get_all_deployments_json():
    """
    Returns all GCP services being monitored via Prometheus.
    Queries gcp_service_uptime_percent to get the list of service names.
    Use when user asks: what services do we have, list GCP services.
    """
    try:
        now_ms  = int(time.time() * 1000)
        from_ms = now_ms - 5 * 60 * 1000  # last 5 minutes

        data   = _query_prometheus(
            [{"refId": "A", "expr": "gcp_service_uptime_percent",
              "format": "time_series", "instant": True}],
            from_ms, now_ms,
        )

        services = set()
        for frame in data.get("results", {}).get("A", {}).get("frames", []) or []:
            for f in frame.get("schema", {}).get("fields", []) or []:
                service = (f.get("labels") or {}).get("service")
                if service:
                    services.add(service)

        return {
            "namespace":   "GCP",
            "count":       len(services),
            "deployments": sorted(services),
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_all_pod_resources_json(INTERVAL="4h", RESOLUTION="5m", lookback_minutes=30):
    """
    Returns GCP service health metrics — uptime % and health score — for all services.
    Use when user asks: health scores, uptime percentage, which services are healthy/degraded.
    """
    try:
        now_ms  = int(time.time() * 1000)
        from_ms = now_ms - lookback_minutes * 60 * 1000

        data = _query_prometheus(
            [
                {"refId": "uptime", "expr": "gcp_service_uptime_percent",
                 "format": "table", "instant": True},
                {"refId": "health", "expr": "gcp_service_health_score",
                 "format": "table", "instant": True},
            ],
            from_ms, now_ms,
        )

        services = {}
        for ref_id in ["uptime", "health"]:
            for frame in data.get("results", {}).get(ref_id, {}).get("frames", []) or []:
                fields      = frame.get("schema", {}).get("fields", []) or []
                value_field = next((f for f in fields if f.get("name") == "Value"), None)
                if not value_field:
                    continue
                labels  = value_field.get("labels") or {}
                service = labels.get("service")
                region  = labels.get("region", "N/A")
                if not service:
                    continue
                vals = frame.get("data", {}).get("values", [])
                if len(vals) < 2 or not vals[1]:
                    continue
                value = vals[1][0]
                if service not in services:
                    services[service] = {
                        "service":      service,
                        "region":       region,
                        "uptime":       None,
                        "health_score": None,
                    }
                if ref_id == "uptime":
                    services[service]["uptime"] = round(value, 4)
                elif ref_id == "health":
                    services[service]["health_score"] = round(value, 2)

        records = sorted(services.values(), key=lambda r: r["service"])
        return {
            "context": {
                "namespace":        "GCP",
                "lookback_minutes": lookback_minutes,
            },
            "pods": records,
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_pod_logs_json(
    pods=".*",
    containers=".*",
    search="",
    loki_uid=None,
    lookback_hours=6,
    limit=10,
):
    """
    Returns GCP active incident data from Prometheus formatted as log entries.
    Use when user asks: incidents, active issues, what is down, high severity problems.
    """
    try:
        now_ms  = int(time.time() * 1000)
        from_ms = now_ms - lookback_hours * 60 * 60 * 1000

        data = _query_prometheus(
            [
                {"refId": "incidents", "expr": "gcp_incident_active",
                 "format": "table", "instant": True},
                {"refId": "duration",  "expr": "gcp_incident_duration_minutes",
                 "format": "table", "instant": True},
            ],
            from_ms, now_ms,
        )

        incidents = {}

        # Parse active status
        for frame in data.get("results", {}).get("incidents", {}).get("frames", []) or []:
            fields      = frame.get("schema", {}).get("fields", []) or []
            value_field = next((f for f in fields if f.get("name") == "Value"), None)
            if not value_field:
                continue
            labels = value_field.get("labels") or {}
            inc_id = labels.get("id")
            if inc_id:
                incidents[inc_id] = {
                    "id":       inc_id,
                    "service":  labels.get("service"),
                    "severity": labels.get("severity"),
                    "status":   labels.get("status"),
                    "region":   labels.get("region"),
                    "duration": None,
                }

        # Parse duration
        for frame in data.get("results", {}).get("duration", {}).get("frames", []) or []:
            fields      = frame.get("schema", {}).get("fields", []) or []
            value_field = next((f for f in fields if f.get("name") == "Value"), None)
            if not value_field:
                continue
            labels = value_field.get("labels") or {}
            inc_id = labels.get("id")
            vals   = frame.get("data", {}).get("values", [])
            if inc_id and inc_id in incidents and len(vals) >= 2 and vals[1]:
                incidents[inc_id]["duration"] = vals[1][0]

        now  = datetime.now(tz=timezone.utc)
        logs = []
        for inc in incidents.values():
            emoji   = "🔴" if inc["status"] == "active" else "🟢"
            message = f"{emoji} [{inc['severity'].upper()}] {inc['service']} — {inc['status'].upper()}"
            if inc["duration"]:
                message += f" ({inc['duration']} min)"
            logs.append({
                "timestamp":   now.isoformat(),
                "pod":         inc["service"],
                "container":   inc["region"],
                "namespace":   "GCP",
                "message":     message,
                "incident_id": inc["id"],
                "severity":    inc["severity"],
                "status":      inc["status"],
            })

        # Sort: high → medium → low
        sev_order = {"high": 0, "medium": 1, "low": 2}
        logs.sort(key=lambda x: sev_order.get(x.get("severity", "low"), 3))

        return {
            "context": {
                "namespace": "GCP",
                "from":      f"now-{lookback_hours}h",
                "to":        "now",
            },
            "logs": logs,
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def list_datasources():
    """Retrieves all datasources connected to Grafana.
    Use when user asks about connected datasources or data sources."""
    try:
        return _get_session().get(f"{BASE_URL}/api/datasources").json()
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════
# POWER BI TOOLS  (unchanged)
# ══════════════════════════════════════════════════════════════════

def get_azure_access_token() -> str:
    tenant        = os.getenv("AZURE_TENANT_ID")
    client_id     = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    if not tenant or not client_id or not client_secret:
        raise ValueError("Missing AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET")
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    payload   = {
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         "https://analysis.windows.net/powerbi/api/.default",
        "grant_type":    "client_credentials",
    }
    resp = requests.post(token_url, data=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _execute_queries_call(dax_query: str) -> dict:
    dataset_id = os.getenv("POWERBI_DATASET_ID")
    if not dataset_id:
        raise ValueError("POWERBI_DATASET_ID is not set")
    group_id = os.getenv("POWERBI_WORKSPACE_ID")
    token    = get_azure_access_token()
    url      = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/executeQueries"
        if group_id else
        f"https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/executeQueries"
    )
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"queries": [{"query": dax_query}], "serializerSettings": {"includeNulls": True}}
    resp = requests.post(url, headers=hdrs, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _extract_rows(execute_queries_json: dict):
    try:
        return execute_queries_json["results"][0]["tables"][0].get("rows", [])
    except Exception:
        return []


@tool
def fetch_model_schema_compact() -> dict:
    """Fetch a compact LLM-safe version of the Power BI schema."""
    full = fetch_model_schema.invoke({"show_hidden": False})
    if "error" in full:
        return full
    compact = {}
    for table_name, table_obj in full["tables"].items():
        compact[table_name] = {
            "columns": [
                {"name": c.get("Name") or c.get("[Name]"),
                 "type": c.get("DataType") or c.get("[DataType]")}
                for c in table_obj.get("columns", [])
            ],
            "measures": [
                m.get("Name") or m.get("[Name]")
                for m in table_obj.get("measures", [])
            ],
        }
    return {"tables": compact, "tables_count": len(compact),
            "note": "Compact schema for LLM reasoning."}


@tool
def execute_dax_query(dax_query: str) -> dict:
    """Execute a DAX query against the configured Power BI semantic model."""
    dataset_id = os.getenv("POWERBI_DATASET_ID")
    group_id   = os.getenv("POWERBI_WORKSPACE_ID")
    token      = get_azure_access_token()
    url        = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/executeQueries"
        if group_id else
        f"https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/executeQueries"
    )
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"queries": [{"query": dax_query}], "serializerSettings": {"includeNulls": True}}
    resp = requests.post(url, headers=hdrs, json=body, timeout=60)
    if not resp.ok:
        try:    return {"ok": False, "status": resp.status_code, "error": resp.json()}
        except: return {"ok": False, "status": resp.status_code, "error": resp.text}
    return {"ok": True, "data": resp.json()}


@tool
def fetch_model_schema(show_hidden: bool = False) -> dict:
    """Fetch semantic model schema using INFO.VIEW.* metadata DAX queries."""
    dax_tables  = "EVALUATE INFO.VIEW.TABLES()"
    dax_columns = "EVALUATE INFO.VIEW.COLUMNS()"
    dax_measures = "EVALUATE INFO.VIEW.MEASURES()"
    dax_rels    = "EVALUATE INFO.VIEW.RELATIONSHIPS()"
    try:
        tables_rows  = _extract_rows(_execute_queries_call(dax_tables))
        columns_rows = _extract_rows(_execute_queries_call(dax_columns))
        measures_rows = _extract_rows(_execute_queries_call(dax_measures))
        rels_rows    = _extract_rows(_execute_queries_call(dax_rels))

        schema = {
            "summary": {"tables_count": 0,
                        "relationships_count": len(rels_rows),
                        "show_hidden": show_hidden},
            "tables": {},
            "relationships": rels_rows,
        }

        for t in tables_rows:
            tname = t.get("Name") or t.get("[Name]")
            if not tname:
                continue
            is_hidden = t.get("IsHidden") if "IsHidden" in t else t.get("[IsHidden]")
            if (not show_hidden) and (is_hidden is True):
                continue
            schema["tables"][tname] = {"tableMetadata": t, "columns": [], "measures": []}

        for c in columns_rows:
            tname = c.get("Table") or c.get("[Table]")
            if not tname:
                continue
            is_hidden = c.get("IsHidden") if "IsHidden" in c else c.get("[IsHidden]")
            if (not show_hidden) and (is_hidden is True):
                continue
            if tname not in schema["tables"]:
                schema["tables"][tname] = {"tableMetadata": {"Name": tname},
                                           "columns": [], "measures": []}
            schema["tables"][tname]["columns"].append(c)

        for m in measures_rows:
            tname = m.get("Table") or m.get("[Table]") or "__MODEL__"
            is_hidden = m.get("IsHidden") if "IsHidden" in m else m.get("[IsHidden]")
            if (not show_hidden) and (is_hidden is True):
                continue
            if tname not in schema["tables"]:
                schema["tables"][tname] = {"tableMetadata": {"Name": tname},
                                           "columns": [], "measures": []}
            schema["tables"][tname]["measures"].append(m)

        schema["summary"]["tables_count"] = len(schema["tables"])
        return schema

    except requests.HTTPError as e:
        return {"error": "Schema extraction failed.", "details": str(e)}
    except Exception as e:
        return {"error": "Unexpected error.", "details": str(e)}