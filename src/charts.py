"""Static charts for the README / report (PNG, 2x resolution)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"

# Palette (validated reference palette, light mode)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#8a8983"
GRID = "#e6e5e0"
BLUE = "#2a78d6"      # primary series
ORANGE = "#eb6834"    # highlighted entity (the problem)
CONTEXT = "#c9c8c1"   # everything else

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": GRID,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,
    }
)


def _title(ax, title: str, subtitle: str) -> None:
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=INK, pad=26)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9.5, color=INK_2, va="bottom")


def _save(fig, name: str) -> None:
    IMAGES.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(IMAGES / name, dpi=200)
    plt.close(fig)


def city_completion(city: pd.DataFrame) -> None:
    df = city.sort_values("completion_rate")
    colors = [ORANGE if c == "Northgate" else CONTEXT for c in df["city"]]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(df["city"], df["completion_rate"] * 100, color=colors, height=0.62)
    ax.set_xlim(70, 84)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Completion rate (%)")
    for y, (c, v) in enumerate(zip(df["city"], df["completion_rate"])):
        if c in ("Northgate", df["city"].iloc[-1]):
            ax.text(v * 100 + 0.2, y, f"{v:.1%}", va="center", fontsize=9, color=INK)
    _title(ax, "Northgate is the only city that breaks the pattern",
           "Ride completion rate by city, Jul 2023 - Jun 2024 (120k requests)")
    _save(fig, "01_city_completion.png")


def zone_wait(zone: pd.DataFrame) -> None:
    df = zone.sort_values("avg_wait_min", ascending=False).head(10).iloc[::-1]
    colors = [ORANGE if z.startswith("NOR") else CONTEXT for z in df["pickup_zone"]]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(df["pickup_zone"], df["avg_wait_min"], color=colors, height=0.62)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Average wait time (minutes)")
    for y, (z, w, c) in enumerate(zip(df["pickup_zone"], df["avg_wait_min"], df["completion_rate"])):
        if z in ("NOR-Z04", "NOR-Z05"):
            ax.text(w + 0.3, y, f"{w:.1f} min  |  {c:.1%} completed", va="center", fontsize=9)
    _title(ax, "Two Northgate zones drive the whole city's problem",
           "Top 10 pickup zones by average wait time")
    _save(fig, "02_zone_wait_time.png")


def wait_vs_completion(wait_bucket: pd.DataFrame) -> None:
    df = wait_bucket
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.bar(df["wait_bucket"].astype(str), df["completion_rate"] * 100, color=BLUE, width=0.6)
    ax.set_ylim(0, 100)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Completion rate (%)")
    for x, v in enumerate(df["completion_rate"]):
        ax.text(x, v * 100 + 1.5, f"{v:.0%}", ha="center", fontsize=9)
    _title(ax, "Longer waits, fewer completed rides",
           "Completion rate by time from request to driver arrival")
    _save(fig, "03_wait_vs_completion.png")


def status_leakage(status: pd.DataFrame) -> None:
    df = status.copy()
    labels = {"completed": "Completed", "cancelled_driver": "Cancelled by driver",
              "cancelled_user": "Cancelled by user", "no_show": "No-show"}
    df["label"] = df["status"].map(labels)
    df = df.iloc[::-1]
    colors = [BLUE if s == "completed" else (ORANGE if s == "cancelled_driver" else CONTEXT)
              for s in df["status"]]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.barh(df["label"], df["requests"], color=colors, height=0.6)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Ride requests")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
    for y, (n, s, w) in enumerate(zip(df["requests"], df["share"], df["avg_wait_min"])):
        ax.text(n + 1200, y, f"{n:,}  ({s:.1%})  |  avg wait {w:.1f} min", va="center", fontsize=9)
    ax.set_xlim(0, df["requests"].max() * 1.55)
    _title(ax, "22,362 requests never became a ride",
           "Ride outcome funnel - driver cancellation is the biggest leak")
    _save(fig, "04_status_leakage.png")


def promo_effect(promo: pd.DataFrame) -> None:
    df = promo.copy()
    df["label"] = df["promo_code_used"].map({True: "Promo", False: "No promo"})
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.8))
    panels = [("completion_rate", "Completion rate", lambda v: f"{v:.1%}", 100),
              ("avg_completed_fare", "Avg completed fare (USD)", lambda v: f"${v:.2f}", 1)]
    for ax, (col, name, fmt, mult) in zip(axes, panels):
        ax.bar(df["label"], df[col] * mult, color=[CONTEXT, BLUE], width=0.55)
        ax.grid(axis="x", visible=False)
        ax.set_title(name, fontsize=10, color=INK_2, loc="left")
        for x, v in enumerate(df[col]):
            ax.text(x, v * mult * 1.02, fmt(v), ha="center", fontsize=9)
        ax.set_ylim(0, df[col].max() * mult * 1.2)
    fig.suptitle("Promos lower the fare but don't lift completion", x=0.02, ha="left",
                 fontsize=13, fontweight="bold")
    _save(fig, "05_promo_effect.png")


def user_segments(users: pd.DataFrame) -> None:
    df = users.set_index("segment").loc[["Active", "Churned"]]
    fig, axes = plt.subplots(1, 3, figsize=(9, 3.6))
    panels = [("users", "Users", "{:,.0f}"), ("avg_promo_rides", "Avg promo rides", "{:.1f}"),
              ("avg_wallet_balance", "Avg wallet balance (USD)", "${:.2f}")]
    for ax, (col, name, fmt) in zip(axes, panels):
        ax.bar(df.index, df[col], color=[BLUE, ORANGE], width=0.55)
        ax.grid(axis="x", visible=False)
        ax.set_title(name, fontsize=10, color=INK_2, loc="left")
        ax.set_ylim(0, df[col].max() * 1.2)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        for x, v in enumerate(df[col]):
            ax.text(x, v * 1.02, fmt.format(v), ha="center", fontsize=9)
    fig.suptitle("79.6% of registered users have churned", x=0.02, ha="left",
                 fontsize=13, fontweight="bold")
    _save(fig, "06_user_churn.png")


def ticket_categories(tickets: pd.DataFrame) -> None:
    df = tickets.sort_values("tickets")
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(df["category_label"], df["tickets"], color=BLUE, height=0.6)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, df["tickets"].max() * 1.75)
    ax.set_xlabel("Support tickets")
    for y, (n, u, h) in enumerate(zip(df["tickets"], df["unresolved_rate"], df["avg_resolution_hrs"])):
        ax.text(n + 80, y, f"{n:,}  |  {u:.0%} unresolved  |  {h:.1f} h to resolve",
                va="center", fontsize=9)
    _title(ax, "App issues and driver behaviour lead 22k support tickets",
           "Tickets by category, unresolved share and average resolution time")
    _save(fig, "07_support_tickets.png")


def make_all_charts(tables: dict[str, pd.DataFrame]) -> None:
    city_completion(tables["kpi_city"])
    zone_wait(tables["kpi_zone"])
    wait_vs_completion(tables["kpi_wait_bucket"])
    status_leakage(tables["kpi_status_funnel"])
    promo_effect(tables["kpi_promo"])
    user_segments(tables["kpi_user_segments"])
    ticket_categories(tables["kpi_ticket_category"])
