import sqlite3
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from scripts import scrape_nse_business_growth_daily as scraper


PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
EXPORT_DIR = PROJECT_ROOT / "data" / "exports"
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"
DB_PATH = PROJECT_ROOT / "data" / "nse_business_growth.db"

MAIN_DATASET_PATH = PROCESSED_DIR / "clean_nse_business_growth_from_nse.csv"
RAW_EVIDENCE_PATH = EXPORT_DIR / "final_raw_nse_daily_trading_days.csv"

TEMP_MAIN_PATH = EXPORT_DIR / "incremental_candidate_main.csv"
TEMP_RAW_PATH = EXPORT_DIR / "incremental_candidate_raw.csv"

DB_TABLE_NAME = "nse_business_growth"

EXPECTED_GROUPS = {
    ("Capital Market", "NA"),
    ("Currency Derivatives", "Futures"),
    ("Currency Derivatives", "Options"),
    ("Equity Derivatives", "Futures"),
    ("Equity Derivatives", "Options"),
    ("Interest Rate Derivatives", "NA"),
}

MAIN_COLUMNS = [
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

RAW_REQUIRED_COLUMNS = [
    "segment",
    "instrument",
    "month_label",
]


class IncrementalUpdateError(RuntimeError):
    pass


def ensure_directories():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def read_csv_safely(path):
    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path, keep_default_na=False)


def normalize_instrument(value):
    if pd.isna(value):
        return "NA"

    text = str(value).strip()

    if text == "" or text.lower() == "nan":
        return "NA"

    return text


