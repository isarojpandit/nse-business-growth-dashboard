import sqlite3
import pandas as pd
from pathlib import Path


DB_PATH = Path("data/nse_business_growth.db")


def load_monthly_data_to_db(df: pd.DataFrame):
    """
    Load cleaned monthly data into SQLite database.
    Existing data will be replaced for now.
    """

    if df.empty:
        print("No data found to load into database.")
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    df.to_sql(
        "nse_business_growth",
        conn,
        if_exists="replace",
        index=False
    )

    conn.close()

    print("Data loaded into SQLite database successfully!")
    print(f"Rows inserted: {len(df)}")
    print(f"Database path: {DB_PATH}")