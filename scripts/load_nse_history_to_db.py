import sys
import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "nse_business_growth.db"
CSV_PATH = PROJECT_ROOT / "data" / "processed" / "clean_nse_business_growth_from_nse.csv"

TABLE_NAME = "nse_business_growth"


def load_nse_history_to_db():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Processed NSE CSV not found: {CSV_PATH}")

    print(f"Reading processed NSE file: {CSV_PATH}")

    df = pd.read_csv(
        CSV_PATH,
        keep_default_na=False
    )

    print(f"Rows found: {len(df)}")
    print(f"Columns found: {list(df.columns)}")

    required_columns = [
        "segment",
        "instrument",
        "year",
        "month_label",
        "month_date",
        "calendar_quarter",
        "financial_year",
        "financial_quarter",
        "turnover",
        "volume",
        "mom_turnover_change",
        "mom_volume_change",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    df = df[required_columns].copy()

    df["instrument"] = (
        df["instrument"]
        .replace("", "NA")
        .fillna("NA")
        .astype(str)
        .str.strip()
    )

    df["segment"] = df["segment"].astype(str).str.strip()
    df["month_label"] = df["month_label"].astype(str).str.strip()

    df["month_date"] = pd.to_datetime(
        df["month_date"],
        errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    df["year"] = pd.to_numeric(
        df["year"],
        errors="coerce"
    ).astype("Int64")

    numeric_columns = [
        "turnover",
        "volume",
        "mom_turnover_change",
        "mom_volume_change",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    duplicate_count = df.duplicated(
        subset=[
            "segment",
            "instrument",
            "month_label",
        ]
    ).sum()

    print(f"Duplicate rows found: {duplicate_count}")

    if duplicate_count > 0:
        df = df.drop_duplicates(
            subset=[
                "segment",
                "instrument",
                "month_label",
            ],
            keep="last"
        )

        print(f"Rows after duplicate removal: {len(df)}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    print(f"Loading data into SQLite database: {DB_PATH}")

    df.to_sql(
        TABLE_NAME,
        conn,
        if_exists="replace",
        index=False
    )

    conn.commit()

    inserted_rows = pd.read_sql_query(
        f"SELECT COUNT(*) AS total_rows FROM {TABLE_NAME}",
        conn
    )

    segment_summary = pd.read_sql_query(
        f"""
        SELECT segment, instrument, COUNT(*) AS rows
        FROM {TABLE_NAME}
        GROUP BY segment, instrument
        ORDER BY segment, instrument
        """,
        conn
    )

    date_summary = pd.read_sql_query(
        f"""
        SELECT segment, instrument,
               MIN(month_date) AS start_month,
               MAX(month_date) AS end_month
        FROM {TABLE_NAME}
        GROUP BY segment, instrument
        ORDER BY segment, instrument
        """,
        conn
    )

    conn.close()

    print("\nData loaded successfully.")
    print(f"Rows inserted: {inserted_rows.loc[0, 'total_rows']}")
    print(f"Database path: {DB_PATH}")

    print("\nRows by segment/instrument:")
    print(segment_summary)

    print("\nDate range by segment/instrument:")
    print(date_summary)


if __name__ == "__main__":
    load_nse_history_to_db()