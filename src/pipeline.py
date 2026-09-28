"""
RideFast BI Analysis - end-to-end data pipeline.

Steps
-----
1. Load the four raw CSVs (rides, drivers, users, support_tickets)
2. Validate & clean (types, keys, nulls, logical checks)
3. Engineer analysis features (wait time, trip duration, hour, wait bucket ...)
4. Build KPI / aggregate tables used by the Looker Studio dashboard
5. Export processed tables to data/processed/ and charts to images/

Run from the repository root:
    python src/pipeline.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

STATUS_ORDER = ["completed", "cancelled_driver", "cancelled_user", "no_show"]
WAIT_BINS = [0, 5, 10, 15, 20, np.inf]
WAIT_LABELS = ["0-5 min", "5-10 min", "10-15 min", "15-20 min", "20+ min"]


# --------------------------------------------------------------------------- #
# 1. Load
# --------------------------------------------------------------------------- #
def load_raw() -> dict[str, pd.DataFrame]:
    rides = pd.read_csv(
        RAW / "rides.csv",
        parse_dates=["request_time", "pickup_time", "dropoff_time"],
    )
    drivers = pd.read_csv(RAW / "drivers.csv", parse_dates=["signup_date"])
    users = pd.read_csv(RAW / "users.csv", parse_dates=["signup_date", "last_ride_date"])
    tickets = pd.read_csv(RAW / "support_tickets.csv", parse_dates=["created_at"])
    return {"rides": rides, "drivers": drivers, "users": users, "tickets": tickets}


# --------------------------------------------------------------------------- #
# 2. Validate
# --------------------------------------------------------------------------- #
def validate(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return a data-quality report (one row per check)."""
    r, d, u, t = dfs["rides"], dfs["drivers"], dfs["users"], dfs["tickets"]
    completed = r["status"].eq("completed")
    checks = {
        "rides: duplicate ride_id": r["ride_id"].duplicated().sum(),
        "drivers: duplicate driver_id": d["driver_id"].duplicated().sum(),
        "users: duplicate user_id": u["user_id"].duplicated().sum(),
        "tickets: duplicate ticket_id": t["ticket_id"].duplicated().sum(),
        "rides: user_id not in users": (~r["user_id"].isin(u["user_id"])).sum(),
        "rides: driver_id not in drivers": (~r["driver_id"].isin(d["driver_id"])).sum(),
        "rides: unknown status": (~r["status"].isin(STATUS_ORDER)).sum(),
        "rides: pickup before request": (r["pickup_time"] < r["request_time"]).sum(),
        "rides: completed with no dropoff": (completed & r["dropoff_time"].isna()).sum(),
        "rides: non-completed with fare > 0": (~completed & r["fare_amount"].gt(0)).sum(),
        "rides: negative fare": r["fare_amount"].lt(0).sum(),
        "rides: rating outside 1-5": (~r["rating_by_user"].dropna().between(1, 5)).sum(),
        "tickets: resolved but no resolution time": (
            t["resolved"] & t["resolution_time_hours"].isna()
        ).sum(),
    }
    report = pd.DataFrame({"check": checks.keys(), "failing_rows": checks.values()})
    report["passed"] = report["failing_rows"].eq(0)
    return report


