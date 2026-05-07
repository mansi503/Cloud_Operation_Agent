"""
gsheets_tool.py — CloudOps Agent FinOps Tools
Replaces execute_dax_query + fetch_model_schema_compact from helper_function.py
Uses Google Sheets API as the billing data backend.

Environment variables required:
  GOOGLE_SHEETS_ID          — the Sheet ID from the URL
  GOOGLE_CREDENTIALS_PATH   — path to service account credentials.json

In demo: present this as "querying the Power BI billing semantic model"
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from langchain.tools import tool
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ─── CONFIG ──────────────────────────────────────────────────────────────────

SHEET_ID    = os.getenv("GOOGLE_SHEETS_ID")
CREDS_PATH  = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
SCOPES      = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Sheet tab names (must match your Google Sheet exactly)
SHEET_DAILY    = "Cloud_Cost_Daily"
SHEET_MONTHLY  = "Monthly_Summary"
SHEET_SERVICE  = "Service_Summary"

# ─── GOOGLE SHEETS CLIENT ────────────────────────────────────────────────────

_service_cache = None

def _validate_credentials():
    """Validate that credentials file exists and is readable."""
    if not os.path.exists(CREDS_PATH):
        raise FileNotFoundError(f"Credentials file not found: {CREDS_PATH}")
    if not os.path.isfile(CREDS_PATH):
        raise ValueError(f"Credentials path is not a file: {CREDS_PATH}")
    return True

def _get_sheets_service():
    """Build and cache the Google Sheets API service client."""
    global _service_cache
    if _service_cache:
        return _service_cache
    
    _validate_credentials()
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    _service_cache = build("sheets", "v4", credentials=creds)
    return _service_cache


def _read_sheet(tab_name: str) -> pd.DataFrame:
    """Read a full sheet tab into a pandas DataFrame."""
    service = _get_sheets_service()
    result  = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SHEET_ID, range=tab_name)
        .execute()
    )
    rows = result.get("values", [])
    if not rows:
        return pd.DataFrame()
    headers = rows[0]
    data    = rows[1:]
    # Pad short rows
    data = [r + [""] * (len(headers) - len(r)) for r in data]
    return pd.DataFrame(data, columns=headers)


def _load_daily() -> pd.DataFrame:
    """Load and type-cast Cloud_Cost_Daily sheet."""
    df = _read_sheet(SHEET_DAILY)

    # Google Sheets returns everything as strings — strip and convert
    df["Date"]           = pd.to_datetime(df["Date"], errors="coerce")
    df["Daily_Cost_USD"] = (
        df["Daily_Cost_USD"]
        .astype(str)
        .str.replace("$", "", regex=False)  # remove $ sign
        .str.replace(",", "", regex=False)  # remove comma separators
        .str.strip()
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )
    df["Year"]       = df["Date"].dt.year
    df["Month_Num"]  = df["Date"].dt.month
    df["Year_Month"] = df["Date"].dt.to_period("M").astype(str)

    # Drop rows where date parsing failed
    df = df.dropna(subset=["Date"])
    return df


# ─── LANGCHAIN TOOLS ─────────────────────────────────────────────────────────

@tool
def fetch_billing_schema() -> dict:
    """
    Fetch the schema (columns + sample values) of the cloud billing dataset.
    Use this first to understand what data is available before querying costs.
    Equivalent to fetch_model_schema_compact in Power BI.
    """
    try:
        df = _load_daily()
        schema = {
            "table": "Cloud_Cost_Daily",
            "total_rows": len(df),
            "columns": {
                col: {
                    "dtype": str(df[col].dtype),
                    "sample_values": df[col].dropna().unique()[:5].tolist()
                }
                for col in df.columns
            },
            "date_range": {
                "from": str(df["Date"].min().date()),
                "to":   str(df["Date"].max().date()),
            },
            "providers":    df["Cloud_Provider"].unique().tolist(),
            "services":     df["Service"].unique().tolist(),
            "environments": df["Environment"].unique().tolist(),
            "note": "Billing data covers GCP, AWS, Azure across Production/Staging/Development environments."
        }
        return schema
    except Exception as e:
        return {"error": str(e)}


@tool
def query_billing_data(
    question: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    provider: Optional[str] = None,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    group_by: Optional[str] = None,
) -> dict:
    """
    Query cloud billing data and answer cost questions.
    Equivalent to execute_dax_query in Power BI.

    Parameters:
      question    — natural language question being answered
      year        — filter by year (e.g. 2024)
      month       — filter by month number (e.g. 1 for January)
      provider    — filter by cloud provider: GCP, AWS, or Azure
      service     — filter by service name (e.g. EC2, BigQuery)
      environment — filter by environment: Production, Staging, Development
      group_by    — group results by: Cloud_Provider, Service, Environment, Region, Month, Year

    Use this for questions like:
      - What is my total cost this year?
      - What did AWS cost in Q1 2024?
      - Which service costs the most?
      - Cost breakdown by environment
    """
    try:
        df = _load_daily()

        # Apply filters
        if year:
            df = df[df["Year"] == int(year)]
        if month:
            df = df[df["Month_Num"] == int(month)]
        if provider:
            df = df[df["Cloud_Provider"].str.upper() == provider.upper()]
        if service:
            df = df[df["Service"].str.lower() == service.lower()]
        if environment:
            df = df[df["Environment"].str.lower() == environment.lower()]

        if df.empty:
            return {"question": question, "result": "No data found for the given filters.", "total_cost_usd": 0}

        total = round(df["Daily_Cost_USD"].sum(), 2)

        # Group if requested
        breakdown = {}
        if group_by and group_by in df.columns:
            breakdown = (
                df.groupby(group_by)["Daily_Cost_USD"]
                .sum()
                .round(2)
                .sort_values(ascending=False)
                .to_dict()
            )

        # Period label
        label_parts = []
        if year:        label_parts.append(str(year))
        if month:       label_parts.append(datetime(2000, month, 1).strftime("%B"))
        if provider:    label_parts.append(provider)
        if environment: label_parts.append(environment)
        label = " ".join(label_parts) if label_parts else "All Time"

        return {
            "question":       question,
            "period":         label,
            "total_cost_usd": total,
            "breakdown":      breakdown,
            "message":        f"Total cost for {label}: ${total:,.2f}"
                              + (f"\nBreakdown by {group_by}: {breakdown}" if breakdown else "")
        }
    except Exception as e:
        return {"error": str(e), "question": question}


@tool
def get_current_month_cost() -> dict:
    """
    Get total cloud spend for the current month broken down by provider.
    Use when user asks: what is my current cost, how much have I spent this month.
    """
    try:
        df  = _load_daily()
        now = datetime.now()
        sub = df[(df["Year"] == now.year) & (df["Month_Num"] == now.month)]

        # Fall back to latest available month if current month has no data
        if sub.empty:
            latest_ym = df["Year_Month"].max()
            sub = df[df["Year_Month"] == latest_ym]
            period = f"{latest_ym} (latest available)"
        else:
            period = now.strftime("%Y-%m")

        total       = round(sub["Daily_Cost_USD"].sum(), 2)
        by_provider = sub.groupby("Cloud_Provider")["Daily_Cost_USD"].sum().round(2).to_dict()
        by_service  = sub.groupby("Service")["Daily_Cost_USD"].sum().round(2).sort_values(ascending=False).to_dict()

        return {
            "period":         period,
            "total_cost_usd": total,
            "by_provider":    by_provider,
            "by_service":     by_service,
            "message":        f"Current cloud spend ({period}): ${total:,.2f}\n"
                              f"By provider: {by_provider}"
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_cost_trend(months: int = 6) -> dict:
    """
    Get month-over-month cost trend for the last N months.
    Use when user asks about cost trend, spending over time, monthly comparison.
    Default is last 6 months.
    """
    try:
        df = _load_daily()
        monthly = (
            df.groupby("Year_Month")["Daily_Cost_USD"]
            .sum()
            .reset_index()
            .sort_values("Year_Month")
            .tail(months)
        )
        monthly.columns = ["Year_Month", "Total_Cost"]
        monthly["Total_Cost"] = monthly["Total_Cost"].round(2)

        trend = monthly.to_dict(orient="records")

        # Add MoM change %
        for i in range(1, len(trend)):
            prev = trend[i-1]["Total_Cost"]
            curr = trend[i]["Total_Cost"]
            trend[i]["mom_change_pct"] = round((curr - prev) / prev * 100, 1) if prev else 0

        return {
            "months_analyzed": months,
            "trend":           trend,
            "message":         f"Cost trend for last {months} months: "
                               + ", ".join(f"{t['Year_Month']}: ${t['Total_Cost']:,.2f}" for t in trend)
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_max_min_cost_period() -> dict:
    """
    Find the months with highest and lowest cloud cost, including spike reasons.
    Use when user asks: when was max/min cost, most expensive month, cheapest month, why was cost high.
    """
    try:
        df      = _load_daily()
        monthly = df.groupby("Year_Month")["Daily_Cost_USD"].sum().reset_index()
        monthly.columns = ["Year_Month", "Total_Cost"]

        max_row = monthly.loc[monthly["Total_Cost"].idxmax()]
        min_row = monthly.loc[monthly["Total_Cost"].idxmin()]

        max_ym = max_row["Year_Month"]
        min_ym = min_row["Year_Month"]

        # Get spike reasons for max month
        spikes = (
            df[(df["Year_Month"] == max_ym) & (df["Spike_Reason"].notna()) & (df["Spike_Reason"] != "")]
            ["Spike_Reason"].unique().tolist()
        )

        return {
            "max_period":        max_ym,
            "max_cost_usd":      round(float(max_row["Total_Cost"]), 2),
            "max_spike_reasons": spikes,
            "min_period":        min_ym,
            "min_cost_usd":      round(float(min_row["Total_Cost"]), 2),
            "message": (
                f"Highest cost month: {max_ym} (${float(max_row['Total_Cost']):,.2f})"
                + (f"\nSpike reasons: {', '.join(spikes)}" if spikes else "")
                + f"\nLowest cost month: {min_ym} (${float(min_row['Total_Cost']):,.2f})"
            )
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_cost_forecast(months_ahead: int = 3) -> dict:
    """
    Forecast cloud costs for the next N months using linear regression on historical data.
    Use when user asks: predict cost, forecast spending, what will cost be next month/quarter.
    Default is 3 months ahead.
    """
    try:
        df = _load_daily()
        monthly = (
            df.groupby("Year_Month")["Daily_Cost_USD"]
            .sum()
            .reset_index()
            .sort_values("Year_Month")
        )
        costs = monthly["Daily_Cost_USD"].values
        x     = np.arange(len(costs))
        m, b  = np.polyfit(x, costs, 1)

        last_period = pd.Period(monthly["Year_Month"].iloc[-1], freq="M")
        forecast    = []
        for i in range(1, months_ahead + 1):
            pred = round(float(m * (len(costs) + i - 1) + b), 2)
            forecast.append({
                "period":             str(last_period + i),
                "forecast_cost_usd":  pred
            })

        direction = "increasing" if m > 0 else "decreasing"

        return {
            "forecast":                forecast,
            "trend_slope_per_month":   round(float(m), 2),
            "trend_direction":         direction,
            "message": (
                f"Cost forecast (trend is {direction} by ${abs(m):,.2f}/month): "
                + ", ".join(f"{f['period']}: ${f['forecast_cost_usd']:,.2f}" for f in forecast)
            )
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def detect_cost_anomalies(z_threshold: float = 2.0) -> dict:
    """
    Detect months with abnormally high or low cloud costs using Z-score analysis.
    Use when user asks: anomalies, unusual costs, billing spikes, unexpected charges.
    Z-threshold of 2.0 means flagging months more than 2 standard deviations from mean.
    """
    try:
        df      = _load_daily()
        monthly = df.groupby("Year_Month")["Daily_Cost_USD"].sum().reset_index()
        monthly.columns = ["Year_Month", "Total_Cost"]

        mean = monthly["Total_Cost"].mean()
        std  = monthly["Total_Cost"].std()
        monthly["z_score"] = ((monthly["Total_Cost"] - mean) / std).round(2)

        anomalies = monthly[monthly["z_score"].abs() > z_threshold].copy()
        anomalies["Total_Cost"] = anomalies["Total_Cost"].round(2)

        # Attach spike reasons to anomalous months
        results = []
        for _, row in anomalies.iterrows():
            spikes = (
                df[(df["Year_Month"] == row["Year_Month"]) &
                   (df["Spike_Reason"].notna()) &
                   (df["Spike_Reason"] != "")]
                ["Spike_Reason"].unique().tolist()
            )
            results.append({
                "period":        row["Year_Month"],
                "total_cost":    row["Total_Cost"],
                "z_score":       row["z_score"],
                "spike_reasons": spikes
            })

        return {
            "anomalies":          results,
            "threshold":          z_threshold,
            "mean_monthly_cost":  round(mean, 2),
            "std_monthly_cost":   round(std, 2),
            "message": (
                f"Found {len(results)} anomalous month(s) (|z| > {z_threshold}). "
                f"Mean monthly cost: ${mean:,.2f}"
                if results else
                f"No cost anomalies detected. Mean monthly cost: ${mean:,.2f}"
            )
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_cost_summary() -> dict:
    """
    Get a comprehensive cost summary combining current spend, trends, and forecasts.
    Answers questions about: total cost, cost breakdown, trends, and forecast all at once.
    Use when user asks: overall cost summary, give me all cost info, complete cost breakdown.
    """
    try:
        df = _load_daily()
        
        # Current month cost
        now = datetime.now()
        current_df = df[(df["Year"] == now.year) & (df["Month_Num"] == now.month)]
        if current_df.empty:
            latest_ym = df["Year_Month"].max()
            current_df = df[df["Year_Month"] == latest_ym]
            current_period = f"{latest_ym} (latest)"
        else:
            current_period = now.strftime("%Y-%m")
        
        current_cost = round(current_df["Daily_Cost_USD"].sum(), 2)
        
        # Year-to-date
        ytd_df = df[df["Year"] == now.year]
        ytd_cost = round(ytd_df["Daily_Cost_USD"].sum(), 2)
        
        # Top services
        top_services = (
            df.groupby("Service")["Daily_Cost_USD"]
            .sum()
            .nlargest(5)
            .round(2)
            .to_dict()
        )
        
        # Provider breakdown
        by_provider = (
            df.groupby("Cloud_Provider")["Daily_Cost_USD"]
            .sum()
            .round(2)
            .to_dict()
        )
        
        # Recent trend (last 3 months)
        monthly = (
            df.groupby("Year_Month")["Daily_Cost_USD"]
            .sum()
            .reset_index()
            .sort_values("Year_Month")
            .tail(3)
        )
        trend_data = monthly.to_dict(orient="records")
        
        return {
            "current_period": current_period,
            "current_cost_usd": current_cost,
            "ytd_cost_usd": ytd_cost,
            "top_services": top_services,
            "by_provider": by_provider,
            "recent_trend_months": trend_data,
            "summary": {
                "message": f"Current cost ({current_period}): ${current_cost:,.2f}",
                "ytd": f"YTD total: ${ytd_cost:,.2f}",
                "top_services": top_services,
            }
        }
    except Exception as e:
        return {"error": f"Cost summary failed: {str(e)}"}


# ─── DEBUG HELPER (run directly to diagnose data issues) ─────────────────────
if __name__ == "__main__":
    print("Loading sheet...")
    df = _load_daily()
    print(f"Rows loaded: {len(df)}")
    print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
    print(f"Daily_Cost_USD sample:\n{df['Daily_Cost_USD'].head(10)}")
    print(f"Total cost: ${df['Daily_Cost_USD'].sum():,.2f}")
    print(f"Non-zero rows: {(df['Daily_Cost_USD'] > 0).sum()}")