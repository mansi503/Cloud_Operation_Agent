"""
test_sheets.py — Google Sheets Integration Test ONLY
Run from project root: python test_sheets.py

Checks:
  1. credentials.json exists and is valid
  2. GOOGLE_SHEETS_ID is set in .env
  3. Can connect to Google Sheets API
  4. Can read Cloud_Cost_Daily tab and validate columns
  5. All 7 FinOps tools return valid responses
"""

import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

def ok(msg):      print(f"  {GREEN}✅ PASS{RESET} — {msg}")
def fail(msg):    print(f"  {RED}❌ FAIL{RESET} — {msg}")
def info(msg):    print(f"  {BLUE}ℹ️  INFO{RESET} — {msg}")
def section(msg): print(f"\n{YELLOW}{'─'*50}\n{msg}\n{'─'*50}{RESET}")

errors = []

# ─── TEST 1: credentials.json ─────────────────────────────────────────────────
section("TEST 1 — credentials.json")

creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

if not os.path.exists(creds_path):
    fail(f"credentials.json not found at: {creds_path}")
    errors.append("credentials.json missing")
else:
    ok(f"Found at: {creds_path}")
    try:
        with open(creds_path) as f:
            creds = json.load(f)
        missing = [k for k in ["type","project_id","client_email","private_key"] if k not in creds]
        if missing:
            fail(f"Missing keys: {missing}")
            errors.append("credentials.json invalid")
        else:
            ok("credentials.json valid")
            info(f"Service account : {creds.get('client_email')}")
            info(f"Project         : {creds.get('project_id')}")
    except json.JSONDecodeError as e:
        fail(f"Not valid JSON: {e}")
        errors.append("credentials.json parse error")

# ─── TEST 2: GOOGLE_SHEETS_ID ────────────────────────────────────────────────
section("TEST 2 — Environment Variable")

sheet_id = os.getenv("GOOGLE_SHEETS_ID")
if not sheet_id:
    fail("GOOGLE_SHEETS_ID not set in .env")
    errors.append("GOOGLE_SHEETS_ID missing")
else:
    ok(f"GOOGLE_SHEETS_ID set: {sheet_id[:10]}...{sheet_id[-5:]}")

# ─── TEST 3: API connection ───────────────────────────────────────────────────
section("TEST 3 — Google Sheets API Connection")

service = None
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds_obj = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    service   = build("sheets", "v4", credentials=creds_obj)
    ok("Google Sheets API client built successfully")

except ImportError:
    fail("Missing packages — run: pip install google-auth google-auth-oauthlib google-api-python-client")
    errors.append("Missing google packages")

except Exception as e:
    fail(f"Failed to build Sheets client: {e}")
    errors.append("Sheets client error")

# ─── TEST 4: Read sheet ───────────────────────────────────────────────────────
section("TEST 4 — Read Cloud_Cost_Daily Tab")

if service and sheet_id:
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range="Cloud_Cost_Daily!A1:M5")
            .execute()
        )
        rows = result.get("values", [])
        if not rows:
            fail("Sheet returned no data — check sharing permissions")
            errors.append("Sheet empty or inaccessible")
        else:
            ok(f"Read {len(rows)} rows successfully")
            headers = rows[0]
            info(f"Columns ({len(headers)}): {', '.join(headers)}")

            expected = ["Date", "Daily_Cost_USD", "Service", "Cloud_Provider", "Environment"]
            missing_cols = [c for c in expected if c not in headers]
            if missing_cols:
                fail(f"Missing columns: {missing_cols}")
                errors.append("Schema mismatch")
            else:
                ok("All expected columns present")
    except Exception as e:
        fail(f"Could not read sheet: {e}")
        info("Make sure you shared the sheet with your service account email")
        errors.append("Sheet read error")
else:
    info("Skipping — client or sheet_id not available")

# ─── TEST 5: All 7 FinOps tools ───────────────────────────────────────────────
section("TEST 5 — All 7 FinOps Tools")

try:
    from tools.gsheets_tool import (
        fetch_billing_schema,
        query_billing_data,
        get_current_month_cost,
        get_cost_trend,
        get_max_min_cost_period,
        get_cost_forecast,
        detect_cost_anomalies,
    )

    tests = [
        ("fetch_billing_schema",    fetch_billing_schema,    {}),
        ("get_current_month_cost",  get_current_month_cost,  {}),
        ("get_cost_trend",          get_cost_trend,          {"months": 3}),
        ("get_max_min_cost_period", get_max_min_cost_period, {}),
        ("get_cost_forecast",       get_cost_forecast,       {"months_ahead": 3}),
        ("detect_cost_anomalies",   detect_cost_anomalies,   {}),
        ("query_billing_data",      query_billing_data,      {
            "question": "Total GCP cost in 2024",
            "year": 2024,
            "provider": "GCP",
            "group_by": "Service"
        }),
    ]

    for name, fn, kwargs in tests:
        try:
            result = fn.invoke(kwargs)
            if isinstance(result, dict) and "error" in result:
                fail(f"{name}: {result['error']}")
                errors.append(f"{name} error")
            else:
                msg = result.get("message", "") if isinstance(result, dict) else str(result)
                ok(f"{name}")
                info(f"  → {msg[:120]}")
        except Exception as e:
            fail(f"{name}: {e}")
            errors.append(f"{name} exception")

except ImportError as e:
    fail(f"Cannot import gsheets_tool: {e}")
    info("Make sure tools/gsheets_tool.py and tools/__init__.py exist")
    errors.append("Import error")

# ─── SUMMARY ──────────────────────────────────────────────────────────────────
section("SUMMARY")

if not errors:
    print(f"\n{GREEN}🎉 All tests passed! Google Sheets integration is working.{RESET}\n")
else:
    print(f"\n{RED}⚠️  {len(errors)} issue(s):{RESET}")
    for i, e in enumerate(errors, 1):
        print(f"  {i}. {RED}{e}{RESET}")
    print(f"\nFix the above and re-run: {YELLOW}python test_sheets.py{RESET}\n")

sys.exit(0 if not errors else 1)