def normalize_main_df(df):
    if df.empty:
        return pd.DataFrame(columns=MAIN_COLUMNS)

    df = df.copy()

    for column in MAIN_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA

    df = df[MAIN_COLUMNS].copy()

    df["segment"] = df["segment"].astype(str).str.strip()
    df["instrument"] = df["instrument"].apply(normalize_instrument)
    df["month_label"] = df["month_label"].astype(str).str.strip()

    df["month_date"] = pd.to_datetime(df["month_date"], errors="coerce")
    df = df.dropna(subset=["month_date"])

    df["month_label"] = df["month_date"].dt.strftime("%b-%Y")
    df["year"] = df["month_date"].dt.year.astype("Int64")

    numeric_columns = [
        "turnover",
        "volume",
        "mom_turnover_change",
        "mom_volume_change",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.drop_duplicates(
        subset=["segment", "instrument", "month_label"],
        keep="last",
    )

    df = df.sort_values(["segment", "instrument", "month_date"])
    df = recompute_mom_changes(df)

    return df


def normalize_raw_df(df):
    if df.empty:
        return pd.DataFrame()

    df = df.copy()

    for column in RAW_REQUIRED_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA

    df["segment"] = df["segment"].astype(str).str.strip()
    df["instrument"] = df["instrument"].apply(normalize_instrument)
    df["month_label"] = df["month_label"].astype(str).str.strip()

    if "month_date" in df.columns:
        df["month_date"] = pd.to_datetime(df["month_date"], errors="coerce")

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    return df


def recompute_mom_changes(df):
    if df.empty:
        return df

    df = df.copy()
    df = df.sort_values(["segment", "instrument", "month_date"])

    df["mom_turnover_change"] = (
        df.groupby(["segment", "instrument"])["turnover"].pct_change()
    )

    df["mom_volume_change"] = (
        df.groupby(["segment", "instrument"])["volume"].pct_change()
    )

    return df


def create_backup_if_needed(main_df, raw_df):
    import os

    if os.getenv("GITHUB_ACTIONS", "false").lower() == "true":
        print("Running in GitHub Actions. Skipping backup file creation.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if not main_df.empty:
        backup_main = BACKUP_DIR / f"backup_clean_nse_business_growth_from_nse_{timestamp}.csv"
        main_df.to_csv(backup_main, index=False)
        print(f"Main backup saved: {backup_main}")

    if not raw_df.empty:
        backup_raw = BACKUP_DIR / f"backup_final_raw_nse_daily_trading_days_{timestamp}.csv"
        raw_df.to_csv(backup_raw, index=False)
        print(f"Raw backup saved : {backup_raw}")


def get_latest_complete_month(main_df):
    if main_df.empty:
        return None

    summary = (
        main_df.groupby("month_date")[["segment", "instrument"]]
        .apply(lambda x: set(zip(x["segment"], x["instrument"])))
        .reset_index(name="groups")
    )

    complete_months = summary[
        summary["groups"].apply(lambda groups: EXPECTED_GROUPS.issubset(groups))
    ].copy()

    if complete_months.empty:
        return None

    return complete_months["month_date"].max()


def get_current_month_start():
    now = datetime.now()
    return pd.Timestamp(year=now.year, month=now.month, day=1)


def get_candidate_financial_years(latest_complete_month):
    current_year = datetime.now().year

    if latest_complete_month is None or pd.isna(latest_complete_month):
        base_year = current_year
    else:
        latest_complete_month = pd.to_datetime(latest_complete_month)

        if latest_complete_month.month >= 4:
            base_year = latest_complete_month.year
        else:
            base_year = latest_complete_month.year - 1

    candidate_start_years = sorted(
        {
            base_year,
            base_year + 1,
            current_year - 1,
            current_year,
            current_year + 1,
        }
    )

    candidate_start_years = [
        year
        for year in candidate_start_years
        if 1999 <= year <= current_year + 1
    ]

    return [f"{year}-{year + 1}" for year in candidate_start_years]


def prepare_temp_scrape_files(main_df, raw_df):
    main_df.to_csv(TEMP_MAIN_PATH, index=False)

    if raw_df.empty:
        raw_df.to_csv(TEMP_RAW_PATH, index=False)
    else:
        raw_df.to_csv(TEMP_RAW_PATH, index=False)

    latest_complete_month = get_latest_complete_month(main_df)
    current_month_start = get_current_month_start()

    scraper.MAIN_OUTPUT_FILE = TEMP_MAIN_PATH
    scraper.RAW_OUTPUT_FILE = TEMP_RAW_PATH
    scraper.MAX_YEARS_PER_SEGMENT = 3
    scraper.SCRAPE_ONLY_AFTER_MONTH_DATE = latest_complete_month
    scraper.SCRAPE_ONLY_BEFORE_MONTH_DATE = current_month_start

    if latest_complete_month is not None:
        print(
            "Scraper lower cutoff enabled. Only scraping months after: "
            f"{latest_complete_month.strftime('%b-%Y')}"
        )

    print(
        "Scraper upper cutoff enabled. Skipping running/current month and later: "
        f"{current_month_start.strftime('%b-%Y')}"
    )


def run_candidate_scrape(main_df, raw_df):
    prepare_temp_scrape_files(main_df, raw_df)

    print("Running NSE candidate scrape using optimized recent-year mode...")
    scraped_main_df, scraped_raw_df = scraper.scrape_all_segments()

    if scraped_main_df is None and scraped_raw_df is None:
        raise IncrementalUpdateError(
            "NSE scraping failed before candidate rows could be produced. "
            "Failing workflow intentionally instead of silently reloading old data."
        )

    if scraped_main_df is None:
        scraped_main_df = read_csv_safely(TEMP_MAIN_PATH)

    if scraped_raw_df is None:
        scraped_raw_df = read_csv_safely(TEMP_RAW_PATH)

    scraped_main_df = normalize_main_df(scraped_main_df)
    scraped_raw_df = normalize_raw_df(scraped_raw_df)

    return scraped_main_df, scraped_raw_df


def get_new_candidate_main_rows(scraped_main_df, latest_complete_month):
    if scraped_main_df.empty:
        return pd.DataFrame(columns=MAIN_COLUMNS)

    candidate_df = scraped_main_df.copy()

    if latest_complete_month is not None and not pd.isna(latest_complete_month):
        candidate_df = candidate_df[
            candidate_df["month_date"] > pd.to_datetime(latest_complete_month)
        ].copy()

    current_month_start = get_current_month_start()

    candidate_df = candidate_df[
        candidate_df["month_date"] < current_month_start
    ].copy()

    candidate_df = candidate_df.sort_values(["month_date", "segment", "instrument"])

    return candidate_df


def get_complete_new_months(candidate_main_df):
    if candidate_main_df.empty:
        return []

    months = []

    for month_date, group_df in candidate_main_df.groupby("month_date"):
        available_groups = set(zip(group_df["segment"], group_df["instrument"]))

        if EXPECTED_GROUPS.issubset(available_groups):
            months.append(pd.to_datetime(month_date))
        else:
            missing_groups = EXPECTED_GROUPS - available_groups
            month_text = pd.to_datetime(month_date).strftime("%b-%Y")
            print(f"Incomplete month skipped: {month_text}")
            print(f"Missing groups: {sorted(missing_groups)}")

    return sorted(months)


def filter_main_to_complete_months(candidate_main_df, complete_months):
    if candidate_main_df.empty or not complete_months:
        return pd.DataFrame(columns=MAIN_COLUMNS)

    complete_month_set = set(pd.to_datetime(complete_months))

    complete_df = candidate_main_df[
        candidate_main_df["month_date"].isin(complete_month_set)
    ].copy()

    complete_df = complete_df[
        complete_df.apply(
            lambda row: (row["segment"], row["instrument"]) in EXPECTED_GROUPS,
            axis=1,
        )
    ].copy()

    complete_df = complete_df.drop_duplicates(
        subset=["segment", "instrument", "month_label"],
        keep="last",
    )

    return complete_df[MAIN_COLUMNS].copy()


def filter_raw_to_complete_main_rows(scraped_raw_df, complete_main_df):
    if scraped_raw_df.empty or complete_main_df.empty:
        return pd.DataFrame(columns=scraped_raw_df.columns)

    allowed_keys = set(
        zip(
            complete_main_df["segment"].astype(str),
            complete_main_df["instrument"].astype(str),
            complete_main_df["month_label"].astype(str),
        )
    )

    raw_df = scraped_raw_df.copy()

    raw_df = raw_df[
        raw_df.apply(
            lambda row: (
                str(row["segment"]),
                str(row["instrument"]),
                str(row["month_label"]),
            ) in allowed_keys,
            axis=1,
        )
    ].copy()

    return raw_df


def merge_main_data(current_main_df, complete_new_main_df):
    if complete_new_main_df.empty:
        return current_main_df.copy()

    merged_df = pd.concat(
        [current_main_df, complete_new_main_df],
        ignore_index=True,
    )

    merged_df = normalize_main_df(merged_df)

    return merged_df


def merge_raw_data(current_raw_df, new_raw_df):
    if new_raw_df.empty:
        return current_raw_df.copy()

    merged_df = pd.concat(
        [current_raw_df, new_raw_df],
        ignore_index=True,
    )

    merged_df = normalize_raw_df(merged_df)

    subset_columns = [
        column for column in ["segment", "instrument", "month_label", "date"]
        if column in merged_df.columns
    ]

    if subset_columns:
        merged_df = merged_df.drop_duplicates(subset=subset_columns, keep="last")

    return merged_df


def clean_raw_against_main(raw_df, main_df):
    if raw_df.empty or main_df.empty:
        return raw_df.copy()

    allowed_keys = set(
        zip(
            main_df["segment"].astype(str),
            main_df["instrument"].astype(str),
            main_df["month_label"].astype(str),
        )
    )

    cleaned_raw_df = raw_df[
        raw_df.apply(
            lambda row: (
                str(row["segment"]),
                str(row["instrument"]),
                str(row["month_label"]),
            ) in allowed_keys,
            axis=1,
        )
    ].copy()

    return cleaned_raw_df


def save_outputs(main_df, raw_df):
    main_df = main_df.copy()
    raw_df = raw_df.copy()

    main_for_csv = main_df.copy()
    main_for_csv["month_date"] = (
        pd.to_datetime(main_for_csv["month_date"]).dt.strftime("%Y-%m-%d")
    )

    main_for_csv.to_csv(MAIN_DATASET_PATH, index=False)

    if not raw_df.empty:
        raw_for_csv = raw_df.copy()

        if "month_date" in raw_for_csv.columns:
            raw_for_csv["month_date"] = (
                pd.to_datetime(raw_for_csv["month_date"], errors="coerce")
                .dt.strftime("%Y-%m-%d")
            )

        if "date" in raw_for_csv.columns:
            raw_for_csv["date"] = (
                pd.to_datetime(raw_for_csv["date"], errors="coerce")
                .dt.strftime("%Y-%m-%d")
            )

        raw_for_csv.to_csv(RAW_EVIDENCE_PATH, index=False)
    else:
        raw_df.to_csv(RAW_EVIDENCE_PATH, index=False)


def reload_sqlite(main_df):
    db_df = main_df.copy()
    db_df["month_date"] = pd.to_datetime(db_df["month_date"]).dt.strftime("%Y-%m-%d")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        db_df.to_sql(DB_TABLE_NAME, conn, if_exists="replace", index=False)

    print("SQLite reloaded successfully.")

    summary = (
        main_df.groupby(["segment", "instrument"])
        .agg(
            rows=("month_label", "count"),
            start_month=("month_date", "min"),
            end_month=("month_date", "max"),
        )
        .reset_index()
    )

    print(summary.to_string(index=False))


def print_group_summary(label, df):
    print(f"\n{label} group summary:")

    if df.empty:
        print("Empty dataframe")
        return

    print(df.groupby(["segment", "instrument"]).size())


def cleanup_temp_files():
    for path in [TEMP_MAIN_PATH, TEMP_RAW_PATH]:
        try:
            if path.exists():
                path.unlink()
        except Exception as error:
            print(f"Could not delete temp file {path}: {error}")


def main():
    print("Starting NSE incremental monthly updater...")

    ensure_directories()

    if not MAIN_DATASET_PATH.exists():
        raise FileNotFoundError(f"Main dataset not found: {MAIN_DATASET_PATH}")

    if not RAW_EVIDENCE_PATH.exists():
        raise FileNotFoundError(f"Raw evidence dataset not found: {RAW_EVIDENCE_PATH}")

    current_main_df = normalize_main_df(read_csv_safely(MAIN_DATASET_PATH))
    current_raw_df = normalize_raw_df(read_csv_safely(RAW_EVIDENCE_PATH))

    main_rows_before = len(current_main_df)
    raw_rows_before = len(current_raw_df)

    latest_complete_month = get_latest_complete_month(current_main_df)

    if latest_complete_month is None:
        print("Latest complete month in current data: Not found")
    else:
        print(f"Latest complete month in current data: {latest_complete_month.strftime('%b-%Y')}")

    current_month_start = get_current_month_start()
    print(f"Current running month skipped from scraping: {current_month_start.strftime('%b-%Y')}")

    candidate_years = get_candidate_financial_years(latest_complete_month)
    print(f"Candidate financial years to check: {candidate_years}")

    create_backup_if_needed(current_main_df, current_raw_df)

    scraped_main_df, scraped_raw_df = run_candidate_scrape(
        current_main_df,
        current_raw_df,
    )

    candidate_main_df = get_new_candidate_main_rows(
        scraped_main_df,
        latest_complete_month,
    )

    print(f"Candidate scraped main rows: {len(candidate_main_df)}")

    if candidate_main_df.empty:
        candidate_raw_df = pd.DataFrame(columns=scraped_raw_df.columns)
    else:
        candidate_keys = set(
            zip(
                candidate_main_df["segment"].astype(str),
                candidate_main_df["instrument"].astype(str),
                candidate_main_df["month_label"].astype(str),
            )
        )

        candidate_raw_df = scraped_raw_df[
            scraped_raw_df.apply(
                lambda row: (
                    str(row["segment"]),
                    str(row["instrument"]),
                    str(row["month_label"]),
                ) in candidate_keys,
                axis=1,
            )
        ].copy()

    print(f"Candidate scraped raw rows : {len(candidate_raw_df)}")

    complete_new_months = get_complete_new_months(candidate_main_df)
    complete_month_labels = [
        month.strftime("%b-%Y")
        for month in complete_new_months
    ]

    print(f"Complete new months found : {complete_month_labels}")

    if not complete_new_months:
        print("\nNo complete new month found.")
        print("Nothing will be appended to main or raw.")
        print("Cleaning raw against current main keys and reloading SQLite only.")

        final_main_df = current_main_df.copy()
        final_raw_df = clean_raw_against_main(current_raw_df, final_main_df)

    else:
        complete_new_main_df = filter_main_to_complete_months(
            candidate_main_df,
            complete_new_months,
        )

        complete_new_raw_df = filter_raw_to_complete_main_rows(
            candidate_raw_df,
            complete_new_main_df,
        )

        print(f"Complete new main rows to append: {len(complete_new_main_df)}")
        print(f"Complete new raw rows to append : {len(complete_new_raw_df)}")

        final_main_df = merge_main_data(current_main_df, complete_new_main_df)
        final_raw_df = merge_raw_data(current_raw_df, complete_new_raw_df)
        final_raw_df = clean_raw_against_main(final_raw_df, final_main_df)

    save_outputs(final_main_df, final_raw_df)
    reload_sqlite(final_main_df)

    main_rows_after = len(final_main_df)
    raw_rows_after = len(final_raw_df)

    print("\nIncremental update completed.")
    print(f"Main rows before: {main_rows_before}")
    print(f"Main rows after : {main_rows_after}")
    print(f"Main rows added : {main_rows_after - main_rows_before}")

    print(f"\nRaw rows before : {raw_rows_before}")
    print(f"Raw rows after  : {raw_rows_after}")
    print(f"Raw rows added  : {raw_rows_after - raw_rows_before}")

    print_group_summary("Final main", final_main_df)
    print_group_summary("Final raw", final_raw_df)

    cleanup_temp_files()


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup_temp_files()