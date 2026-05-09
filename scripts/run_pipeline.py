import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.transformation.clean_data import clean_table_sheet
from src.storage.load_to_db import load_monthly_data_to_db
from src.utils.validation import validate_clean_data


RAW_FILE = Path("data/raw/Business growth & Volume Dashboard.xlsx")
PROCESSED_FILE = Path("data/processed/clean_nse_business_growth.csv")


def save_processed_csv(df: pd.DataFrame):
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        PROCESSED_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("Processed CSV saved successfully!")
    print(f"CSV path: {PROCESSED_FILE}")


def show_duplicate_rows(df: pd.DataFrame):
    duplicate_rows = df[
        df.duplicated(
            subset=[
                "segment",
                "instrument",
                "month_label",
                "financial_year",
                "financial_quarter"
            ],
            keep=False
        )
    ]

    if duplicate_rows.empty:
        print("No duplicate rows found.")
        return

    print("\nDuplicate rows found:")
    print(
        duplicate_rows[
            [
                "segment",
                "instrument",
                "year",
                "month_label",
                "month_date",
                "calendar_quarter",
                "financial_year",
                "financial_quarter",
                "turnover",
                "volume"
            ]
        ].to_string(index=False)
    )


def run_pipeline():
    if not RAW_FILE.exists():
        message = f"Excel file not found. Please place file here: {RAW_FILE}"
        print(message)
        return False, message

    print("Reading Excel file...")

    df_raw = pd.read_excel(
        RAW_FILE,
        sheet_name="Table"
    )

    df_raw.columns = df_raw.columns.str.strip()

    print("Excel file loaded successfully!")
    print(f"Raw rows: {len(df_raw)}")
    print(f"Raw columns: {len(df_raw.columns)}")

    print("\nCleaning and transforming data...")

    df_clean = clean_table_sheet(df_raw)

    print("Data cleaned successfully!")
    print(f"Clean rows: {len(df_clean)}")

    if df_clean.empty:
        message = "Clean data is empty. Please check Excel sheet and column names."
        print(message)
        return False, message

    show_duplicate_rows(df_clean)

    print("\nValidating clean data...")

    try:
        validate_clean_data(
            df_clean,
            expected_rows=240
        )
    except Exception as error:
        message = f"Validation failed: {error}"
        print(message)
        return False, message

    print("\nSaving processed CSV...")

    save_processed_csv(df_clean)

    print("\nLoading data into SQLite database...")

    load_monthly_data_to_db(df_clean)

    message = (
        f"Pipeline completed successfully. "
        f"Rows inserted: {len(df_clean)}"
    )

    print("\n" + message)

    return True, message


if __name__ == "__main__":
    run_pipeline()