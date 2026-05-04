from langchain.tools import tool
import os 
import requests
from dotenv import load_dotenv
import httpx
import time
from datetime import datetime, timezone

load_dotenv()

BASE_URL = os.getenv("MCP_GRAFANA_URL")
TOKEN = os.getenv("MCP_GRAFANA_TOKEN")
headers = {"Authorization": f"Bearer {TOKEN}"}
NAMESPACE = os.getenv("NAMESPACE")


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
        data = response.json()
        monitors = data.get("monitors", [])
        if not monitors:
            return "No monitor data found for status.cloud.google.com."

        mon = monitors[0]
        ratios = mon.get("custom_uptime_ratio", "N/A-N/A-N/A").split("-")
        uptime_7 = ratios[0] if len(ratios) > 0 else "N/A"
        uptime_30 = ratios[1] if len(ratios) > 1 else "N/A"
        uptime_365 = ratios[2] if len(ratios) > 2 else "N/A"

        # Count incidents and downtime from logs
        logs = mon.get("logs", [])
        incidents_7 = 0
        incidents_30 = 0
        incidents_365 = 0
        downtime_7 = 0
        downtime_30 = 0
        downtime_365 = 0
        now = datetime.now().timestamp()
        for log_entry in logs:
            if log_entry.get("type", 0) == 1:  # type 1 = down
                duration = log_entry.get("duration", 0)
                log_time = log_entry.get("datetime", 0)
                age_days = (now - log_time) / 86400
                if age_days <= 7:
                    incidents_7 += 1
                    downtime_7 += duration
                if age_days <= 30:
                    incidents_30 += 1
                    downtime_30 += duration
                if age_days <= 365:
                    incidents_365 += 1
                    downtime_365 += duration

        def fmt_duration(secs):
            h, rem = divmod(int(secs), 3600)
            m, s = divmod(rem, 60)
            parts = []
            if h:
                parts.append(f"{h}h")
            if m:
                parts.append(f"{m}m")
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
        data = response.json()
        monitors = data.get("monitors", [])
        if not monitors:
            return "No monitor data found."

        mon = monitors[0]
        status_map = {0: "Paused", 1: "Not checked yet", 2: "UP", 8: "Seems down", 9: "DOWN"}
        status_code = mon.get("status", -1)
        status = status_map.get(status_code, "Unknown")
        friendly_name = mon.get("friendly_name", "Unknown")
        url = mon.get("url", "Unknown")

        # Calculate how long the monitor has been in its current state
        duration_str = "N/A"
        logs = mon.get("logs", [])
        if logs:
            last_change_ts = logs[0].get("datetime", 0)
            if last_change_ts:
                now = datetime.now().timestamp()
                elapsed = int(now - last_change_ts)
                days = elapsed // 86400
                hours = (elapsed % 86400) // 3600
                minutes = (elapsed % 3600) // 60
                seconds = elapsed % 60
                parts = []
                if days:
                    parts.append(f"{days} day{'s' if days != 1 else ''}")
                if hours:
                    parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                if minutes:
                    parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
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
        data = response.json()
        monitors = data.get("monitors", [])
        if not monitors:
            return "No monitor data found."

        logs = monitors[0].get("logs", [])
        now = datetime.now().timestamp()
        cutoff = now - (days * 86400)

        incidents = []
        for log in logs:
            log_time = log.get("datetime", 0)
            if log_time < cutoff:
                continue

            log_id = log.get("id", "N/A")
            log_type = log.get("type", 0)
            type_map = {1: "DOWN", 2: "UP (Resolved)", 98: "Started", 99: "Paused"}
            status = type_map.get(log_type, f"Type {log_type}")
            duration = log.get("duration", 0)
            reason = log.get("reason", {})
            if isinstance(reason, dict):
                reason_code = reason.get("code", "")
                reason_detail = reason.get("detail", "N/A")
            else:
                reason_code = ""
                reason_detail = str(reason)

            from datetime import timezone as tz
            dt_utc = datetime.fromtimestamp(log_time, tz=tz.utc)
            dt_str = dt_utc.strftime("%B %d, %Y, %I:%M %p (UTC)")

            # Format duration
            dur_parts = []
            h, rem = divmod(int(duration), 3600)
            m, s = divmod(rem, 60)
            if h:
                dur_parts.append(f"{h} hour{'s' if h != 1 else ''}")
            if m:
                dur_parts.append(f"{m} minute{'s' if m != 1 else ''}")
            if s:
                dur_parts.append(f"{s} second{'s' if s != 1 else ''}")
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
        data = response.json()
        monitors = data.get("monitors", [])
        if not monitors:
            return "No monitor data found."

        mon = monitors[0]
        avg_resp = mon.get("average_response_time", "N/A")
        resp_times = mon.get("response_times", [])

        now = datetime.now().timestamp()
        cutoff = now - (hours * 3600)

        recent = []
        values = []
        for rt in resp_times:
            rt_time = rt.get("datetime", 0)
            if rt_time >= cutoff:
                val = rt.get("value", 0)
                dt_str = datetime.fromtimestamp(rt_time).strftime("%Y-%m-%d %H:%M")
                recent.append(f"  {dt_str}: {val}ms")
                if val:
                    values.append(val)

        summary = f"Response Times for GCP - status.cloud.google.com (last {hours}h):\n"
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


