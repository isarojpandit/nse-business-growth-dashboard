import os
from pathlib import Path
import sqlite3
import pandas as pd

from scrape_nse_business_growth_daily import (
    NSE_SEGMENT_URLS,
    open_segment_page,
    click_text,
    click_month_from_summary_table,
    extract_tables,
    find_month_summary_table,
    get_months_from_summary_table,
    normalize_capital_market_year,
    extract_daily_rows_from_tables,
    get_daily_dataframe,
    aggregate_equity_derivatives,
    aggregate_currency_derivatives,
    aggregate_interest_rate_derivatives,
    build_equity_raw_rows,
    build_currency_raw_rows,
    build_ird_raw_rows,
    add_dashboard_fields,
    remove_incomplete_latest_month,
    get_available_financial_years,
)

from playwright.sync_api import sync_playwright


MAIN_FILE = Path("data/processed/clean_nse_business_growth_from_nse.csv")
RAW_FILE = Path("data/exports/final_raw_nse_daily_trading_days.csv")

BACKUP_DIR = Path("data/backups")

DB_FILE = Path("data/nse_business_growth.db")
TABLE_NAME = "nse_business_growth"


EXPECTED_GROUPS = {
    ("Capital Market", "NA"),
    ("Currency Derivatives", "Futures"),
    ("Currency Derivatives", "Options"),
    ("Equity Derivatives", "Futures"),
    ("Equity Derivatives", "Options"),
    ("Interest Rate Derivatives", "NA"),
}


def read_main_data():
    if not MAIN_FILE.exists():
        raise FileNotFoundError(f"Main CSV not found: {MAIN_FILE}")

    df = pd.read_csv(MAIN_FILE, keep_default_na=False)

    df["segment"] = df["segment"].astype(str).str.strip()
    df["instrument"] = df["instrument"].replace("", "NA").astype(str).str.strip()
    df["month_label"] = df["month_label"].astype(str).str.strip()
    df["month_date"] = pd.to_datetime(df["month_date"], errors="coerce")

    df = df.dropna(subset=["month_date"]).copy()

    return df


def read_raw_data():
    if not RAW_FILE.exists():
        print(f"Raw file not found, creating new raw dataframe: {RAW_FILE}")
        return pd.DataFrame()

    df = pd.read_csv(RAW_FILE, keep_default_na=False)

    if "segment" in df.columns:
        df["segment"] = df["segment"].astype(str).str.strip()

    if "instrument" in df.columns:
        df["instrument"] = df["instrument"].replace("", "NA").astype(str).str.strip()

    if "month_label" in df.columns:
        df["month_label"] = df["month_label"].astype(str).str.strip()

    return df


def backup_current_files():
    if os.getenv("GITHUB_ACTIONS") == "true":
        print("Running in GitHub Actions. Skipping backup file creation.")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")

    if MAIN_FILE.exists():
        backup_main = BACKUP_DIR / f"clean_nse_business_growth_from_nse_{timestamp}.csv"

        pd.read_csv(MAIN_FILE, keep_default_na=False).to_csv(
            backup_main,
            index=False,
            encoding="utf-8-sig",
        )

        print(f"Main backup created: {backup_main}")

    if RAW_FILE.exists():
        backup_raw = BACKUP_DIR / f"final_raw_nse_daily_trading_days_{timestamp}.csv"

        pd.read_csv(RAW_FILE, keep_default_na=False).to_csv(
            backup_raw,
            index=False,
            encoding="utf-8-sig",
        )

        print(f"Raw backup created: {backup_raw}")


def month_label_to_date(month_label):
    return pd.to_datetime(month_label, format="%b-%Y", errors="coerce")


def get_latest_complete_month(main_df):
    df = main_df.copy()

    df["segment"] = df["segment"].astype(str)
    df["instrument"] = df["instrument"].replace("", "NA").astype(str)
    df["month_label"] = df["month_label"].astype(str)

    grouped = (
        df.groupby("month_label")
        .apply(
            lambda x: set(
                zip(
                    x["segment"].astype(str),
                    x["instrument"].astype(str),
                )
            )
        )
        .reset_index(name="groups")
    )

    complete_months = []

    for _, row in grouped.iterrows():
        if EXPECTED_GROUPS.issubset(row["groups"]):
            complete_months.append(row["month_label"])

    if not complete_months:
        raise ValueError("No complete month found in existing main CSV.")

    complete_month_dates = [
        month_label_to_date(month_label)
        for month_label in complete_months
    ]

    latest_date = max(complete_month_dates)

    return latest_date