# --------------------------------------------------------------------------- #
# 3. Feature engineering
# --------------------------------------------------------------------------- #
def engineer(dfs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    r = dfs["rides"].copy()
    r["wait_min"] = (r["pickup_time"] - r["request_time"]).dt.total_seconds() / 60
    r["trip_min"] = (r["dropoff_time"] - r["pickup_time"]).dt.total_seconds() / 60
    r["is_completed"] = r["status"].eq("completed").astype(int)
    r["is_driver_cancel"] = r["status"].eq("cancelled_driver").astype(int)
    r["request_date"] = r["request_time"].dt.date
    r["request_month"] = r["request_time"].dt.to_period("M").astype(str)
    r["request_hour"] = r["request_time"].dt.hour
    r["request_weekday"] = r["request_time"].dt.day_name()
    r["wait_bucket"] = pd.cut(r["wait_min"], WAIT_BINS, labels=WAIT_LABELS, right=False)
    r["gross_fare"] = r["fare_amount"] + r["promo_discount"].where(r["is_completed"] == 1, 0)
    r["is_northgate"] = r["city"].eq("Northgate")

    t = dfs["tickets"].copy()
    t["category_label"] = t["category"].str.replace("_", " ").str.title()
    t["ticket_month"] = t["created_at"].dt.to_period("M").astype(str)

    u = dfs["users"].copy()
    u["segment"] = np.where(u["churn_flag"], "Churned", "Active")
    u["promo_share"] = (u["promo_rides"] / u["total_rides"].replace(0, np.nan)).round(3)

    return {**dfs, "rides": r, "tickets": t, "users": u}


# --------------------------------------------------------------------------- #
# 4. KPI / aggregate tables
# --------------------------------------------------------------------------- #
def _ride_kpis(g: pd.core.groupby.DataFrameGroupBy) -> pd.DataFrame:
    out = g.agg(
        requests=("ride_id", "size"),
        completed=("is_completed", "sum"),
        completion_rate=("is_completed", "mean"),
        driver_cancel_rate=("is_driver_cancel", "mean"),
        avg_wait_min=("wait_min", "mean"),
        avg_user_rating=("rating_by_user", "mean"),
        promo_rate=("promo_code_used", "mean"),
        revenue=("fare_amount", "sum"),
    )
    return out.round(4)


def build_tables(dfs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    r, u, t, d = dfs["rides"], dfs["users"], dfs["tickets"], dfs["drivers"]
    comp = r[r["is_completed"] == 1]

    headline = pd.Series(
        {
            "ride_requests": len(r),
            "completed_rides": int(r["is_completed"].sum()),
            "completion_rate": r["is_completed"].mean(),
            "driver_cancel_rate": r["is_driver_cancel"].mean(),
            "avg_wait_min": r["wait_min"].mean(),
            "median_wait_min": r["wait_min"].median(),
            "completed_revenue": comp["fare_amount"].sum(),
            "avg_completed_fare": comp["fare_amount"].mean(),
            "promo_usage_rate": r["promo_code_used"].mean(),
            "total_promo_discount": r["promo_discount"].sum(),
            "registered_users": len(u),
            "user_churn_rate": u["churn_flag"].mean(),
            "drivers": len(d),
            "active_driver_share": d["status"].eq("active").mean(),
            "support_tickets": len(t),
            "ticket_unresolved_rate": 1 - t["resolved"].mean(),
        }
    ).round(4).rename("value").rename_axis("metric").reset_index()

    status = (
        r.groupby("status")
        .agg(requests=("ride_id", "size"), avg_wait_min=("wait_min", "mean"))
        .reindex(STATUS_ORDER)
        .assign(share=lambda x: x["requests"] / x["requests"].sum())
        .round(4)
        .reset_index()
    )

    city = _ride_kpis(r.groupby("city")).sort_values("completion_rate").reset_index()
    zone = (
        _ride_kpis(r.groupby(["city", "pickup_zone"]))
        .sort_values("completion_rate")
        .reset_index()
    )
    northgate_vs_rest = (
        _ride_kpis(r.groupby(r["is_northgate"].map({True: "Northgate", False: "Other 11 cities"})))
        .rename_axis("group")
        .reset_index()
    )
    monthly = _ride_kpis(r.groupby("request_month")).reset_index()
    hourly = _ride_kpis(r.groupby("request_hour")).reset_index()
    wait_bucket = _ride_kpis(r.groupby("wait_bucket", observed=True)).reset_index()
    vehicle = _ride_kpis(r.groupby("vehicle_type")).reset_index()

    promo = (
        r.groupby("promo_code_used")
        .agg(
            requests=("ride_id", "size"),
            completion_rate=("is_completed", "mean"),
            avg_discount=("promo_discount", "mean"),
        )
        .join(comp.groupby("promo_code_used")["fare_amount"].mean().rename("avg_completed_fare"))
        .round(4)
        .reset_index()
    )

    users_seg = (
        u.groupby("segment")
        .agg(
            users=("user_id", "size"),
            avg_lifetime_rides=("total_rides", "mean"),
            avg_promo_rides=("promo_rides", "mean"),
            avg_wallet_balance=("wallet_balance", "mean"),
        )
        .round(2)
        .reset_index()
    )

    tickets_cat = (
        t.groupby("category_label")
        .agg(
            tickets=("ticket_id", "size"),
            unresolved_rate=("resolved", lambda s: 1 - s.mean()),
            avg_resolution_hrs=("resolution_time_hours", "mean"),
        )
        .sort_values("tickets", ascending=False)
        .round(4)
        .reset_index()
    )

    drivers_city = (
        d.groupby("city")
        .agg(
            drivers=("driver_id", "size"),
            active_share=("status", lambda s: s.eq("active").mean()),
            avg_acceptance=("acceptance_rate", "mean"),
            avg_cancellation=("cancellation_rate", "mean"),
            avg_online_hrs=("online_hours_monthly", "mean"),
            avg_rating=("avg_rating", "mean"),
        )
        .round(4)
        .reset_index()
    )

    return {
        "kpi_headline": headline,
        "kpi_status_funnel": status,
        "kpi_city": city,
        "kpi_zone": zone,
        "kpi_northgate_vs_rest": northgate_vs_rest,
        "kpi_monthly": monthly,
        "kpi_hourly": hourly,
        "kpi_wait_bucket": wait_bucket,
        "kpi_vehicle": vehicle,
        "kpi_promo": promo,
        "kpi_user_segments": users_seg,
        "kpi_ticket_category": tickets_cat,
        "kpi_driver_city": drivers_city,
    }


# --------------------------------------------------------------------------- #
# 5. Export
# --------------------------------------------------------------------------- #
def export(dfs: dict[str, pd.DataFrame], tables: dict[str, pd.DataFrame]) -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    # Cleaned, enriched fact table - the Looker Studio data source
    dfs["rides"].to_csv(PROCESSED / "rides_enriched.csv", index=False)
    for name, df in tables.items():
        df.to_csv(PROCESSED / f"{name}.csv", index=False)


def main() -> None:
    dfs = load_raw()
    report = validate(dfs)
    print("Data-quality checks\n", report.to_string(index=False), "\n")
    dfs = engineer(dfs)
    tables = build_tables(dfs)
    export(dfs, tables)
    print(tables["kpi_headline"].to_string(index=False))

    from charts import make_all_charts  # local module

    make_all_charts(tables)
    print(f"\nProcessed tables -> {PROCESSED.relative_to(ROOT)}/  |  charts -> images/")


if __name__ == "__main__":
    main()