@tool
def get_all_deployments_json():
    """
    Returns JSON containing all Kubernetes deployment names
    from Prometheus via Grafana API.
    """

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    session.verify = False

    # 1) Find Prometheus datasource
    datasources = session.get(f"{BASE_URL}/api/datasources").json()
    prom_ds = next((d for d in datasources if d.get("type") == "prometheus"), None)
    if not prom_ds:
        raise RuntimeError("No Prometheus datasource found")

    ds_uid = prom_ds["uid"]

    # 2) Build query payload
    payload = {
        "queries": [
            {
                "refId": "A",
                "datasource": {"uid": ds_uid, "type": "prometheus"},
                "expr": f'kube_deployment_status_replicas_available{{namespace="{NAMESPACE}"}}',
                "format": "time_series",   
                "instant": True
            }
        ]
    }

    # 3) Execute query
    resp = session.post(f"{BASE_URL}/api/ds/query", json=payload)
    resp.raise_for_status()
    data = resp.json()

    # 4) Parse deployment names
    deployments = set()

    result = data.get("results", {}).get("A", {})
    for frame in result.get("frames", []) or []:
        fields = frame.get("schema", {}).get("fields", []) or []
        for f in fields:
            labels = f.get("labels") or {}
            deployment = labels.get("deployment")
            if deployment:
                deployments.add(deployment)

    # 5) Output JSON
    return {
        "namespace": NAMESPACE,
        "count": len(deployments),
        "deployments": sorted(deployments)
    }


