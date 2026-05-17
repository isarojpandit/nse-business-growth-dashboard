import sys
import re
import os
from pathlib import Path
from datetime import datetime

import pandas as pd
from playwright.sync_api import sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "nse_scraped"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

MAIN_DATASET_PATH = PROCESSED_DIR / "clean_nse_business_growth_from_nse.csv"

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LATEST_RAW_FILE = RAW_DIR / f"all_segments_monthly_raw_latest_{timestamp}.csv"
BACKUP_FILE = PROCESSED_DIR / f"backup_clean_nse_business_growth_from_nse_{timestamp}.csv"


NSE_SEGMENT_URLS = {
    "capital_market": {
        "segment": "Capital Market",
        "url": "https://www.nseindia.com/market-data/business-growth-cm-segment",
    },
    "equity_derivatives": {
        "segment": "Equity Derivatives",
        "url": "https://www.nseindia.com/market-data/business-growth-fo-segment",
    },
    "currency_derivatives": {
        "segment": "Currency Derivatives",
        "url": "https://www.nseindia.com/market-data/business-growth-cd-segment",
    },
    "interest_rate_derivatives": {
        "segment": "Interest Rate Derivatives",
        "url": "https://www.nseindia.com/market-data/business-growth-interest-rate-derivative",
    },
}


def is_ci_environment():
    return os.getenv("CI", "false").lower() == "true"


def clean_number(value):
    if value is None or pd.isna(value):
        return None

    value = str(value).strip()

    if value in ["", "-", "nan", "None"]:
        return None

    value = value.replace(",", "")

    try:
        return float(value)
    except Exception:
        return None


def normalize_month_label(value):
    if value is None or pd.isna(value):
        return None

    value = str(value).replace("\n", "").strip()

    for fmt in ["%b-%Y", "%b-%y"]:
        parsed = pd.to_datetime(value, format=fmt, errors="coerce")

        if not pd.isna(parsed):
            return parsed.strftime("%b-%Y")

    return None


def month_label_to_date(month_label):
    return pd.to_datetime(month_label, format="%b-%Y", errors="coerce")


def get_financial_year(month_date):
    if pd.isna(month_date):
        return None

    year = month_date.year
    month = month_date.month

    if month >= 4:
        return f"FY {year}-{str(year + 1)[-2:]}"

    return f"FY {year - 1}-{str(year)[-2:]}"


def get_financial_quarter(month_date):
    if pd.isna(month_date):
        return None

    month = month_date.month

    if month in [4, 5, 6]:
        return "Q1"

    if month in [7, 8, 9]:
        return "Q2"

    if month in [10, 11, 12]:
        return "Q3"

    if month in [1, 2, 3]:
        return "Q4"

    return None


