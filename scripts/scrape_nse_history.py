from pathlib import Path
from datetime import datetime
import re

import pandas as pd
from playwright.sync_api import sync_playwright


OUTPUT_DIR = Path("data/raw/nse_scraped")
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

COMBINED_RAW_FILE = OUTPUT_DIR / f"all_segments_monthly_raw_history_{timestamp}.csv"


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
    """
    Extract available financial years like 2025-2026, 2024-2025, etc.
    from clickable links/text on the NSE page.
    """

    body_text = page.locator("body").inner_text()

    years = re.findall(r"\b(20\d{2}-20\d{2}|19\d{2}-19\d{2})\b", body_text)

    unique_years = sorted(
        set(years),
        reverse=True
    )

    return unique_years


def find_monthly_table(page):
    tables = page.locator("table")
    table_count = tables.count()

    best_table_index = None
    best_table_rows = None

    month_keywords = [
        "JAN-",
        "FEB-",
        "MAR-",
        "APR-",
        "MAY-",
        "JUN-",
        "JUL-",
        "AUG-",
        "SEP-",
        "OCT-",
        "NOV-",
        "DEC-",
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


def rows_to_dataframe(
    source_name,
    segment_name,
    clicked_year,
    table_index,
    rows
):
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


def scrape_segment_history(page, source_name, segment_name, url):
    print("\n" + "=" * 120)
    print(f"Scraping full history for: {source_name}")
    print(f"Segment: {segment_name}")
    print(f"URL: {url}")
    print("=" * 120)

    open_segment_page(page, url)

    available_years = get_available_financial_years(page)

    print(f"Available financial years found: {len(available_years)}")
    print(available_years)

    segment_frames = []

    for year in available_years:
        print("\n" + "-" * 100)
        print(f"Processing {source_name} | {year}")

        try:
            # Reload fresh page for every year.
            # This is slower but more stable than clicking many years on the same DOM.
            open_segment_page(page, url)

            clicked = click_financial_year(page, year)

            if not clicked:
                print(f"Could not click year: {year}")
                continue

            table_index, monthly_rows = find_monthly_table(page)

            if not monthly_rows:
                print(f"No monthly table found for {source_name} | {year}")
                continue

            raw_df = rows_to_dataframe(
                source_name=source_name,
                segment_name=segment_name,
                clicked_year=year,
                table_index=table_index,
                rows=monthly_rows,
            )

            print(
                f"Scraped {len(raw_df)} raw rows "
                f"for {source_name} | {year}"
            )

            segment_frames.append(raw_df)

        except Exception as error:
            print(f"Failed for {source_name} | {year}")
            print(f"Error: {error}")

    if not segment_frames:
        print(f"No historical data scraped for {source_name}")
        return None

    segment_df = pd.concat(segment_frames, ignore_index=True)

    print(f"\nCompleted {source_name}")
    print(f"Total raw rows: {len(segment_df)}")
    print("Rows by clicked_year:")
    print(segment_df["clicked_year"].value_counts().sort_index())

    return segment_df


def scrape_all_segments_history():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_segment_frames = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
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
            segment_df = scrape_segment_history(
                page=page,
                source_name=source_name,
                segment_name=config["segment"],
                url=config["url"],
            )

            if segment_df is not None:
                all_segment_frames.append(segment_df)

        browser.close()

    if not all_segment_frames:
        print("No data scraped from any segment.")
        return None

    combined_df = pd.concat(
        all_segment_frames,
        ignore_index=True
    )

    combined_df.to_csv(
        COMBINED_RAW_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n" + "=" * 120)
    print("FULL HISTORICAL RAW SCRAPING COMPLETED")
    print(f"Combined raw file saved: {COMBINED_RAW_FILE}")

    print("\nRows by source:")
    print(combined_df["source_name"].value_counts())

    print("\nRows by source and clicked year:")
    print(
        combined_df
        .groupby(["source_name", "clicked_year"])
        .size()
        .reset_index(name="rows")
        .sort_values(["source_name", "clicked_year"])
    )

    return combined_df


if __name__ == "__main__":
    scrape_all_segments_history()