@tool
def get_all_pod_resources_json(INTERVAL="4h", RESOLUTION="5m", lookback_minutes=30):
    """It retrieves all pod names in KubeIT with their CPU, network, Storage I/O and memory information in json format"""
    
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    session.verify = False

    # Resolve Prometheus datasource UID
    datasources = session.get(f"{BASE_URL}/api/datasources").json()
    prom_ds = next((d for d in datasources if d.get("type") == "prometheus"), None)
    if not prom_ds:
        raise RuntimeError("No Prometheus datasource found in Grafana /api/datasources")

    ds_uid = prom_ds["uid"]

    def now_ms():
        return int(time.time() * 1000)

    # PromQL expressions
    CPU_QUOTA = [
        ("A", "CPU Usage",
         'sum(node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{namespace="$namespace"}) by (pod)'),
        ("B", "CPU Requests",
         'sum(cluster:namespace:pod_cpu:active:kube_pod_container_resource_requests{namespace="$namespace"}) by (pod)'),
        ("C", "CPU Requests %",
         'sum(node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{namespace="$namespace"}) by (pod) / '
         'sum(cluster:namespace:pod_cpu:active:kube_pod_container_resource_requests{namespace="$namespace"}) by (pod)'),
        ("D", "CPU Limits",
         'sum(cluster:namespace:pod_cpu:active:kube_pod_container_resource_limits{namespace="$namespace"}) by (pod)'),
        ("E", "CPU Limits %",
         'sum(node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{namespace="$namespace"}) by (pod) / '
         'sum(cluster:namespace:pod_cpu:active:kube_pod_container_resource_limits{namespace="$namespace"}) by (pod)'),
    ]

    MEMORY_QUOTA = [
        ("A", "Memory Usage",
         'sum(container_memory_working_set_bytes{namespace="$namespace",container!="", image!=""}) by (pod)'),
        ("B", "Memory Requests",
         'sum(cluster:namespace:pod_memory:active:kube_pod_container_resource_requests{namespace="$namespace"}) by (pod)'),
        ("C", "Memory Requests %",
         'sum(container_memory_working_set_bytes{namespace="$namespace",container!="", image!=""}) by (pod) / '
         'sum(cluster:namespace:pod_memory:active:kube_pod_container_resource_requests{namespace="$namespace"}) by (pod)'),
        ("D", "Memory Limits",
         'sum(cluster:namespace:pod_memory:active:kube_pod_container_resource_limits{namespace="$namespace"}) by (pod)'),
        ("E", "Memory Limits %",
         'sum(container_memory_working_set_bytes{namespace="$namespace",container!="", image!=""}) by (pod) / '
         'sum(cluster:namespace:pod_memory:active:kube_pod_container_resource_limits{namespace="$namespace"}) by (pod)'),
        ("F", "Memory Usage (RSS)",
         'sum(container_memory_rss{namespace="$namespace",container!=""}) by (pod)'),
        ("G", "Memory Usage (Cache)",
         'sum(container_memory_cache{namespace="$namespace",container!=""}) by (pod)'),
        ("H", "Memory Usage (Swap)",
         'sum(container_memory_swap{namespace="$namespace",container!=""}) by (pod)'),
    ]

    NETWORK = [
        ("A", "Receive Bandwidth (Bps)",
         'sum(irate(container_network_receive_bytes_total{namespace=~"$namespace"}[$__rate_interval])) by (pod)'),
        ("B", "Transmit Bandwidth (Bps)",
         'sum(irate(container_network_transmit_bytes_total{namespace=~"$namespace"}[$__rate_interval])) by (pod)'),
        ("C", "Receive Packets (pps)",
         'sum(irate(container_network_receive_packets_total{namespace=~"$namespace"}[$__rate_interval])) by (pod)'),
        ("D", "Transmit Packets (pps)",
         'sum(irate(container_network_transmit_packets_total{namespace=~"$namespace"}[$__rate_interval])) by (pod)'),
        ("E", "Rx Dropped (pps)",
         'sum(irate(container_network_receive_packets_dropped_total{namespace=~"$namespace"}[$__rate_interval])) by (pod)'),
        ("F", "Tx Dropped (pps)",
         'sum(irate(container_network_transmit_packets_dropped_total{namespace=~"$namespace"}[$__rate_interval])) by (pod)'),
    ]

    STORAGE_IO = [
        ("A", "IOPS Reads",
         'sum by(pod) (rate(container_fs_reads_total{container!="", namespace=~"$namespace"}[5m]))'),
        ("B", "IOPS Writes",
         'sum by(pod) (rate(container_fs_writes_total{container!="", namespace=~"$namespace"}[5m]))'),
        ("C", "IOPS Reads+Writes",
         'sum by(pod) (rate(container_fs_reads_total{container!="", namespace=~"$namespace"}[5m]) + '
         'rate(container_fs_writes_total{container!="", namespace=~"$namespace"}[5m]))'),
        ("D", "Throughput Read (Bps)",
         'sum by(pod) (rate(container_fs_reads_bytes_total{container!="", namespace=~"$namespace"}[5m]))'),
        ("E", "Throughput Write (Bps)",
         'sum by(pod) (rate(container_fs_writes_bytes_total{container!="", namespace=~"$namespace"}[5m]))'),
        ("F", "Throughput Read+Write (Bps)",
         'sum by(pod) (rate(container_fs_reads_bytes_total{container!="", namespace=~"$namespace"}[5m]) + '
         'rate(container_fs_writes_bytes_total{container!="", namespace=~"$namespace"}[5m]))'),
    ]

    def render_expr(expr: str) -> str:
        return (expr.replace("$namespace", NAMESPACE)
                    .replace("$interval", INTERVAL)
                    .replace("$resolution", RESOLUTION)
                    .replace("$__rate_interval", RESOLUTION))

    combined = []
    for ref, name, expr in CPU_QUOTA:
        combined.append((f"cpu_{ref}", "cpu", name, expr))
    for ref, name, expr in MEMORY_QUOTA:
        combined.append((f"mem_{ref}", "memory", name, expr))
    for ref, name, expr in NETWORK:
        combined.append((f"net_{ref}", "network", name, expr))
    for ref, name, expr in STORAGE_IO:
        combined.append((f"io_{ref}", "storage", name, expr))

    to_ms = now_ms()
    from_ms = to_ms - lookback_minutes * 60 * 1000

    payload = {
        "from": str(from_ms),
        "to": str(to_ms),
        "queries": [
            {
                "refId": uniq_ref,
                "datasource": {"uid": ds_uid, "type": "prometheus"},
                "expr": render_expr(expr),
                "format": "table",
                "instant": True
            }
            for (uniq_ref, _, _, expr) in combined
        ]
    }

    resp = session.post(f"{BASE_URL}/api/ds/query", json=payload)
    resp.raise_for_status()
    data = resp.json()

    ref_to_metric = {uniq_ref: (section, metric_name) for (uniq_ref, section, metric_name, _) in combined}

    pods = {}

    for uniq_ref, res in data.get("results", {}).items():
        section_metric = ref_to_metric.get(uniq_ref)
        if not section_metric:
            continue

        section, metric_name = section_metric

        for frame in (res.get("frames", []) or []):
            fields = frame.get("schema", {}).get("fields", []) or []

            value_field = next((f for f in fields if f.get("name") == "Value"), None)
            if not value_field:
                continue

            pod = (value_field.get("labels") or {}).get("pod")
            if not pod:
                continue

            values = frame.get("data", {}).get("values", [])
            if len(values) < 2 or not values[1]:
                continue

            ts = values[0][0] if values and values[0] else None
            val = values[1][0]

            rec = pods.setdefault(pod, {"cpu": {}, "memory": {}, "network": {}, "storage": {}})
            rec[section][metric_name] = val
            if ts is not None:
                rec["_timestamp_ms"] = ts

    records = [{"pod": pod, **metrics} for pod, metrics in pods.items()]
    records.sort(key=lambda r: r["pod"])

    out = {
        "context": {
            "namespace": NAMESPACE,
            "interval": INTERVAL,
            "resolution": RESOLUTION,
            "rate_interval": RESOLUTION,
            "lookback_minutes": lookback_minutes,
            "datasource_uid": ds_uid,
            "from_ms": from_ms,
            "to_ms": to_ms,
        },
        "pods": records
    }

    return out


