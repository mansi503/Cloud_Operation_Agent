# gcp_mock_exporter.py
# Simulates GCP incidents.json data as Prometheus metrics
# Run this BEFORE starting Prometheus

from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
import random

# ── Mock GCP incident data (mirrors incidents.json structure) ──────
MOCK_INCIDENTS = [
    {
        "id": "inc-001",
        "service": "Google Compute Engine",
        "severity": "high",
        "status": "active",
        "region": "us-central1",
        "duration_minutes": 45,
        "affected_products": ["VM Instances", "Persistent Disk"],
    },
    {
        "id": "inc-002",
        "service": "Cloud Storage",
        "severity": "medium",
        "status": "resolved",
        "region": "europe-west1",
        "duration_minutes": 120,
        "affected_products": ["GCS Buckets"],
    },
    {
        "id": "inc-003",
        "service": "BigQuery",
        "severity": "low",
        "status": "resolved",
        "region": "us-east1",
        "duration_minutes": 15,
        "affected_products": ["Query Jobs"],
    },
    {
        "id": "inc-004",
        "service": "Cloud Run",
        "severity": "high",
        "status": "active",
        "region": "asia-east1",
        "duration_minutes": 30,
        "affected_products": ["Container Instances"],
    },
    {
        "id": "inc-005",
        "service": "Cloud SQL",
        "severity": "medium",
        "status": "monitoring",
        "region": "us-central1",
        "duration_minutes": 60,
        "affected_products": ["MySQL", "PostgreSQL"],
    },
]

# ── Mock GCP service uptime (%) ────────────────────────────────────
MOCK_SERVICES = [
    {"name": "compute_engine",    "uptime": 99.95, "region": "us-central1"},
    {"name": "cloud_storage",     "uptime": 99.99, "region": "us-central1"},
    {"name": "bigquery",          "uptime": 99.90, "region": "us-east1"},
    {"name": "cloud_run",         "uptime": 98.50, "region": "asia-east1"},
    {"name": "cloud_sql",         "uptime": 99.20, "region": "us-central1"},
    {"name": "kubernetes_engine", "uptime": 99.98, "region": "europe-west1"},
    {"name": "cloud_functions",   "uptime": 99.85, "region": "us-central1"},
]


def generate_metrics():
    lines = []

    # ── 1. Total active incidents count ───────────────────────────
    lines.append("# HELP gcp_active_incidents_total Number of currently active GCP incidents")
    lines.append("# TYPE gcp_active_incidents_total gauge")
    active = sum(1 for i in MOCK_INCIDENTS if i["status"] == "active")
    lines.append(f"gcp_active_incidents_total {active}")

    # ── 2. Per-incident status gauge ──────────────────────────────
    lines.append("# HELP gcp_incident_active Is this incident currently active (1=active, 0=resolved)")
    lines.append("# TYPE gcp_incident_active gauge")
    for inc in MOCK_INCIDENTS:
        val = 1 if inc["status"] == "active" else 0
        lines.append(
            f'gcp_incident_active{{id="{inc["id"]}",service="{inc["service"]}",severity="{inc["severity"]}",region="{inc["region"]}",status="{inc["status"]}"}} {val}'
        )

    # ── 3. Incident duration ───────────────────────────────────────
    lines.append("# HELP gcp_incident_duration_minutes Duration of incident in minutes")
    lines.append("# TYPE gcp_incident_duration_minutes gauge")
    for inc in MOCK_INCIDENTS:
        lines.append(
            f'gcp_incident_duration_minutes{{id="{inc["id"]}",service="{inc["service"]}",severity="{inc["severity"]}"}} {inc["duration_minutes"]}'
        )

    # ── 4. Incidents by severity ───────────────────────────────────
    lines.append("# HELP gcp_incidents_by_severity Count of incidents per severity")
    lines.append("# TYPE gcp_incidents_by_severity gauge")
    for sev in ["high", "medium", "low"]:
        count = sum(1 for i in MOCK_INCIDENTS if i["severity"] == sev)
        lines.append(f'gcp_incidents_by_severity{{severity="{sev}"}} {count}')

    # ── 5. Service uptime percentage ──────────────────────────────
    lines.append("# HELP gcp_service_uptime_percent Uptime percentage per GCP service")
    lines.append("# TYPE gcp_service_uptime_percent gauge")
    for svc in MOCK_SERVICES:
        # add tiny random drift to simulate live data
        uptime = round(svc["uptime"] + random.uniform(-0.05, 0.05), 4)
        uptime = min(100.0, max(0.0, uptime))
        lines.append(
            f'gcp_service_uptime_percent{{service="{svc["name"]}",region="{svc["region"]}"}} {uptime}'
        )

    # ── 6. Service health score (0-100) ───────────────────────────
    lines.append("# HELP gcp_service_health_score Overall health score 0-100")
    lines.append("# TYPE gcp_service_health_score gauge")
    for svc in MOCK_SERVICES:
        score = round(svc["uptime"] - random.uniform(0, 2), 1)
        lines.append(
            f'gcp_service_health_score{{service="{svc["name"]}",region="{svc["region"]}"}} {score}'
        )

    return "\n".join(lines) + "\n"


class MockExporterHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            body = generate_metrics().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress noisy logs

if __name__ == "__main__":
    port = 8000
    print(f"GCP mock exporter running → http://localhost:{port}/metrics")
    print("Press Ctrl+C to stop.")
    HTTPServer(("", port), MockExporterHandler).serve_forever()