def get_candidate_years_from_latest(latest_complete_month):
    current_date = pd.Timestamp.today()

    candidate_years = set()

    start_year = latest_complete_month.year
    end_year = current_date.year + 1

    for year in range(start_year - 1, end_year + 1):
        candidate_years.add(f"{year}-{year + 1}")

    return candidate_years


def find_new_months_from_summary(summary_table, latest_complete_month):
    months = get_months_from_summary_table(summary_table)

    new_months = []

    for month_label in months:
        month_date = month_label_to_date(month_label)

        if pd.isna(month_date):
            continue

        if month_date > latest_complete_month:
            new_months.append(month_label)

    new_months = sorted(
        set(new_months),
        key=lambda value: month_label_to_date(value),
    )

    return new_months


def scrape_capital_market_incremental(page, url, available_years, latest_complete_month):
    main_rows = []
    raw_rows = []

    for year in available_years:
        print(f"\nChecking Capital Market year: {year}")

        opened = open_segment_page(page, url)

        if not opened:
            print(f"Could not open Capital Market page for year: {year}")
            continue

        clicked = click_text(page, year)

        if not clicked:
            print(f"Could not click Capital Market year: {year}")
            continue

        all_tables = extract_tables(page)
        summary_table = find_month_summary_table(all_tables)

        year_main_rows, year_raw_rows = normalize_capital_market_year(
            summary_table=summary_table,
            clicked_year=year,
        )

        new_month_labels = set()

        for row in year_main_rows:
            month_date = month_label_to_date(row["month_label"])

            if pd.isna(month_date):
                continue

            if month_date > latest_complete_month:
                main_rows.append(row)
                new_month_labels.add(row["month_label"])

        for row in year_raw_rows:
            if row["month_label"] in new_month_labels:
                raw_rows.append(row)

    return main_rows, raw_rows


def scrape_derivative_incremental(
    page,
    source_name,
    segment_name,
    url,
    available_years,
    latest_complete_month,
):
    main_rows = []
    raw_rows = []

    for year in available_years:
        print(f"\nChecking {segment_name} year: {year}")

        opened = open_segment_page(page, url)

        if not opened:
            print(f"Could not open {segment_name} page for year: {year}")
            continue

        clicked = click_text(page, year)

        if not clicked:
            print(f"Could not click {segment_name} year: {year}")
            continue

        all_tables = extract_tables(page)
        summary_table = find_month_summary_table(all_tables)

        new_months = find_new_months_from_summary(
            summary_table=summary_table,
            latest_complete_month=latest_complete_month,
        )

        print(f"New candidate months found: {new_months}")

        for month_label in new_months:
            print(f"  Processing {segment_name}: {month_label}")

            clicked_month = click_month_from_summary_table(page, month_label)

            if not clicked_month:
                print(f"  Could not click month: {month_label}")
                opened = open_segment_page(page, url)
                if opened:
                    click_text(page, year)
                continue

            all_month_tables = extract_tables(page)
            best_table_index, daily_rows = extract_daily_rows_from_tables(all_month_tables)

            if not daily_rows:
                print(f"  No daily rows found: {segment_name} | {month_label}")
                opened = open_segment_page(page, url)
                if opened:
                    click_text(page, year)
                continue

            daily_df = get_daily_dataframe(
                source_name=source_name,
                segment=segment_name,
                year=year,
                month_label=month_label,
                daily_rows=daily_rows,
            )

            if daily_df.empty:
                print(f"  Daily dataframe empty: {segment_name} | {month_label}")
                opened = open_segment_page(page, url)
                if opened:
                    click_text(page, year)
                continue

            print(
                f"  Daily rows: {len(daily_df)} | "
                f"active days: {daily_df['date'].nunique()} | "
                f"table index: {best_table_index}"
            )

            if source_name == "equity_derivatives":
                month_main_rows = aggregate_equity_derivatives(month_label, daily_df)
                month_raw_rows = build_equity_raw_rows(month_label, year, daily_df)

            elif source_name == "currency_derivatives":
                month_main_rows = aggregate_currency_derivatives(month_label, daily_df)
                month_raw_rows = build_currency_raw_rows(month_label, year, daily_df)

            elif source_name == "interest_rate_derivatives":
                month_main_rows = aggregate_interest_rate_derivatives(month_label, daily_df)
                month_raw_rows = build_ird_raw_rows(month_label, year, daily_df)

            else:
                month_main_rows = []
                month_raw_rows = []

            main_rows.extend(month_main_rows)
            raw_rows.extend(month_raw_rows)

            opened = open_segment_page(page, url)

            if opened:
                click_text(page, year)

    return main_rows, raw_rows


