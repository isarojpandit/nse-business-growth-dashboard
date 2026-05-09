import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("data/nse_business_growth.db")


def view_database():
    if not DB_PATH.exists():
        print("Database file not found.")
        print(f"Expected path: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)

    print("\nTotal rows:")
    total_rows = pd.read_sql_query(
        "SELECT COUNT(*) AS total_rows FROM nse_business_growth",
        conn
    )
    print(total_rows)

    print("\nRows by segment and instrument:")
    segment_count = pd.read_sql_query(
        """
        SELECT segment, instrument, COUNT(*) AS row_count
        FROM nse_business_growth
        GROUP BY segment, instrument
        ORDER BY segment, instrument
        """,
        conn
    )
    print(segment_count)

    print("\nFinancial years:")
    fy = pd.read_sql_query(
        """
        SELECT financial_year, COUNT(*) AS row_count
        FROM nse_business_growth
        GROUP BY financial_year
        ORDER BY financial_year
        """,
        conn
    )
    print(fy)

    print("\nFinancial quarter check:")
    fq = pd.read_sql_query(
        """
        SELECT financial_year, financial_quarter, COUNT(*) AS row_count
        FROM nse_business_growth
        GROUP BY financial_year, financial_quarter
        ORDER BY financial_year, financial_quarter
        """,
        conn
    )
    print(fq)

    print("\nFirst 20 rows:")
    preview = pd.read_sql_query(
        """
        SELECT 
            segment,
            instrument,
            month_label,
            calendar_quarter,
            financial_year,
            financial_quarter,
            turnover,
            volume
        FROM nse_business_growth
        LIMIT 20
        """,
        conn
    )
    print(preview)

    conn.close()


if __name__ == "__main__":
    view_database()