@tool
def get_pod_logs_json(
    pods=".*",
    containers=".*",
    search="",
    loki_uid=None,
    lookback_hours=6,
    limit=10
):
    """
    Extract logs from Grafana Loki (Tenant / Logs / Search dashboard)
    Returns LLM-friendly JSON.
    """

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    session.verify = False

    if not loki_uid:
        datasources = session.get(f"{BASE_URL}/api/datasources").json()
        loki_ds = next((d for d in datasources if d.get("type") == "loki"), None)
        if not loki_ds:
            raise RuntimeError("No Loki datasource found in Grafana")
        loki_uid = loki_ds["uid"]

    to_ms = int(time.time() * 1000)
    from_ms = to_ms - lookback_hours * 60 * 60 * 1000

    logql = f'{{container=~"{containers}", namespace="{NAMESPACE}", pod=~"{pods}"}}'

    if search:
        logql += f' |~ "{search}"'

    payload = {
        "from": str(from_ms),
        "to": str(to_ms),
        "queries": [
            {
                "refId": "A",
                "datasource": {
                    "uid": loki_uid,
                    "type": "loki"
                },
                "expr": logql,
                "queryType": "range",
                "maxLines": limit
            }
        ]
    }

    resp = session.post(f"{BASE_URL}/api/ds/query", json=payload)
    resp.raise_for_status()
    data = resp.json()

    logs = []

    frames = data.get("results", {}).get("A", {}).get("frames", [])

    for frame in frames:
        fields = frame["schema"]["fields"]
        values = frame["data"]["values"]

        field_names = [f["name"] for f in fields]
        rows = zip(*values)

        for row in rows:
            row_dict = dict(zip(field_names, row))

            ts_ns = row_dict.get("ts") or row_dict.get("Time")
            msg = row_dict.get("Line") or row_dict.get("line") or row_dict.get("message") or row_dict.get("Value")

            labels = row_dict.get("labels", {})

            logs.append({
                "timestamp": datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc).isoformat()
                             if isinstance(ts_ns, (int, float)) else None,
                "pod": labels.get("pod"),
                "container": labels.get("container"),
                "namespace": labels.get("namespace"),
                "message": msg,
            })

    result = {
        "context": {
            "namespace": NAMESPACE,
            "pods": pods,
            "containers": containers,
            "search": search,
            "from": f"now-{lookback_hours}h",
            "to": "now",
            "loki_uid": loki_uid,
        },
        "logs": logs
    }

    return result