def get_complete_new_month_labels(existing_main_df, candidate_main_rows, latest_complete_month):
    if not candidate_main_rows:
        return set()

    candidate_df = pd.DataFrame(candidate_main_rows)

    candidate_df["segment"] = candidate_df["segment"].astype(str).str.strip()
    candidate_df["instrument"] = candidate_df["instrument"].replace("", "NA").astype(str).str.strip()
    candidate_df["month_label"] = candidate_df["month_label"].astype(str).str.strip()

    combined_df = pd.concat(
        [
            existing_main_df[
                [
                    "segment",
                    "instrument",
                    "month_label",
                ]
            ],
            candidate_df[
                [
                    "segment",
                    "instrument",
                    "month_label",
                ]
            ],
        ],
        ignore_index=True,
    )

    complete_month_labels = set()

    grouped = (
        combined_df.groupby("month_label")
        .apply(
            lambda x: set(
                zip(
                    x["segment"].astype(str),
                    x["instrument"].astype(str),
                )
            )
        )
        .reset_index(name="groups")
    )

    for _, row in grouped.iterrows():
        month_label = row["month_label"]
        month_date = month_label_to_date(month_label)

        if pd.isna(month_date):
            continue

        if month_date <= latest_complete_month:
            continue

        if EXPECTED_GROUPS.issubset(row["groups"]):
            complete_month_labels.add(month_label)

    return complete_month_labels


def filter_new_rows_to_complete_months(candidate_main_rows, candidate_raw_rows, complete_month_labels):
    if not complete_month_labels:
        return [], []

    filtered_main_rows = [
        row
        for row in candidate_main_rows
        if row.get("month_label") in complete_month_labels
    ]

    filtered_raw_rows = [
        row
        for row in candidate_raw_rows
        if row.get("month_label") in complete_month_labels
    ]

    return filtered_main_rows, filtered_raw_rows


def append_unique_main_rows(main_df, new_rows):
    if not new_rows:
        return main_df.copy()

    new_df = pd.DataFrame(new_rows)

    combined = pd.concat([main_df, new_df], ignore_index=True)

    combined["instrument"] = combined["instrument"].replace("", "NA").astype(str)

    combined = combined.drop_duplicates(
        subset=["segment", "instrument", "month_label"],
        keep="last",
    )

    return combined


def append_unique_raw_rows(raw_df, new_rows):
    if not new_rows:
        return raw_df.copy()

    new_df = pd.DataFrame(new_rows)

    combined = pd.concat([raw_df, new_df], ignore_index=True)

    if "instrument" in combined.columns:
        combined["instrument"] = combined["instrument"].replace("", "NA").astype(str)

    required_subset = [
        "source_name",
        "segment",
        "instrument",
        "clicked_year",
        "month_label",
        "date",
        "source_level",
    ]

    available_subset = [
        column
        for column in required_subset
        if column in combined.columns
    ]

    if available_subset:
        combined = combined.drop_duplicates(
            subset=available_subset,
            keep="last",
        )

    return combined


def filter_raw_to_main(raw_df, main_df):
    if raw_df.empty:
        return raw_df.copy()

    main_keys = set(
        zip(
            main_df["segment"].astype(str),
            main_df["instrument"].replace("", "NA").astype(str),
            main_df["month_label"].astype(str),
        )
    )

    raw_df = raw_df.copy()

    raw_df["segment"] = raw_df["segment"].astype(str)
    raw_df["instrument"] = raw_df["instrument"].replace("", "NA").astype(str)
    raw_df["month_label"] = raw_df["month_label"].astype(str)

    raw_df = raw_df[
        raw_df.apply(
            lambda row: (
                row["segment"],
                row["instrument"],
                row["month_label"],
            )
            in main_keys,
            axis=1,
        )
    ].copy()

    return raw_df


