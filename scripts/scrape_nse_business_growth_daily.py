from pathlib import Path
from datetime import datetime
import re

import pandas as pd
from playwright.sync_api import sync_playwright


EXPORT_DIR = Path("data/exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

MAIN_OUTPUT_FILE = EXPORT_DIR / "test_clean_nse_business_growth_from_daily.csv"
RAW_OUTPUT_FILE = EXPORT_DIR / "raw_nse_daily_trading_days.csv"

MAX_YEARS_PER_SEGMENT = None

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

EXPECTED_SEGMENT_INSTRUMENT_GROUPS = {
    ("Capital Market", "NA"),
    ("Equity Derivatives", "Futures"),
    ("Equity Derivatives", "Options"),
    ("Currency Derivatives", "Futures"),
    ("Currency Derivatives", "Options"),
    ("Interest Rate Derivatives", "NA"),
}


def clean_number(value):
    if value is None or pd.isna(value):
        return None

    value = str(value).strip()

    if value in ["", "-", "nan", "None"]:
        return None

    value = value.replace(",", "")
    value = value.replace("₹", "")
    value = value.replace("Cr", "")
    value = value.strip()

    try:
        return float(value)
    except Exception:
        return None


def normalize_date_text(value):
    if value is None or pd.isna(value):
        return ""

    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("- ", "-")
    text = text.replace(" -", "-")
    text = text.replace("/ ", "/")
    text = text.replace(" /", "/")

    return text


def parse_daily_date(value):
    text = normalize_date_text(value)

    if not text:
        return None

    if re.fullmatch(r"\d+(\.\d+)?", text):
        return None

    allowed_patterns = [
        r"^\d{1,2}-[A-Za-z]{3}-\d{4}$",
        r"^\d{1,2}-[A-Za-z]{3}-\d{2}$",
        r"^\d{1,2}/[A-Za-z]{3}/\d{4}$",
        r"^\d{1,2}/[A-Za-z]{3}/\d{2}$",
        r"^\d{1,2}-\d{1,2}-\d{4}$",
        r"^\d{1,2}/\d{1,2}/\d{4}$",
        r"^\d{4}-\d{1,2}-\d{1,2}$",
    ]

    if not any(re.fullmatch(pattern, text) for pattern in allowed_patterns):
        return None

    date_formats = [
        "%d-%b-%Y",
        "%d-%b-%y",
        "%d/%b/%Y",
        "%d/%b/%y",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
    ]

    for fmt in date_formats:
        parsed = pd.to_datetime(text, format=fmt, errors="coerce")

        if not pd.isna(parsed):
            if 1990 <= parsed.year <= datetime.now().year + 1:
                return parsed

    return None


def normalize_month_label(value):
    if value is None or pd.isna(value):
        return None

    text = str(value).replace("\n", "").strip()
    text = re.sub(r"\s+", "", text)

    for fmt in ["%b-%Y", "%b-%y"]:
        parsed = pd.to_datetime(text, format=fmt, errors="coerce")

        if not pd.isna(parsed):
            return parsed.strftime("%b-%Y")

    parsed_daily = parse_daily_date(value)

    if parsed_daily is not None:
        return parsed_daily.strftime("%b-%Y")

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


def load_existing_outputs():
    if MAIN_OUTPUT_FILE.exists():
        main_df = pd.read_csv(MAIN_OUTPUT_FILE)
        print(f"Existing main file loaded: {MAIN_OUTPUT_FILE} | rows={len(main_df)}")
    else:
        main_df = pd.DataFrame()

    if RAW_OUTPUT_FILE.exists():
        raw_df = pd.read_csv(RAW_OUTPUT_FILE)
        print(f"Existing raw file loaded: {RAW_OUTPUT_FILE} | rows={len(raw_df)}")
    else:
        raw_df = pd.DataFrame()

    return main_df, raw_df


def dataframe_to_source_main_rows(main_df):
    if main_df.empty:
        return []

    needed_columns = [
        "segment",
        "instrument",
        "month_label",
        "monthly_turnover",
        "monthly_volume",
        "active_trading_days",
        "turnover",
        "volume",
        "source_logic",
    ]

    available_columns = [column for column in needed_columns if column in main_df.columns]

    return main_df[available_columns].to_dict("records")


def dataframe_to_raw_rows(raw_df):
    if raw_df.empty:
        return []

    return raw_df.to_dict("records")


def get_existing_main_keys(main_rows):
    if not main_rows:
        return set()

    df = pd.DataFrame(main_rows)

    required_columns = {"segment", "instrument", "month_label"}

    if not required_columns.issubset(df.columns):
        return set()

    return set(
        zip(
            df["segment"].astype(str),
            df["instrument"].astype(str),
            df["month_label"].astype(str),
        )
    )


def get_existing_raw_keys(raw_rows):
    if not raw_rows:
        return set()

    df = pd.DataFrame(raw_rows)

    required_columns = {
        "segment",
        "instrument",
        "month_label",
        "clicked_year",
        "source_level",
        "date",
    }

    if not required_columns.issubset(df.columns):
        return set()

    return set(
        zip(
            df["segment"].astype(str),
            df["instrument"].astype(str),
            df["month_label"].astype(str),
            df["clicked_year"].astype(str),
            df["source_level"].astype(str),
            df["date"].astype(str),
        )
    )


def get_existing_missing_daily_keys(raw_rows):
    if not raw_rows:
        return set()

    df = pd.DataFrame(raw_rows)

    required_columns = {"segment", "month_label", "source_level"}

    if not required_columns.issubset(df.columns):
        return set()

    missing_df = df[df["source_level"].astype(str) == "missing_daily_table"].copy()

    if missing_df.empty:
        return set()

    return set(
        zip(
            missing_df["segment"].astype(str),
            missing_df["month_label"].astype(str),
        )
    )


def open_segment_page(page, url, retries=5):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            print(f"Opening page attempt {attempt}/{retries}: {url}")

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=90000,
            )

            page.wait_for_timeout(12000)
            page.mouse.wheel(0, 900)
            page.wait_for_timeout(2500)

            return True

        except Exception as error:
            last_error = error
            print(f"Page open failed attempt {attempt}/{retries}: {error}")

            try:
                page.wait_for_timeout(5000)
                page.reload(wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(5000)
                page.mouse.wheel(0, 900)
                page.wait_for_timeout(2500)
                return True
            except Exception as reload_error:
                print(f"Reload also failed: {reload_error}")

            page.wait_for_timeout(8000)

    print(f"Failed to open page after {retries} attempts: {url}")
    print(f"Last error: {last_error}")

    return False


def click_text(page, text, wait_ms=7000, retries=3):
    for attempt in range(1, retries + 1):
        try:
            locator = page.locator(f"text={text}")
            count = locator.count()

            if count == 0:
                print(f"Text not found: {text}")
                return False

            locator.first.click(timeout=15000)
            page.wait_for_timeout(wait_ms)

            return True

        except Exception as error:
            print(f"Click text failed attempt {attempt}/{retries}: {text} | {error}")
            page.wait_for_timeout(3000)

    return False


def click_month_from_summary_table(page, month_label, retries=3):
    month_dt = pd.to_datetime(month_label, format="%b-%Y", errors="coerce")

    month_variants = {
        month_label,
        month_label.upper(),
        month_label.title(),
    }

    if not pd.isna(month_dt):
        month_variants.update(
            {
                month_dt.strftime("%b-%Y"),
                month_dt.strftime("%b-%y"),
                month_dt.strftime("%B-%Y"),
                month_dt.strftime("%B %Y"),
                month_dt.strftime("%b %Y"),
                month_dt.strftime("%b").upper() + "-" + str(month_dt.year),
                month_dt.strftime("%b").title() + "-" + str(month_dt.year),
            }
        )

    for attempt in range(1, retries + 1):
        print(f"    Month click attempt {attempt}/{retries}: {month_label}")

        for value in month_variants:
            cell_locator = page.locator(
                "table tr td, table tr th"
            ).filter(
                has_text=re.compile(
                    rf"^\s*{re.escape(value)}\s*$",
                    re.IGNORECASE,
                )
            )

            count = cell_locator.count()
            print(f"    Month cell '{value}' exact table-cell count: {count}")

            for index in range(count):
                cell = cell_locator.nth(index)

                try:
                    if cell.is_visible():
                        cell.scroll_into_view_if_needed()
                        page.wait_for_timeout(500)
                        cell.click(timeout=15000)
                        page.wait_for_timeout(7000)
                        return True

                except Exception as error:
                    print(f"    Exact month cell click failed: {value} index {index}: {error}")

        for value in month_variants:
            row_locator = page.locator("table tr").filter(
                has_text=re.compile(re.escape(value), re.IGNORECASE)
            )

            count = row_locator.count()
            print(f"    Month row '{value}' count: {count}")

            for index in range(count):
                row = row_locator.nth(index)

                try:
                    if row.is_visible():
                        row.scroll_into_view_if_needed()
                        page.wait_for_timeout(500)

                        clickable = row.locator("a, button, td, th").first

                        if clickable.count() > 0:
                            clickable.click(timeout=15000)
                        else:
                            row.click(timeout=15000)

                        page.wait_for_timeout(7000)
                        return True

                except Exception as error:
                    print(f"    Month row click failed: {value} index {index}: {error}")

        page.wait_for_timeout(3000)

    return False


def get_available_financial_years(page):
    body_text = page.locator("body").inner_text()

    years = re.findall(
        r"\b(?:19|20)\d{2}-(?:19|20)\d{2}\b",
        body_text,
    )

    years = sorted(
        set(years),
        key=lambda value: int(value.split("-")[0]),
        reverse=True,
    )

    return years


def extract_tables(page):
    tables = page.locator("table")
    table_count = tables.count()

    all_tables = []

    for table_index in range(table_count):
        table = tables.nth(table_index)
        rows = table.locator("tr")
        row_count = rows.count()

        table_rows = []

        for row_index in range(row_count):
            row = rows.nth(row_index)
            cells = row.locator("th, td")
            cell_count = cells.count()

            row_values = []

            for cell_index in range(cell_count):
                try:
                    text = cells.nth(cell_index).inner_text().strip()
                except Exception:
                    text = ""

                row_values.append(text)

            if any(str(value).strip() for value in row_values):
                table_rows.append(row_values)

        all_tables.append(
            {
                "table_index": table_index,
                "rows": table_rows,
            }
        )

    return all_tables


def find_month_summary_table(all_tables):
    best_table = None
    best_month_count = 0

    for table_info in all_tables:
        rows = table_info["rows"]
        month_count = 0

        for row in rows:
            if not row:
                continue

            month_label = normalize_month_label(row[0])

            if month_label is not None:
                month_count += 1

        if month_count > best_month_count:
            best_month_count = month_count
            best_table = table_info

    return best_table


def get_months_from_summary_table(summary_table):
    months = []

    if summary_table is None:
        return months

    for row in summary_table["rows"]:
        if not row:
            continue

        month_label = normalize_month_label(row[0])

        if month_label is not None:
            months.append(month_label)

    months = sorted(
        set(months),
        key=lambda value: pd.to_datetime(value, format="%b-%Y", errors="coerce"),
        reverse=True,
    )

    return months


def restore_year_summary_page(page, url, year):
    print(f"  Restoring year summary page: {year}")

    opened = open_segment_page(page, url)

    if not opened:
        return False

    clicked = click_text(page, year)

    if not clicked:
        return False

    return True


def back_to_year_summary_or_restore(page, url, year):
    try:
        page.go_back(wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        current_tables = extract_tables(page)
        current_summary = find_month_summary_table(current_tables)
        current_months = get_months_from_summary_table(current_summary)

        if current_months:
            return True

        print("  Back page does not contain month summary. Restoring...")
        return restore_year_summary_page(page, url, year)

    except Exception as error:
        print(f"  Back navigation failed: {error}")
        return restore_year_summary_page(page, url, year)


def extract_daily_rows_from_tables(all_tables):
    best_table_index = None
    best_rows = []

    for table_info in all_tables:
        table_index = table_info["table_index"]
        rows = table_info["rows"]

        if not rows:
            continue

        max_cols = max(len(row) for row in rows)

        padded_rows = [
            row + [""] * (max_cols - len(row))
            for row in rows
        ]

        daily_rows = []

        for row in padded_rows:
            parsed_date = None
            date_col_index = None

            for col_index, cell in enumerate(row):
                parsed = parse_daily_date(cell)

                if parsed is not None:
                    parsed_date = parsed
                    date_col_index = col_index
                    break

            if parsed_date is None:
                continue

            numeric_values = []

            for idx, value in enumerate(row):
                if idx == date_col_index:
                    continue

                number = clean_number(value)

                if number is not None:
                    numeric_values.append(number)

            if not numeric_values:
                continue

            daily_rows.append(
                {
                    "date": parsed_date.date(),
                    "month_label": parsed_date.strftime("%b-%Y"),
                    "table_index": table_index,
                    "date_col_index": date_col_index,
                    "raw_row": row,
                }
            )

        if len(daily_rows) > len(best_rows):
            best_rows = daily_rows
            best_table_index = table_index

    return best_table_index, best_rows


def get_daily_dataframe(source_name, segment, year, month_label, daily_rows):
    if not daily_rows:
        return pd.DataFrame()

    max_cols = max(len(item["raw_row"]) for item in daily_rows)

    output_rows = []

    for item in daily_rows:
        if item["month_label"] != month_label:
            continue

        row_dict = {
            "source_name": source_name,
            "segment": segment,
            "clicked_year": year,
            "month_label": month_label,
            "date": item["date"],
        }

        raw_row = item["raw_row"] + [""] * (max_cols - len(item["raw_row"]))

        for index, value in enumerate(raw_row):
            row_dict[f"col_{index + 1}"] = value

        output_rows.append(row_dict)

    return pd.DataFrame(output_rows)


def make_raw_row(
    source_name,
    segment,
    instrument,
    clicked_year,
    month_label,
    date,
    daily_turnover,
    daily_volume,
    active_trading_days,
    source_level,
    raw_values,
):
    row = {
        "source_name": source_name,
        "segment": segment,
        "instrument": instrument,
        "clicked_year": clicked_year,
        "month_label": month_label,
        "date": date,
        "daily_turnover": daily_turnover,
        "daily_volume": daily_volume,
        "active_trading_days": active_trading_days,
        "source_level": source_level,
    }

    for index, value in enumerate(raw_values):
        row[f"raw_col_{index + 1}"] = value

    return row


def make_missing_daily_marker(source_name, segment, clicked_year, month_label, reason):
    return {
        "source_name": source_name,
        "segment": segment,
        "instrument": "NA",
        "clicked_year": clicked_year,
        "month_label": month_label,
        "date": "",
        "daily_turnover": "",
        "daily_volume": "",
        "active_trading_days": "",
        "source_level": "missing_daily_table",
        "raw_col_1": reason,
    }


def normalize_capital_market_year(summary_table, clicked_year):
    main_rows = []
    raw_rows = []

    if summary_table is None:
        return main_rows, raw_rows

    for raw_row in summary_table["rows"]:
        if len(raw_row) < 9:
            continue

        month_label = normalize_month_label(raw_row[0])

        if month_label is None:
            continue

        trading_days = clean_number(raw_row[4])
        traded_quantity_lakhs = clean_number(raw_row[7])
        monthly_turnover_crores = clean_number(raw_row[8])

        if trading_days is None or trading_days == 0:
            continue

        if traded_quantity_lakhs is None or monthly_turnover_crores is None:
            continue

        main_rows.append(
            {
                "segment": "Capital Market",
                "instrument": "NA",
                "month_label": month_label,
                "monthly_turnover": monthly_turnover_crores,
                "monthly_volume": traded_quantity_lakhs,
                "active_trading_days": trading_days,
                "turnover": monthly_turnover_crores / trading_days,
                "volume": traded_quantity_lakhs / trading_days,
                "source_logic": "capital_market_year_table_trading_days",
            }
        )

        raw_rows.append(
            make_raw_row(
                source_name="capital_market",
                segment="Capital Market",
                instrument="NA",
                clicked_year=clicked_year,
                month_label=month_label,
                date="",
                daily_turnover=monthly_turnover_crores,
                daily_volume=traded_quantity_lakhs,
                active_trading_days=trading_days,
                source_level="capital_market_year_summary_table",
                raw_values=raw_row,
            )
        )

    return main_rows, raw_rows


def build_equity_raw_rows(month_label, clicked_year, daily_df):
    raw_rows = []
    active_days = daily_df["date"].nunique()

    for _, row in daily_df.iterrows():
        raw_values = [
            row[column]
            for column in daily_df.columns
            if column.startswith("col_")
        ]

        raw_rows.append(
            make_raw_row(
                source_name="equity_derivatives",
                segment="Equity Derivatives",
                instrument="Futures",
                clicked_year=clicked_year,
                month_label=month_label,
                date=row["date"],
                daily_turnover=clean_number(row.get("col_3")),
                daily_volume=clean_number(row.get("col_2")),
                active_trading_days=active_days,
                source_level="daily_table",
                raw_values=raw_values,
            )
        )

        raw_rows.append(
            make_raw_row(
                source_name="equity_derivatives",
                segment="Equity Derivatives",
                instrument="Options",
                clicked_year=clicked_year,
                month_label=month_label,
                date=row["date"],
                daily_turnover=clean_number(row.get("col_10")),
                daily_volume=clean_number(row.get("col_8")),
                active_trading_days=active_days,
                source_level="daily_table",
                raw_values=raw_values,
            )
        )

    return raw_rows


def build_currency_raw_rows(month_label, clicked_year, daily_df):
    raw_rows = []
    active_days = daily_df["date"].nunique()

    for _, row in daily_df.iterrows():
        raw_values = [
            row[column]
            for column in daily_df.columns
            if column.startswith("col_")
        ]

        raw_rows.append(
            make_raw_row(
                source_name="currency_derivatives",
                segment="Currency Derivatives",
                instrument="Futures",
                clicked_year=clicked_year,
                month_label=month_label,
                date=row["date"],
                daily_turnover=clean_number(row.get("col_3")),
                daily_volume=clean_number(row.get("col_2")),
                active_trading_days=active_days,
                source_level="daily_table",
                raw_values=raw_values,
            )
        )

        raw_rows.append(
            make_raw_row(
                source_name="currency_derivatives",
                segment="Currency Derivatives",
                instrument="Options",
                clicked_year=clicked_year,
                month_label=month_label,
                date=row["date"],
                daily_turnover=clean_number(row.get("col_6")),
                daily_volume=clean_number(row.get("col_4")),
                active_trading_days=active_days,
                source_level="daily_table",
                raw_values=raw_values,
            )
        )

    return raw_rows


def build_ird_raw_rows(month_label, clicked_year, daily_df):
    raw_rows = []
    active_days = daily_df["date"].nunique()

    for _, row in daily_df.iterrows():
        raw_values = [
            row[column]
            for column in daily_df.columns
            if column.startswith("col_")
        ]

        raw_rows.append(
            make_raw_row(
                source_name="interest_rate_derivatives",
                segment="Interest Rate Derivatives",
                instrument="NA",
                clicked_year=clicked_year,
                month_label=month_label,
                date=row["date"],
                daily_turnover=clean_number(row.get("col_3")),
                daily_volume=clean_number(row.get("col_2")),
                active_trading_days=active_days,
                source_level="daily_table",
                raw_values=raw_values,
            )
        )

    return raw_rows


def aggregate_equity_derivatives(month_label, daily_df):
    rows = []

    if daily_df.empty:
        return rows

    active_days = daily_df["date"].nunique()

    if active_days == 0:
        return rows

    futures_volume = daily_df["col_2"].apply(clean_number).sum()
    futures_turnover = daily_df["col_3"].apply(clean_number).sum()

    options_volume = daily_df["col_8"].apply(clean_number).sum()
    options_turnover = daily_df["col_10"].apply(clean_number).sum()

    rows.append(
        {
            "segment": "Equity Derivatives",
            "instrument": "Futures",
            "month_label": month_label,
            "monthly_turnover": futures_turnover,
            "monthly_volume": futures_volume,
            "active_trading_days": active_days,
            "turnover": futures_turnover / active_days,
            "volume": futures_volume / active_days,
            "source_logic": "daily_table_sum_divide_by_active_days",
        }
    )

    rows.append(
        {
            "segment": "Equity Derivatives",
            "instrument": "Options",
            "month_label": month_label,
            "monthly_turnover": options_turnover,
            "monthly_volume": options_volume,
            "active_trading_days": active_days,
            "turnover": options_turnover / active_days,
            "volume": options_volume / active_days,
            "source_logic": "daily_table_sum_divide_by_active_days",
        }
    )

    return rows


def aggregate_currency_derivatives(month_label, daily_df):
    rows = []

    if daily_df.empty:
        return rows

    active_days = daily_df["date"].nunique()

    if active_days == 0:
        return rows

    futures_volume = daily_df["col_2"].apply(clean_number).sum()
    futures_turnover = daily_df["col_3"].apply(clean_number).sum()

    options_volume = daily_df["col_4"].apply(clean_number).sum()
    options_turnover = daily_df["col_6"].apply(clean_number).sum()

    rows.append(
        {
            "segment": "Currency Derivatives",
            "instrument": "Futures",
            "month_label": month_label,
            "monthly_turnover": futures_turnover,
            "monthly_volume": futures_volume,
            "active_trading_days": active_days,
            "turnover": futures_turnover / active_days,
            "volume": futures_volume / active_days,
            "source_logic": "daily_table_sum_divide_by_active_days",
        }
    )

    rows.append(
        {
            "segment": "Currency Derivatives",
            "instrument": "Options",
            "month_label": month_label,
            "monthly_turnover": options_turnover,
            "monthly_volume": options_volume,
            "active_trading_days": active_days,
            "turnover": options_turnover / active_days,
            "volume": options_volume / active_days,
            "source_logic": "daily_table_sum_divide_by_active_days",
        }
    )

    return rows


def aggregate_interest_rate_derivatives(month_label, daily_df):
    rows = []

    if daily_df.empty:
        return rows

    active_days = daily_df["date"].nunique()

    if active_days == 0:
        return rows

    monthly_volume = daily_df["col_2"].apply(clean_number).sum()
    monthly_turnover = daily_df["col_3"].apply(clean_number).sum()

    rows.append(
        {
            "segment": "Interest Rate Derivatives",
            "instrument": "NA",
            "month_label": month_label,
            "monthly_turnover": monthly_turnover,
            "monthly_volume": monthly_volume,
            "active_trading_days": active_days,
            "turnover": monthly_turnover / active_days,
            "volume": monthly_volume / active_days,
            "source_logic": "daily_table_sum_divide_by_active_days",
        }
    )

    return rows


def add_dashboard_fields(df):
    df = df.copy()

    if df.empty:
        return df

    df["month_date"] = df["month_label"].apply(month_label_to_date)
    df = df.dropna(subset=["month_date"])

    df["instrument"] = (
        df["instrument"]
        .replace("", "NA")
        .fillna("NA")
        .astype(str)
        .str.strip()
    )

    df["segment"] = df["segment"].astype(str).str.strip()

    df["year"] = df["month_date"].dt.year.astype(int)
    df["calendar_quarter"] = df["month_date"].apply(get_calendar_quarter)
    df["financial_year"] = df["month_date"].apply(get_financial_year)
    df["financial_quarter"] = df["month_date"].apply(get_financial_quarter)

    numeric_columns = [
        "monthly_turnover",
        "monthly_volume",
        "active_trading_days",
        "turnover",
        "volume",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.sort_values(["segment", "instrument", "month_date"])

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
            "monthly_turnover",
            "monthly_volume",
            "active_trading_days",
            "turnover",
            "volume",
            "mom_turnover_change",
            "mom_volume_change",
            "source_logic",
        ]
    ]

    return df


def remove_incomplete_latest_month(df):
    df = df.copy()

    if df.empty:
        return df

    latest_month_date = df["month_date"].max()
    latest_df = df[df["month_date"] == latest_month_date].copy()

    available_groups = set(
        zip(
            latest_df["segment"].astype(str),
            latest_df["instrument"].astype(str),
        )
    )

    missing_groups = EXPECTED_SEGMENT_INSTRUMENT_GROUPS - available_groups

    if missing_groups:
        latest_month_label = latest_df["month_label"].iloc[0]

        print(
            f"Removing incomplete latest month: {latest_month_label}. "
            f"Missing groups: {sorted(missing_groups)}"
        )

        df = df[df["month_date"] != latest_month_date].copy()

    return df


def filter_raw_to_main(raw_df, main_df):
    if raw_df.empty or main_df.empty:
        return raw_df

    valid_main_keys = set(
        zip(
            main_df["segment"].astype(str),
            main_df["instrument"].astype(str),
            main_df["month_label"].astype(str),
        )
    )

    raw_df = raw_df.copy()
    raw_df["segment"] = raw_df["segment"].astype(str)
    raw_df["instrument"] = raw_df["instrument"].astype(str)
    raw_df["month_label"] = raw_df["month_label"].astype(str)

    raw_df = raw_df[
        raw_df.apply(
            lambda row: (
                row["segment"],
                row["instrument"],
                row["month_label"],
            )
            in valid_main_keys,
            axis=1,
        )
    ].copy()

    return raw_df


def save_progress(main_rows, raw_rows, final_save=False):
    main_df = pd.DataFrame(main_rows)
    raw_df = pd.DataFrame(raw_rows)

    if main_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    main_df = add_dashboard_fields(main_df)

    main_df = main_df.drop_duplicates(
        subset=["segment", "instrument", "month_label"],
        keep="last",
    )

    if final_save:
        main_df = remove_incomplete_latest_month(main_df)

    if not raw_df.empty:
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

        if final_save:
            raw_df = filter_raw_to_main(raw_df, main_df)

    main_df.to_csv(MAIN_OUTPUT_FILE, index=False, encoding="utf-8-sig")
    raw_df.to_csv(RAW_OUTPUT_FILE, index=False, encoding="utf-8-sig")

    if final_save:
        print(f"Final save completed: {MAIN_OUTPUT_FILE}, {RAW_OUTPUT_FILE}")
    else:
        print(f"Progress saved: main={len(main_df)} rows, raw={len(raw_df)} rows")

    return main_df, raw_df


def scrape_capital_market(page, source_name, segment_name, url, years, main_rows, raw_rows):
    existing_main_keys = get_existing_main_keys(main_rows)
    existing_raw_keys = get_existing_raw_keys(raw_rows)

    for year in years:
        print(f"\nCapital Market | Year: {year}")

        opened = open_segment_page(page, url)

        if not opened:
            print("NSE page failed repeatedly. Saving progress and stopping safely.")
            save_progress(main_rows, raw_rows, final_save=False)
            raise RuntimeError(
                f"NSE connection failed repeatedly for Capital Market | {year}. "
                "Progress is saved. Wait 5-10 minutes and run again."
            )

        clicked = click_text(page, year)

        if not clicked:
            print(f"Could not click year: {year}")
            continue

        all_tables = extract_tables(page)
        summary_table = find_month_summary_table(all_tables)

        year_main_rows, year_raw_rows = normalize_capital_market_year(
            summary_table=summary_table,
            clicked_year=year,
        )

        added = 0

        for row in year_main_rows:
            key = (row["segment"], row["instrument"], row["month_label"])

            if key not in existing_main_keys:
                main_rows.append(row)
                existing_main_keys.add(key)
                added += 1

        for raw_row in year_raw_rows:
            raw_key = (
                str(raw_row.get("segment")),
                str(raw_row.get("instrument")),
                str(raw_row.get("month_label")),
                str(raw_row.get("clicked_year")),
                str(raw_row.get("source_level")),
                str(raw_row.get("date")),
            )

            if raw_key not in existing_raw_keys:
                raw_rows.append(raw_row)
                existing_raw_keys.add(raw_key)

        print(f"Capital Market rows added: {added}")
        save_progress(main_rows, raw_rows, final_save=False)

    return main_rows, raw_rows


def scrape_derivative_segment(page, source_name, segment_name, url, years, main_rows, raw_rows):
    for year in years:
        print(f"\n{segment_name} | Year: {year}")

        opened = open_segment_page(page, url)

        if not opened:
            print("NSE page failed repeatedly. Saving progress and stopping safely.")
            save_progress(main_rows, raw_rows, final_save=False)
            raise RuntimeError(
                f"NSE connection failed repeatedly for {segment_name} | {year}. "
                "Progress is saved. Wait 5-10 minutes and run again."
            )

        clicked = click_text(page, year)

        if not clicked:
            print(f"Could not click year: {year}")
            continue

        all_tables = extract_tables(page)
        summary_table = find_month_summary_table(all_tables)
        months = get_months_from_summary_table(summary_table)

        print(f"Months found: {months}")

        for month_label in months:
            existing_keys = get_existing_main_keys(main_rows)
            missing_daily_keys = get_existing_missing_daily_keys(raw_rows)

            if (segment_name, month_label) in missing_daily_keys:
                print(f"  Skipping known missing daily table: {segment_name} | {month_label}")
                continue

            if source_name in ["equity_derivatives", "currency_derivatives"]:
                futures_key = (segment_name, "Futures", month_label)
                options_key = (segment_name, "Options", month_label)

                if futures_key in existing_keys and options_key in existing_keys:
                    print(f"  Skipping already scraped: {segment_name} | {month_label}")
                    continue

            elif source_name == "interest_rate_derivatives":
                key = (segment_name, "NA", month_label)

                if key in existing_keys:
                    print(f"  Skipping already scraped: {segment_name} | {month_label}")
                    continue

            print(f"  Processing month: {month_label}")

            clicked_month = click_month_from_summary_table(page, month_label)

            if not clicked_month:
                print(f"  Could not click month from current year table: {month_label}")
                print("  Marking this month as missing_daily_table and continuing.")

                raw_rows.append(
                    make_missing_daily_marker(
                        source_name=source_name,
                        segment=segment_name,
                        clicked_year=year,
                        month_label=month_label,
                        reason="Month click failed from year summary table",
                    )
                )

                save_progress(main_rows, raw_rows, final_save=False)

                restored = restore_year_summary_page(page, url, year)

                if not restored:
                    print("  Could not restore year page after month click failure.")
                    print("  Progress is saved. Stop safely; run again later.")
                    raise RuntimeError(
                        f"NSE connection failed while restoring after month click failure: "
                        f"{segment_name} | {year} | {month_label}. "
                        "Progress is saved. Run again."
                    )

                continue

            all_month_tables = extract_tables(page)
            best_table_index, daily_rows = extract_daily_rows_from_tables(all_month_tables)

            if not daily_rows:
                print(f"  No daily rows found for {month_label}")
                print("  Marking this month as missing_daily_table and moving ahead.")

                raw_rows.append(
                    make_missing_daily_marker(
                        source_name=source_name,
                        segment=segment_name,
                        clicked_year=year,
                        month_label=month_label,
                        reason="No daily date rows found after clicking month",
                    )
                )

                save_progress(main_rows, raw_rows, final_save=False)

                restored = back_to_year_summary_or_restore(page, url, year)

                if not restored:
                    print("  Could not restore year page after missing daily rows.")
                    print("  Progress is saved. Stop safely; run again later.")
                    raise RuntimeError(
                        f"NSE connection failed while restoring after missing daily table: "
                        f"{segment_name} | {year} | {month_label}. "
                        "Progress is saved. Run again."
                    )

                continue

            daily_df = get_daily_dataframe(
                source_name=source_name,
                segment=segment_name,
                year=year,
                month_label=month_label,
                daily_rows=daily_rows,
            )

            if daily_df.empty:
                print(f"  Daily dataframe empty for {month_label}")
                print("  Marking this month as missing_daily_table and moving ahead.")

                raw_rows.append(
                    make_missing_daily_marker(
                        source_name=source_name,
                        segment=segment_name,
                        clicked_year=year,
                        month_label=month_label,
                        reason="Daily dataframe empty after extracting daily rows",
                    )
                )

                save_progress(main_rows, raw_rows, final_save=False)

                restored = back_to_year_summary_or_restore(page, url, year)

                if not restored:
                    print("  Could not restore year page after empty dataframe.")
                    print("  Progress is saved. Stop safely; run again later.")
                    raise RuntimeError(
                        f"NSE connection failed while restoring after empty dataframe: "
                        f"{segment_name} | {year} | {month_label}. "
                        "Progress is saved. Run again."
                    )

                continue

            print(
                f"  Daily rows: {len(daily_df)} | "
                f"active days: {daily_df['date'].nunique()} | "
                f"table index: {best_table_index}"
            )

            if source_name == "equity_derivatives":
                rows = aggregate_equity_derivatives(month_label, daily_df)
                evidence_rows = build_equity_raw_rows(month_label, year, daily_df)

            elif source_name == "currency_derivatives":
                rows = aggregate_currency_derivatives(month_label, daily_df)
                evidence_rows = build_currency_raw_rows(month_label, year, daily_df)

            elif source_name == "interest_rate_derivatives":
                rows = aggregate_interest_rate_derivatives(month_label, daily_df)
                evidence_rows = build_ird_raw_rows(month_label, year, daily_df)

            else:
                rows = []
                evidence_rows = []

            main_rows.extend(rows)
            raw_rows.extend(evidence_rows)

            save_progress(main_rows, raw_rows, final_save=False)

            restored = back_to_year_summary_or_restore(page, url, year)

            if not restored:
                print("NSE page failed repeatedly. Saving progress and stopping safely.")
                save_progress(main_rows, raw_rows, final_save=False)
                raise RuntimeError(
                    f"NSE connection failed after scraping {segment_name} | {year} | {month_label}. "
                    "Progress is saved. Wait 5-10 minutes and run again."
                )

    return main_rows, raw_rows


def scrape_all_segments():
    existing_main_df, existing_raw_df = load_existing_outputs()

    main_rows = dataframe_to_source_main_rows(existing_main_df)
    raw_rows = dataframe_to_raw_rows(existing_raw_df)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
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

            print("\n" + "=" * 120)
            print(f"SCRAPING SEGMENT: {segment_name}")
            print("=" * 120)

            opened = open_segment_page(page, url)

            if not opened:
                print("NSE page failed repeatedly. Saving progress and stopping safely.")
                save_progress(main_rows, raw_rows, final_save=False)
                raise RuntimeError(
                    f"NSE connection failed repeatedly for segment: {segment_name}. "
                    "Progress is saved. Wait 5-10 minutes and run again."
                )

            years = get_available_financial_years(page)

            if MAX_YEARS_PER_SEGMENT is not None:
                years = years[:MAX_YEARS_PER_SEGMENT]

            print(f"Years selected: {years}")

            if source_name == "capital_market":
                main_rows, raw_rows = scrape_capital_market(
                    page=page,
                    source_name=source_name,
                    segment_name=segment_name,
                    url=url,
                    years=years,
                    main_rows=main_rows,
                    raw_rows=raw_rows,
                )

            else:
                main_rows, raw_rows = scrape_derivative_segment(
                    page=page,
                    source_name=source_name,
                    segment_name=segment_name,
                    url=url,
                    years=years,
                    main_rows=main_rows,
                    raw_rows=raw_rows,
                )

        browser.close()

    final_main_df, final_raw_df = save_progress(main_rows, raw_rows, final_save=True)

    print("\n" + "=" * 120)
    print("SCRAPING COMPLETED")
    print(f"Main output saved: {MAIN_OUTPUT_FILE}")
    print(f"Raw output saved: {RAW_OUTPUT_FILE}")

    print("\nMain rows by segment/instrument:")
    print(
        final_main_df.groupby(["segment", "instrument"])
        .size()
        .reset_index(name="rows")
    )

    print("\nRaw rows by segment/instrument:")
    if not final_raw_df.empty:
        print(
            final_raw_df.groupby(["segment", "instrument"])
            .size()
            .reset_index(name="rows")
        )
    else:
        print("Raw dataframe is empty.")

    print("\nMain date range:")
    print(
        final_main_df.groupby(["segment", "instrument"])
        .agg(
            start_month=("month_date", "min"),
            end_month=("month_date", "max"),
        )
        .reset_index()
    )

    print("\nMain preview:")
    print(final_main_df.tail(30))

    return final_main_df, final_raw_df


if __name__ == "__main__":
    scrape_all_segments()