@tool
def list_datasources():
    """It retrieves all the datasources that are connected and providing data to grafana"""
    datasources = requests.get(f"{BASE_URL}/api/datasources", headers=headers, verify=False)
    datasources = datasources.json()
    return datasources


# =============================================================================
# Azure AD token using Service Principal (Power BI)
# =============================================================================
def get_azure_access_token() -> str:
    """
    Get Azure AD token for Power BI REST API using client_credentials.
    Requires: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
    """
    tenant = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")

    if not tenant or not client_id or not client_secret:
        raise ValueError("Missing AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET")

    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://analysis.windows.net/powerbi/api/.default",
        "grant_type": "client_credentials",
    }

    resp = requests.post(token_url, data=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _execute_queries_call(dax_query: str) -> dict:
    """Internal helper to call Power BI ExecuteQueries and return raw JSON."""
    dataset_id = os.getenv("POWERBI_DATASET_ID")
    if not dataset_id:
        raise ValueError("POWERBI_DATASET_ID is not set")

    group_id = os.getenv("POWERBI_WORKSPACE_ID")
    token = get_azure_access_token()

    if group_id:
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/executeQueries"
    else:
        url = f"https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/executeQueries"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    body = {
        "queries": [{"query": dax_query}],
        "serializerSettings": {"includeNulls": True},
    }

    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _extract_rows(execute_queries_json: dict):
    """Extract rows array from ExecuteQueries response."""
    try:
        return execute_queries_json["results"][0]["tables"][0].get("rows", [])
    except Exception:
        return []


@tool
def fetch_model_schema_compact() -> dict:
    """
    Fetch a compact, LLM-safe version of the Power BI schema.
    Returns only table names, column names + data types, and measure names.
    Designed to stay well below token limits.
    """
    full = fetch_model_schema.invoke({"show_hidden": False})

    if "error" in full:
        return full

    compact = {}

    for table_name, table_obj in full["tables"].items():
        compact[table_name] = {
            "columns": [
                {
                    "name": c.get("Name") or c.get("[Name]"),
                    "type": c.get("DataType") or c.get("[DataType]")
                }
                for c in table_obj.get("columns", [])
            ],
            "measures": [
                m.get("Name") or m.get("[Name]")
                for m in table_obj.get("measures", [])
            ]
        }

    return {
        "tables": compact,
        "tables_count": len(compact),
        "note": "Compact schema for LLM reasoning. Full metadata not included."
    }


@tool
def execute_dax_query(dax_query: str) -> dict:
    """
    Execute a DAX query against the configured Power BI semantic model.
    Pass the EXACT DAX query string.
    Returns raw ExecuteQueries JSON.
    """
    dataset_id = os.getenv("POWERBI_DATASET_ID")
    group_id = os.getenv("POWERBI_WORKSPACE_ID")
    token = get_azure_access_token()

    if group_id:
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/executeQueries"
    else:
        url = f"https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/executeQueries"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"queries": [{"query": dax_query}], "serializerSettings": {"includeNulls": True}}

    resp = requests.post(url, headers=headers, json=body, timeout=60)

    if not resp.ok:
        try:
            return {"ok": False, "status": resp.status_code, "error": resp.json()}
        except Exception:
            return {"ok": False, "status": resp.status_code, "error": resp.text}

    return {"ok": True, "data": resp.json()}