def save_outputs(main_df, raw_df):
    main_df = add_dashboard_fields(main_df)

    main_df = main_df.drop_duplicates(
        subset=["segment", "instrument", "month_label"],
        keep="last",
    )

    main_df = remove_incomplete_latest_month(main_df)

    main_df = main_df.sort_values(
        ["segment", "instrument", "month_date"]
    )

    raw_df = raw_df.copy()

    if not raw_df.empty:
        raw_df = filter_raw_to_main(raw_df, main_df)

        raw_df = raw_df.drop_duplicates(
            subset=[
                "source_name",
                "segment",
                "instrument",
                "clicked_year",
                "month_label",
                "date",
                "source_level",
            ],
            keep="last",
        )

    MAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_FILE.parent.mkdir(parents=True, exist_ok=True)

    main_df.to_csv(
        MAIN_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    raw_df.to_csv(
        RAW_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    return main_df, raw_df


def reload_sqlite(main_df):
    db_df = main_df.copy()

    db_df["month_date"] = pd.to_datetime(db_df["month_date"], errors="coerce")
    db_df = db_df.dropna(subset=["month_date"]).copy()
    db_df["month_date"] = db_df["month_date"].dt.strftime("%Y-%m-%d")

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)

    db_df.to_sql(
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

    conn.close()

    print("\nSQLite reloaded successfully.")
    print(check_df.to_string(index=False))


def main():
    print("Starting NSE incremental monthly updater...")
    print()

    main_df = read_main_data()
    raw_df = read_raw_data()

    latest_complete_month = get_latest_complete_month(main_df)

    print(f"Latest complete month in current data: {latest_complete_month.strftime('%b-%Y')}")

    candidate_years = get_candidate_years_from_latest(latest_complete_month)

    print(f"Candidate financial years to check: {sorted(candidate_years)}")

    backup_current_files()

    all_candidate_main_rows = []
    all_candidate_raw_rows = []

    with sync_playwright() as p:
        headless = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"

        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            ignore_https_errors=True,
        )

        page = context.new_page()

        for source_name, config in NSE_SEGMENT_URLS.items():
            segment_name = config["segment"]
            url = config["url"]

            print("\n" + "=" * 100)
            print(f"Checking segment: {segment_name}")
            print("=" * 100)

            opened = open_segment_page(page, url)

            if not opened:
                print(f"Could not open segment page: {segment_name}")
                continue

            website_years = get_available_financial_years(page)

            available_years = [
                year
                for year in website_years
                if year in candidate_years
            ]

            if not available_years:
                print(f"No candidate years found on page for {segment_name}")
                continue

            print(f"Available candidate years: {available_years}")

            if source_name == "capital_market":
                segment_main_rows, segment_raw_rows = scrape_capital_market_incremental(
                    page=page,
                    url=url,
                    available_years=available_years,
                    latest_complete_month=latest_complete_month,
                )

            else:
                segment_main_rows, segment_raw_rows = scrape_derivative_incremental(
                    page=page,
                    source_name=source_name,
                    segment_name=segment_name,
                    url=url,
                    available_years=available_years,
                    latest_complete_month=latest_complete_month,
                )

            all_candidate_main_rows.extend(segment_main_rows)
            all_candidate_raw_rows.extend(segment_raw_rows)

        browser.close()

    complete_new_month_labels = get_complete_new_month_labels(
        existing_main_df=main_df,
        candidate_main_rows=all_candidate_main_rows,
        latest_complete_month=latest_complete_month,
    )

    print()
    print(f"Candidate scraped main rows: {len(all_candidate_main_rows)}")
    print(f"Candidate scraped raw rows : {len(all_candidate_raw_rows)}")
    print(f"Complete new months found : {sorted(complete_new_month_labels)}")

    new_main_rows, new_raw_rows = filter_new_rows_to_complete_months(
        candidate_main_rows=all_candidate_main_rows,
        candidate_raw_rows=all_candidate_raw_rows,
        complete_month_labels=complete_new_month_labels,
    )

    if not complete_new_month_labels:
        print()
        print("No complete new month found.")
        print("Nothing will be appended to main or raw.")
        print("Cleaning raw against current main keys and reloading SQLite only.")

    before_main_rows = len(main_df)
    before_raw_rows = len(raw_df)

    updated_main_df = append_unique_main_rows(main_df, new_main_rows)
    updated_raw_df = append_unique_raw_rows(raw_df, new_raw_rows)

    final_main_df, final_raw_df = save_outputs(updated_main_df, updated_raw_df)

    reload_sqlite(final_main_df)

    print("\nIncremental update completed.")
    print(f"Main rows before: {before_main_rows}")
    print(f"Main rows after : {len(final_main_df)}")
    print(f"Main rows added : {len(final_main_df) - before_main_rows}")
    print()
    print(f"Raw rows before : {before_raw_rows}")
    print(f"Raw rows after  : {len(final_raw_df)}")
    print(f"Raw rows added  : {len(final_raw_df) - before_raw_rows}")
    print()
    print("Final main group summary:")
    print(
        final_main_df.groupby(["segment", "instrument"], dropna=False)
        .size()
        .to_string()
    )
    print()
    print("Final raw group summary:")
    if not final_raw_df.empty:
        print(
            final_raw_df.groupby(["segment", "instrument"], dropna=False)
            .size()
            .to_string()
        )
    else:
        print("Raw dataframe is empty.")


if __name__ == "__main__":
    main()