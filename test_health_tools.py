#!/usr/bin/env python3
"""
Quick test to verify health tool parsing works correctly.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# Test imports
print("Testing health tool imports and parsing...")
print()

try:
    from src.cloud_agent.helper_function import (
        get_all_pod_resources_json,
        get_pod_logs_json,
        get_all_deployments_json,
        get_health_summary,
    )
    print("✅ Successfully imported health tools")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

print()
print("=" * 80)
print("TEST 1: List services")
print("=" * 80)
try:
    result = get_all_deployments_json.invoke({})
    if "error" in result:
        print(f"❌ Error: {result.get('error')}")
    else:
        count = result.get("count", 0)
        services = result.get("deployments", [])
        print(f"✅ Found {count} services: {services}")
except Exception as e:
    print(f"❌ Exception: {e}")

print()
print("=" * 80)
print("TEST 2: Get service health metrics")
print("=" * 80)
try:
    result = get_all_pod_resources_json.invoke({})
    if "error" in result:
        print(f"❌ Error: {result.get('error')}")
        print(f"   Full result: {result}")
    else:
        pods = result.get("pods", [])
        if pods:
            print(f"✅ Found {len(pods)} services with health data:")
            for pod in pods[:5]:
                service = pod.get("service", "N/A")
                uptime = pod.get("uptime", "N/A")
                health = pod.get("health_score", "N/A")
                print(f"   - {service}: uptime={uptime}%, health={health}")
        else:
            print("❌ No pods returned")
except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("TEST 3: Get incidents")
print("=" * 80)
try:
    result = get_pod_logs_json.invoke({})
    if "error" in result:
        print(f"❌ Error: {result.get('error')}")
    else:
        logs = result.get("logs", [])
        note = result.get("note", "")
        if logs:
            print(f"✅ Found {len(logs)} incidents:")
            for log in logs[:3]:
                print(f"   - {log.get('message', 'N/A')}")
        else:
            print(f"✅ No incidents (healthy): {note}")
except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("TEST 4: Get complete health summary")
print("=" * 80)
try:
    result = get_health_summary.invoke({})
    if "error" in result:
        print(f"❌ Error: {result.get('error')}")
    else:
        services_count = result.get("services_count", 0)
        health_metrics = result.get("health_metrics", {})
        active_incidents = result.get("active_incidents", {})
        
        print(f"✅ Health Summary:")
        print(f"   Services: {services_count}")
        if health_metrics:
            print(f"   Health Status:")
            print(f"     - Healthy: {health_metrics.get('healthy', 0)}")
            print(f"     - Degraded: {health_metrics.get('degraded', 0)}")
            print(f"     - Critical: {health_metrics.get('critical', 0)}")
        if active_incidents:
            print(f"   Active Incidents: {active_incidents.get('count', 0)}")
except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("ALL TESTS COMPLETE")
print("=" * 80)