@tool
def fetch_model_schema(show_hidden: bool = False) -> dict:
    """
    Fetch semantic model schema using INFO.VIEW.* metadata DAX queries.
    Returns a JSON structure the LLM can use.
    """
    dax_tables = "EVALUATE INFO.VIEW.TABLES()"
    dax_columns = "EVALUATE INFO.VIEW.COLUMNS()"
    dax_measures = "EVALUATE INFO.VIEW.MEASURES()"
    dax_rels = "EVALUATE INFO.VIEW.RELATIONSHIPS()"

    try:
        tables_rows = _extract_rows(_execute_queries_call(dax_tables))
        columns_rows = _extract_rows(_execute_queries_call(dax_columns))
        measures_rows = _extract_rows(_execute_queries_call(dax_measures))
        rels_rows = _extract_rows(_execute_queries_call(dax_rels))

        schema = {
            "summary": {
                "tables_count": 0,
                "relationships_count": len(rels_rows),
                "show_hidden": show_hidden,
            },
            "tables": {},
            "relationships": rels_rows,
        }

        # Index tables
        for t in tables_rows:
            tname = t.get("Name") or t.get("[Name]")
            if not tname:
                continue

            is_hidden = t.get("IsHidden") if "IsHidden" in t else t.get("[IsHidden]")
            if (not show_hidden) and (is_hidden is True):
                continue

            schema["tables"][tname] = {
                "tableMetadata": t,
                "columns": [],
                "measures": [],
            }

        # Attach columns to tables
        for c in columns_rows:
            tname = c.get("Table") or c.get("[Table]")
            if not tname:
                continue

            is_hidden = c.get("IsHidden") if "IsHidden" in c else c.get("[IsHidden]")
            if (not show_hidden) and (is_hidden is True):
                continue

            if tname not in schema["tables"]:
                schema["tables"][tname] = {
                    "tableMetadata": {"Name": tname},
                    "columns": [],
                    "measures": [],
                }

            schema["tables"][tname]["columns"].append(c)

        # Attach measures to tables
        for m in measures_rows:
            tname = m.get("Table") or m.get("[Table]") or "__MODEL__"

            is_hidden = m.get("IsHidden") if "IsHidden" in m else m.get("[IsHidden]")
            if (not show_hidden) and (is_hidden is True):
                continue

            if tname not in schema["tables"]:
                schema["tables"][tname] = {
                    "tableMetadata": {"Name": tname},
                    "columns": [],
                    "measures": [],
                }

            schema["tables"][tname]["measures"].append(m)

        schema["summary"]["tables_count"] = len(schema["tables"])
        return schema

    except requests.HTTPError as e:
        return {
            "error": "Schema extraction failed via ExecuteQueries.",
            "hint": "INFO.VIEW.* metadata queries may be blocked or require higher permissions.",
            "details": str(e),
        }
    except Exception as e:
        return {"error": "Unexpected error while extracting schema.", "details": str(e)}
