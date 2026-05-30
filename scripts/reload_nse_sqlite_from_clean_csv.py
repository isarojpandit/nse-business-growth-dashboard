from pathlib import Path
import sqlite3
import pandas as pd


CSV_FILE = Path("data/processed/clean_nse_business_growth_from_nse.csv")
DB_FILE = Path("data/nse_business_growth.db")
TABLE_NAME = "nse_business_growth"


def main():
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"CSV file not found: {CSV_FILE}")

    df = pd.read_csv(CSV_FILE, keep_default_na=False)

    df["segment"] = df["segment"].astype(str).str.strip()
    df["instrument"] = df["instrument"].replace("", "NA").astype(str).str.strip()
    df["month_label"] = df["month_label"].astype(str).str.strip()

    df["month_date"] = pd.to_datetime(df["month_date"], errors="coerce")
    df = df.dropna(subset=["month_date"]).copy()
    df["month_date"] = df["month_date"].dt.strftime("%Y-%m-%d")

    numeric_columns = [
        "year",
        "monthly_turnover",
        "monthly_volume",
        "active_trading_days",
        "turnover",
        "volume",
        "mom_turnover_change",
        "mom_volume_change",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.drop_duplicates(
        subset=["segment", "instrument", "month_label"],
        keep="last",
    )

    df = df.sort_values(["segment", "instrument", "month_date"])

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)

    df.to_sql(
        TABLE_NAME,
        conn,
        if_exists="replace",
        index=False,
    )

    check_df = pd.read_sql_query(
        f"""
        SELECT
            segment,
            instrument,
            COUNT(*) AS rows,
            MIN(month_date) AS start_month,
            MAX(month_date) AS end_month
        FROM {TABLE_NAME}
        GROUP BY segment, instrument
        ORDER BY segment, instrument
        """,
        conn,
    )

    total_rows = pd.read_sql_query(
        f"SELECT COUNT(*) AS total_rows FROM {TABLE_NAME}",
        conn,
    )

    conn.close()

    print(f"SQLite DB reloaded successfully: {DB_FILE}")
    print(f"Table: {TABLE_NAME}")
    print()
    print(total_rows.to_string(index=False))
    print()
    print(check_df.to_string(index=False))


if __name__ == "__main__":
    main()