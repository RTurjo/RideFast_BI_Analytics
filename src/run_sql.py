"""Load the raw CSVs into an in-memory SQLite DB and run every query in sql/kpi_queries.sql.

    python src/run_sql.py
"""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ["rides", "drivers", "users", "support_tickets"]


def main() -> None:
    con = sqlite3.connect(":memory:")
    for name in TABLES:
        df = pd.read_csv(ROOT / "data" / "raw" / f"{name}.csv")
        for col in df.select_dtypes("bool"):
            df[col] = df[col].map({True: "True", False: "False"})
        df.to_sql(name, con, index=False)

    sql = (ROOT / "sql" / "kpi_queries.sql").read_text()
    blocks = [b.strip() for b in sql.split(";") if "SELECT" in b]
    for block in blocks:
        title = next((l for l in block.splitlines() if l.startswith("-- Q")), "Query")
        print(f"\n{title}\n" + "-" * len(title))
        print(pd.read_sql(block, con).to_string(index=False))


if __name__ == "__main__":
    main()
