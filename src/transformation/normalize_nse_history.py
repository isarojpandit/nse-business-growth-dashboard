from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw/nse_scraped")
PROCESSED_DIR = Path("data/processed")

OUTPUT_FILE = PROCESSED_DIR / "clean_nse_business_growth_from_nse.csv"


def clean_number(value):
    if value is None:
        return None

    if pd.isna(value):
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
    if value is None:
        return None

    if pd.isna(value):
        return None

    value = str(value).replace("\n", "").strip()

    for fmt in ["%b-%Y", "%b-%y"]:
        parsed = pd.to_datetime(value, format=fmt, errors="coerce")

        if not pd.isna(parsed):
            return parsed.strftime("%b-%Y")

    return None


def month_label_to_date(month_label):
    if month_label is None:
        return None

    return pd.to_datetime(
        month_label,
        format="%b-%Y",
        errors="coerce"
    )


def is_month_row(value):
    month_label = normalize_month_label(value)
    return month_label is not None


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


def get_latest_raw_history_file():
    files = sorted(
        RAW_DIR.glob("all_segments_monthly_raw_history_*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True
    )

    if not files:
        raise FileNotFoundError(
            "No raw history file found in data/raw/nse_scraped. "
            "Expected file pattern: all_segments_monthly_raw_history_*.csv"
        )

    return files[0]


def get_value(row, column_name):
    if column_name not in row.index:
        return None

    value = row[column_name]

    if pd.isna(value):
        return None

    return value


def build_trading_days_map(raw_df):
    """
    Capital Market monthly table contains No. of Trading Days.
    We use this as common monthly trading days reference for all segments.
    """

    cm_df = raw_df[raw_df["source_name"] == "capital_market"].copy()

    trading_days_map = {}

    for _, row in cm_df.iterrows():
        month_label = normalize_month_label(get_value(row, "col_1"))

        if month_label is None:
            continue

        trading_days = clean_number(get_value(row, "col_5"))

        if trading_days is None or trading_days == 0:
            continue

        trading_days_map[month_label] = trading_days

    return trading_days_map


def normalize_capital_market(raw_df, trading_days_map):
    cm_df = raw_df[raw_df["source_name"] == "capital_market"].copy()

    rows = []

    for _, row in cm_df.iterrows():
        month_label = normalize_month_label(get_value(row, "col_1"))

        if month_label is None:
            continue

        trading_days = trading_days_map.get(month_label)

        if trading_days is None or trading_days == 0:
            continue

        traded_quantity_lakhs = clean_number(get_value(row, "col_8"))
        monthly_turnover_crores = clean_number(get_value(row, "col_9"))

        if traded_quantity_lakhs is None or monthly_turnover_crores is None:
            continue

        rows.append(
            {
                "segment": "Capital Market",
                "instrument": "NA",
                "month_label": month_label,
                "turnover": monthly_turnover_crores / trading_days,
                "volume": traded_quantity_lakhs / trading_days,
            }
        )

    return rows


def normalize_equity_derivatives(raw_df, trading_days_map):
    eq_df = raw_df[raw_df["source_name"] == "equity_derivatives"].copy()

    rows = []

    for _, row in eq_df.iterrows():
        month_label = normalize_month_label(get_value(row, "col_1"))

        if month_label is None:
            continue

        trading_days = trading_days_map.get(month_label)

        if trading_days is None or trading_days == 0:
            continue

        # NSE Equity Derivatives monthly table mapping:
        # col_2 = Index Futures No. of Contracts
        # col_3 = Index Futures Turnover
        # col_8 = Index Options No. of Contracts
        # col_9 = Index Options Premium Turnover

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

    return rows


def normalize_currency_derivatives(raw_df, trading_days_map):
    cd_df = raw_df[raw_df["source_name"] == "currency_derivatives"].copy()

    rows = []

    for _, row in cd_df.iterrows():
        month_label = normalize_month_label(get_value(row, "col_1"))

        if month_label is None:
            continue

        trading_days = trading_days_map.get(month_label)

        if trading_days is None or trading_days == 0:
            continue

        # NSE Currency Derivatives monthly table mapping:
        # col_2 = Currency Futures No. of Contracts
        # col_3 = Currency Futures Turnover
        # col_4 = Currency Options No. of Contracts
        # col_6 = Currency Options Premium Turnover

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

    return rows


def normalize_interest_rate_derivatives(raw_df, trading_days_map):
    ird_df = raw_df[raw_df["source_name"] == "interest_rate_derivatives"].copy()

    rows = []

    for _, row in ird_df.iterrows():
        month_label = normalize_month_label(get_value(row, "col_1"))

        if month_label is None:
            continue

        trading_days = trading_days_map.get(month_label)

        if trading_days is None or trading_days == 0:
            continue

        # NSE Interest Rate Derivatives monthly table mapping:
        # col_2 = Volume Contracts
        # col_3 = Turnover

        volume_contracts = clean_number(get_value(row, "col_2"))
        monthly_turnover_crores = clean_number(get_value(row, "col_3"))

        if volume_contracts is None or monthly_turnover_crores is None:
            continue

        rows.append(
            {
                "segment": "Interest Rate Derivatives",
                "instrument": "NA",
                "month_label": month_label,
                "turnover": monthly_turnover_crores / trading_days,
                "volume": volume_contracts / trading_days,
            }
        )

    return rows


def add_dashboard_fields(df):
    df = df.copy()

    df["month_date"] = df["month_label"].apply(month_label_to_date)
    df = df.dropna(subset=["month_date"])

    df["year"] = df["month_date"].dt.year.astype(int)
    df["calendar_quarter"] = df["month_date"].apply(get_calendar_quarter)
    df["financial_year"] = df["month_date"].apply(get_financial_year)
    df["financial_quarter"] = df["month_date"].apply(get_financial_quarter)

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


def normalize_nse_history(input_file=None):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    if input_file is None:
        input_file = get_latest_raw_history_file()
    else:
        input_file = Path(input_file)

    print(f"Reading raw history file: {input_file}")

    raw_df = pd.read_csv(input_file)

    print(f"Raw rows: {len(raw_df)}")
    print(f"Raw columns: {len(raw_df.columns)}")

    print("\nRaw rows by source:")
    print(raw_df["source_name"].value_counts())

    trading_days_map = build_trading_days_map(raw_df)

    print(f"\nTrading days mapped months: {len(trading_days_map)}")

    all_rows = []

    all_rows.extend(
        normalize_capital_market(
            raw_df,
            trading_days_map,
        )
    )

    all_rows.extend(
        normalize_equity_derivatives(
            raw_df,
            trading_days_map,
        )
    )

    all_rows.extend(
        normalize_currency_derivatives(
            raw_df,
            trading_days_map,
        )
    )

    all_rows.extend(
        normalize_interest_rate_derivatives(
            raw_df,
            trading_days_map,
        )
    )

    normalized_df = pd.DataFrame(all_rows)

    if normalized_df.empty:
        raise ValueError("Normalization failed. No rows produced.")

    normalized_df = add_dashboard_fields(normalized_df)

    duplicate_count = normalized_df.duplicated(
        subset=[
            "segment",
            "instrument",
            "month_label",
        ]
    ).sum()

    print(f"\nDuplicate segment-instrument-month rows: {duplicate_count}")

    normalized_df = normalized_df.drop_duplicates(
        subset=[
            "segment",
            "instrument",
            "month_label",
        ],
        keep="last"
    )

    normalized_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nNormalized rows by segment/instrument:")
    print(
        normalized_df
        .groupby(["segment", "instrument"])
        .size()
        .reset_index(name="rows")
    )

    print("\nFinancial year range:")
    print(
        normalized_df
        .groupby(["segment", "instrument"])
        .agg(
            start_month=("month_date", "min"),
            end_month=("month_date", "max")
        )
        .reset_index()
    )

    print("\nNormalized preview:")
    print(normalized_df.head(30))

    print(f"\nSaved normalized NSE history to: {OUTPUT_FILE}")

    return normalized_df


if __name__ == "__main__":
    normalize_nse_history()