def get_calendar_quarter(month_date):
    if pd.isna(month_date):
        return None

    quarter = ((month_date.month - 1) // 3) + 1
    return f"Q{quarter}-{month_date.year}"


def fix_instrument_na(df):
    df = df.copy()

    if "instrument" in df.columns:
        df["instrument"] = (
            df["instrument"]
            .replace("", "NA")
            .fillna("NA")
            .astype(str)
            .str.strip()
        )

    return df


def extract_table_rows(table):
    rows = table.locator("tr")
    row_count = rows.count()

    extracted_rows = []

    for i in range(row_count):
        row = rows.nth(i)
        cells = row.locator("th, td")
        cell_count = cells.count()

        row_data = []

        for j in range(cell_count):
            text = cells.nth(j).inner_text().strip()
            row_data.append(text)

        if any(cell.strip() for cell in row_data):
            extracted_rows.append(row_data)

    return extracted_rows


def get_available_financial_years(page):
    body_text = page.locator("body").inner_text()

    years = re.findall(
        r"\b(?:19|20)\d{2}-(?:19|20)\d{2}\b",
        body_text
    )

    unique_years = sorted(
        set(years),
        key=lambda value: int(value.split("-")[0]),
        reverse=True
    )

    return unique_years


def find_monthly_table(page):
    tables = page.locator("table")
    table_count = tables.count()

    best_table_index = None
    best_table_rows = None

    month_keywords = [
        "JAN-", "FEB-", "MAR-", "APR-", "MAY-", "JUN-",
        "JUL-", "AUG-", "SEP-", "OCT-", "NOV-", "DEC-"
    ]

    for table_index in range(table_count):
        table = tables.nth(table_index)
        table_text = table.inner_text().strip()
        table_text_upper = table_text.upper()

        has_month_header = (
            "MONTH" in table_text_upper
            or "MONTH / YEAR" in table_text_upper
        )

        has_month_rows = any(
            keyword in table_text_upper
            for keyword in month_keywords
        )

        has_turnover = (
            "TURNOVER" in table_text_upper
            or "VALUE" in table_text_upper
        )

        has_activity_metric = (
            "VOLUME" in table_text_upper
            or "QUANTITY" in table_text_upper
            or "NO. OF CONTRACTS" in table_text_upper
            or "NO OF CONTRACTS" in table_text_upper
            or "CONTRACTS" in table_text_upper
        )

        has_no_records_only = (
            "NO RECORDS" in table_text_upper
            and not has_month_rows
        )

        if (
            has_month_header
            and has_month_rows
            and has_turnover
            and has_activity_metric
            and not has_no_records_only
        ):
            best_table_index = table_index
            best_table_rows = extract_table_rows(table)

    return best_table_index, best_table_rows


def open_segment_page(page, url):
    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    page.wait_for_timeout(12000)
    page.mouse.wheel(0, 700)
    page.wait_for_timeout(2000)


def click_financial_year(page, year):
    locator = page.locator(f"text={year}")
    count = locator.count()

    if count == 0:
        return False

    locator.first.click()
    page.wait_for_timeout(6000)

    return True


def rows_to_dataframe(source_name, segment_name, clicked_year, table_index, rows):
    max_cols = max(len(row) for row in rows)
    columns = [f"col_{i + 1}" for i in range(max_cols)]

    normalized_rows = []

    for row in rows:
        padded_row = row + [""] * (max_cols - len(row))
        normalized_rows.append(padded_row)

    df = pd.DataFrame(normalized_rows, columns=columns)

    df.insert(0, "source_name", source_name)
    df.insert(1, "segment", segment_name)
    df.insert(2, "clicked_year", clicked_year)
    df.insert(3, "table_index", table_index)

    return df


def scrape_latest_raw_data(years_to_scrape=2):
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    all_frames = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=is_ci_environment(),
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
        )

        page = context.new_page()

        for source_name, config in NSE_SEGMENT_URLS.items():
            print("\n" + "=" * 100)
            print(f"Scraping latest data for: {source_name}")
            print("=" * 100)

            url = config["url"]
            segment_name = config["segment"]

            open_segment_page(page, url)

            available_years = get_available_financial_years(page)
            selected_years = available_years[:years_to_scrape]

            print(f"Available years: {available_years[:5]}")
            print(f"Selected years for update: {selected_years}")

            for year in selected_years:
                try:
                    open_segment_page(page, url)

                    clicked = click_financial_year(page, year)

                    if not clicked:
                        print(f"Could not click year: {year}")
                        continue

                    table_index, rows = find_monthly_table(page)

                    if not rows:
                        print(f"No monthly table found for {source_name} | {year}")
                        continue

                    raw_df = rows_to_dataframe(
                        source_name=source_name,
                        segment_name=segment_name,
                        clicked_year=year,
                        table_index=table_index,
                        rows=rows,
                    )

                    print(
                        f"Scraped rows: {len(raw_df)} | "
                        f"{source_name} | {year}"
                    )

                    all_frames.append(raw_df)

                except Exception as error:
                    print(f"Failed: {source_name} | {year}")
                    print(f"Error: {error}")

        browser.close()

    if not all_frames:
        raise ValueError("No latest raw data scraped.")

    combined_raw = pd.concat(all_frames, ignore_index=True)

    combined_raw.to_csv(
        LATEST_RAW_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("\nLatest raw update file saved:")
    print(LATEST_RAW_FILE)

    print("\nLatest raw rows by source:")
    print(combined_raw["source_name"].value_counts())

    return combined_raw


def get_value(row, column_name):
    if column_name not in row.index:
        return None

    value = row[column_name]

    if pd.isna(value):
        return None

    return value


def build_trading_days_map(raw_df):
    trading_days_map = {}

    cm_df = raw_df[raw_df["source_name"] == "capital_market"].copy()

    for _, row in cm_df.iterrows():
        month_label = normalize_month_label(get_value(row, "col_1"))

        if month_label is None:
            continue

        trading_days = clean_number(get_value(row, "col_5"))

        if trading_days is None or trading_days == 0:
            continue

        trading_days_map[month_label] = trading_days

    return trading_days_map


def normalize_latest_raw(raw_df):
    trading_days_map = build_trading_days_map(raw_df)

    rows = []

    for _, row in raw_df.iterrows():
        source_name = get_value(row, "source_name")
        month_label = normalize_month_label(get_value(row, "col_1"))

        if month_label is None:
            continue

        trading_days = trading_days_map.get(month_label)

        if trading_days is None or trading_days == 0:
            continue

        if source_name == "capital_market":
            traded_quantity_lakhs = clean_number(get_value(row, "col_8"))
            monthly_turnover_crores = clean_number(get_value(row, "col_9"))

            if traded_quantity_lakhs is not None and monthly_turnover_crores is not None:
                rows.append(
                    {
                        "segment": "Capital Market",
                        "instrument": "NA",
                        "month_label": month_label,
                        "turnover": monthly_turnover_crores / trading_days,
                        "volume": traded_quantity_lakhs / trading_days,
                    }
                )

        elif source_name == "equity_derivatives":
            index_futures_contracts = clean_number(get_value(row, "col_2"))
            index_futures_turnover = clean_number(get_value(row, "col_3"))

            index_options_contracts = clean_number(get_value(row, "col_8"))
            index_options_premium_turnover = clean_number(get_value(row, "col_9"))

            if index_futures_contracts is not None and index_futures_turnover is not None:
                rows.append(
                    {
                        "segment": "Equity Derivatives",
                        "instrument": "Futures",
                        "month_label": month_label,
                        "turnover": index_futures_turnover / trading_days,
                        "volume": index_futures_contracts / trading_days,
                    }
                )

            if index_options_contracts is not None and index_options_premium_turnover is not None:
                rows.append(
                    {
                        "segment": "Equity Derivatives",
                        "instrument": "Options",
                        "month_label": month_label,
                        "turnover": index_options_premium_turnover / trading_days,
                        "volume": index_options_contracts / trading_days,
                    }
                )

        elif source_name == "currency_derivatives":
            currency_futures_contracts = clean_number(get_value(row, "col_2"))
            currency_futures_turnover = clean_number(get_value(row, "col_3"))

            currency_options_contracts = clean_number(get_value(row, "col_4"))
            currency_options_premium_turnover = clean_number(get_value(row, "col_6"))

            if currency_futures_contracts is not None and currency_futures_turnover is not None:
                rows.append(
                    {
                        "segment": "Currency Derivatives",
                        "instrument": "Futures",
                        "month_label": month_label,
                        "turnover": currency_futures_turnover / trading_days,
                        "volume": currency_futures_contracts / trading_days,
                    }
                )

            if currency_options_contracts is not None and currency_options_premium_turnover is not None:
                rows.append(
                    {
                        "segment": "Currency Derivatives",
                        "instrument": "Options",
                        "month_label": month_label,
                        "turnover": currency_options_premium_turnover / trading_days,
                        "volume": currency_options_contracts / trading_days,
                    }
                )

        elif source_name == "interest_rate_derivatives":
            volume_contracts = clean_number(get_value(row, "col_2"))
            monthly_turnover_crores = clean_number(get_value(row, "col_3"))

            if volume_contracts is not None and monthly_turnover_crores is not None:
                rows.append(
                    {
                        "segment": "Interest Rate Derivatives",
                        "instrument": "NA",
                        "month_label": month_label,
                        "turnover": monthly_turnover_crores / trading_days,
                        "volume": volume_contracts / trading_days,
                    }
                )

    latest_df = pd.DataFrame(rows)

    return latest_df


def add_dashboard_fields(df):
    df = df.copy()

    df["instrument"] = (
        df["instrument"]
        .replace("", "NA")
        .fillna("NA")
        .astype(str)
        .str.strip()
    )

    df["segment"] = df["segment"].astype(str).str.strip()
    df["month_label"] = df["month_label"].astype(str).str.strip()

    df["month_date"] = df["month_label"].apply(month_label_to_date)
    df = df.dropna(subset=["month_date"])

    df["year"] = df["month_date"].dt.year.astype(int)
    df["calendar_quarter"] = df["month_date"].apply(get_calendar_quarter)
    df["financial_year"] = df["month_date"].apply(get_financial_year)
    df["financial_quarter"] = df["month_date"].apply(get_financial_quarter)

    df["turnover"] = pd.to_numeric(df["turnover"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

    df = df.sort_values(
        ["segment", "instrument", "month_date"]
    )

    df["mom_turnover_change"] = (
        df.groupby(["segment", "instrument"])["turnover"].pct_change()
    )

    df["mom_volume_change"] = (
        df.groupby(["segment", "instrument"])["volume"].pct_change()
    )

    df = df[
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
            "volume",
            "mom_turnover_change",
            "mom_volume_change",
        ]
    ]

    return df


def get_group_counts(df, count_column_name):
    df = fix_instrument_na(df)

    counts = (
        df.groupby(["segment", "instrument"])
        .size()
        .reset_index(name=count_column_name)
    )

    return counts


def safety_check_before_overwrite(existing_df, final_df):
    old_counts = get_group_counts(existing_df, "old_rows")
    new_counts = get_group_counts(final_df, "new_rows")

    count_check = old_counts.merge(
        new_counts,
        on=["segment", "instrument"],
        how="left"
    )

    count_check["new_rows"] = count_check["new_rows"].fillna(0).astype(int)

    dropped_groups = count_check[
        count_check["new_rows"] < count_check["old_rows"]
    ]

    if not dropped_groups.empty:
        print("\nERROR: Row count decreased for some groups.")
        print(dropped_groups)
        raise ValueError(
            "Safety check failed. Main dataset was not overwritten."
        )

    print("\nSafety check passed. No segment/instrument history was dropped.")


def update_main_dataset():
    if not MAIN_DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Main dataset not found: {MAIN_DATASET_PATH}. "
            "Run historical normalization first."
        )

    print(f"Reading existing main dataset: {MAIN_DATASET_PATH}")

    existing_df = pd.read_csv(
        MAIN_DATASET_PATH,
        keep_default_na=False
    )

    existing_df = fix_instrument_na(existing_df)

    print(f"Existing rows: {len(existing_df)}")

    existing_df.to_csv(
        BACKUP_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print(f"Backup created: {BACKUP_FILE}")

    latest_raw_df = scrape_latest_raw_data(years_to_scrape=2)

    latest_normalized_df = normalize_latest_raw(latest_raw_df)

    if latest_normalized_df.empty:
        raise ValueError("Latest normalization produced 0 rows.")

    latest_normalized_df = add_dashboard_fields(latest_normalized_df)

    print(f"\nLatest normalized rows: {len(latest_normalized_df)}")

    combined_df = pd.concat(
        [existing_df, latest_normalized_df],
        ignore_index=True
    )

    before_dedup = len(combined_df)

    combined_df = fix_instrument_na(combined_df)

    combined_df = combined_df.drop_duplicates(
        subset=["segment", "instrument", "month_label"],
        keep="last"
    )

    after_dedup = len(combined_df)

    print(f"Rows before dedup: {before_dedup}")
    print(f"Rows after dedup: {after_dedup}")
    print(f"Rows updated/replaced: {before_dedup - after_dedup}")

    combined_df = add_dashboard_fields(combined_df)

    safety_check_before_overwrite(
        existing_df=existing_df,
        final_df=combined_df
    )

    combined_df.to_csv(
        MAIN_DATASET_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nMain dataset updated successfully:")
    print(MAIN_DATASET_PATH)

    print("\nRows by segment/instrument:")
    print(
        combined_df
        .groupby(["segment", "instrument"])
        .size()
        .reset_index(name="rows")
    )

    print("\nLatest month by segment/instrument:")
    print(
        combined_df
        .groupby(["segment", "instrument"])
        .agg(latest_month=("month_date", "max"))
        .reset_index()
    )


if __name__ == "__main__":
    update_main_dataset()