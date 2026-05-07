#!/usr/bin/env python3
"""
Quick diagnostics script to verify Health tool connectivity and data availability.
Run this to debug why health queries return "No health data available".
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load env
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

BASE_URL = os.getenv("MCP_GRAFANA_URL")
TOKEN = os.getenv("MCP_GRAFANA_TOKEN")

print("=" * 80)
print("HEALTH TOOL DIAGNOSTICS")
print("=" * 80)
print()

# 1. Check environment variables
print("1. ENVIRONMENT VARIABLES")
print("-" * 80)
print(f"MCP_GRAFANA_URL:   {BASE_URL or '❌ NOT SET'}")
print(f"MCP_GRAFANA_TOKEN: {TOKEN[:20] + '...' if TOKEN else '❌ NOT SET'}")
print()

if not BASE_URL or not TOKEN:
    print("❌ Missing required environment variables. Cannot proceed.")
    exit(1)

# 2. Check Grafana connectivity
print("2. GRAFANA CONNECTIVITY")
print("-" * 80)
session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
})
session.verify = False

try:
    resp = session.get(f"{BASE_URL}/api/datasources", timeout=5)
    if resp.status_code == 200:
        print(f"✅ Grafana is reachable at {BASE_URL}")
        datasources = resp.json()
        print(f"   Found {len(datasources)} datasources:")
        for ds in datasources:
            ds_type = ds.get("type", "unknown")
            ds_name = ds.get("name", "unnamed")
            print(f"   - {ds_name} ({ds_type})")
    else:
        print(f"❌ Grafana returned status {resp.status_code}")
        exit(1)
except Exception as e:
    print(f"❌ Cannot reach Grafana: {str(e)}")
    exit(1)

# 3. Check Prometheus datasource
print()
print("3. PROMETHEUS DATASOURCE")
print("-" * 80)
prom_ds = next((d for d in datasources if d.get("type") == "prometheus"), None)
if prom_ds:
    prom_uid = prom_ds.get("uid")
    print(f"✅ Found Prometheus datasource")
    print(f"   UID: {prom_uid}")
    print(f"   URL: {prom_ds.get('url', 'N/A')}")
    
    # Try to query available metrics
    try:
        metrics_resp = session.get(
            f"{BASE_URL}/api/datasources/proxy/{prom_uid}/api/v1/label/__name__/values",
            timeout=5
        )
        if metrics_resp.status_code == 200:
            all_metrics = metrics_resp.json().get("data", [])
            gcp_metrics = [m for m in all_metrics if "gcp" in m.lower()]
            print(f"   Found {len(all_metrics)} total metrics")
            print(f"   Found {len(gcp_metrics)} GCP metrics:")
            for m in gcp_metrics[:10]:
                print(f"     - {m}")
        else:
            print(f"❌ Could not fetch metrics: HTTP {metrics_resp.status_code}")
    except Exception as e:
        print(f"❌ Error querying Prometheus: {str(e)}")
else:
    print("❌ No Prometheus datasource found in Grafana")
    print("   Please add Prometheus as a datasource in Grafana")
    exit(1)

# 4. Check mock exporter
print()
print("4. MOCK EXPORTER")
print("-" * 80)
try:
    exporter_resp = requests.get("http://localhost:8000/metrics", timeout=5)
    if exporter_resp.status_code == 200:
        print("✅ Mock exporter is running at http://localhost:8000/metrics")
        metrics_text = exporter_resp.text
        gcp_metrics_in_exporter = [line for line in metrics_text.split('\n') 
                                  if line.startswith('gcp_') and not line.startswith('#')]
        print(f"   Generating {len(gcp_metrics_in_exporter)} GCP metrics:")
        for m in gcp_metrics_in_exporter[:10]:
            print(f"     - {m.split('{')[0]}")
    else:
        print(f"❌ Mock exporter returned {exporter_resp.status_code}")
except Exception as e:
    print(f"⚠️  Mock exporter not running: {str(e)}")
    print("   Start it with: python gcp_mock_exporter.py")

# 5. Test actual Prometheus queries
print()
print("5. TEST PROMETHEUS QUERIES")
print("-" * 80)
if prom_ds:
    import time
    now_ms = int(time.time() * 1000)
    from_ms = now_ms - 5 * 60 * 1000  # Last 5 minutes
    
    queries = [
        {"refId": "uptime", "expr": "gcp_service_uptime_percent", "format": "table", "instant": True},
        {"refId": "health", "expr": "gcp_service_health_score", "format": "table", "instant": True},
    ]
    
    full_queries = [
        {
            "refId": q["refId"],
            "datasource": {"uid": prom_uid, "type": "prometheus"},
            "expr": q["expr"],
            "format": q["format"],
            "instant": q["instant"],
        }
        for q in queries
    ]
    
    payload = {
        "from": str(from_ms),
        "to": str(now_ms),
        "queries": full_queries,
    }
    
    try:
        query_resp = session.post(f"{BASE_URL}/api/ds/query", json=payload, timeout=10)
        if query_resp.status_code == 200:
            result = query_resp.json()
            results = result.get("results", {})
            
            for metric_name, ref_data in results.items():
                if ref_data.get("error"):
                    print(f"❌ Query '{metric_name}' failed: {ref_data.get('error')}")
                else:
                    frames = ref_data.get("frames", []) or []
                    print(f"✅ Query '{metric_name}' returned {len(frames)} frames")
                    if frames:
                        total_values = sum(len(f.get("data", {}).get("values", [])) for f in frames)
                        print(f"   Total data points: {total_values}")
        else:
            print(f"❌ Query failed: HTTP {query_resp.status_code}")
    except Exception as e:
        print(f"❌ Error executing queries: {str(e)}")

print()
print("=" * 80)
print("DIAGNOSTICS COMPLETE")
print("=" * 80)
print()
print("TROUBLESHOOTING GUIDE:")
print("- If mock exporter is not running → python gcp_mock_exporter.py")
print("- If Grafana can't see Prometheus → check Prometheus URL in Grafana datasource settings")
print("- If 'gcp_' metrics are 0 → make sure Prometheus scrape config includes mock exporter")
print("  Add to prometheus.yml scrape_configs:")
print("    - job_name: 'gcp-mock'")
print("      static_configs:")
print("        - targets: ['localhost:8000']")
print()
