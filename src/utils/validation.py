import pandas as pd


REQUIRED_COLUMNS = [
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


EXPECTED_SEGMENT_INSTRUMENTS = {
    ("Capital Market", "NA"),
    ("Equity Derivatives", "Futures"),
    ("Equity Derivatives", "Options"),
    ("Currency Derivatives", "Futures"),
    ("Currency Derivatives", "Options"),
    ("Interest Rate Derivatives", "NA"),
}


EXPECTED_FINANCIAL_QUARTER_MONTHS = {
    "Q1": ["Apr", "May", "Jun"],
    "Q2": ["Jul", "Aug", "Sep"],
    "Q3": ["Oct", "Nov", "Dec"],
    "Q4": ["Jan", "Feb", "Mar"],
}


def validate_required_columns(df: pd.DataFrame):
    missing_columns = [
        col for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )


def validate_row_count(df: pd.DataFrame, expected_rows: int = 240):
    actual_rows = len(df)

    if actual_rows != expected_rows:
        raise ValueError(
            f"Row count mismatch. Expected {expected_rows}, got {actual_rows}"
        )


def validate_segment_instrument_pairs(df: pd.DataFrame):
    actual_pairs = set(
        zip(
            df["segment"].astype(str),
            df["instrument"].astype(str)
        )
    )

    missing_pairs = EXPECTED_SEGMENT_INSTRUMENTS - actual_pairs
    extra_pairs = actual_pairs - EXPECTED_SEGMENT_INSTRUMENTS

    if missing_pairs:
        raise ValueError(
            f"Missing segment-instrument pairs: {missing_pairs}"
        )

    if extra_pairs:
        raise ValueError(
            f"Unexpected segment-instrument pairs found: {extra_pairs}"
        )


def validate_missing_values(df: pd.DataFrame):
    missing_turnover = df["turnover"].isna().sum()
    missing_volume = df["volume"].isna().sum()
    missing_month_date = df["month_date"].isna().sum()
    missing_financial_year = df["financial_year"].isna().sum()
    missing_financial_quarter = df["financial_quarter"].isna().sum()

    issues = []

    if missing_turnover > 0:
        issues.append(f"Missing turnover values: {missing_turnover}")

    if missing_volume > 0:
        issues.append(f"Missing volume values: {missing_volume}")

    if missing_month_date > 0:
        issues.append(f"Missing month_date values: {missing_month_date}")

    if missing_financial_year > 0:
        issues.append(f"Missing financial_year values: {missing_financial_year}")

    if missing_financial_quarter > 0:
        issues.append(
            f"Missing financial_quarter values: {missing_financial_quarter}"
        )

    if issues:
        raise ValueError(" | ".join(issues))


def validate_duplicates(df: pd.DataFrame):
    duplicate_count = df.duplicated(
        subset=[
            "segment",
            "instrument",
            "month_label",
            "financial_year",
            "financial_quarter"
        ]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            f"Duplicate rows found: {duplicate_count}"
        )


def validate_financial_quarter_mapping(df: pd.DataFrame):
    temp_df = df.copy()
    temp_df["month_date"] = pd.to_datetime(
        temp_df["month_date"],
        errors="coerce"
    )
    temp_df["month_name"] = temp_df["month_date"].dt.strftime("%b")

    invalid_rows = []

    for _, row in temp_df.iterrows():
        financial_quarter = row["financial_quarter"]
        month_name = row["month_name"]

        expected_months = EXPECTED_FINANCIAL_QUARTER_MONTHS.get(
            financial_quarter,
            []
        )

        if month_name not in expected_months:
            invalid_rows.append(
                {
                    "month_label": row["month_label"],
                    "financial_year": row["financial_year"],
                    "financial_quarter": financial_quarter,
                    "month_name": month_name,
                }
            )

    if invalid_rows:
        raise ValueError(
            f"Invalid financial quarter mapping found: {invalid_rows[:5]}"
        )


def validate_clean_data(df: pd.DataFrame, expected_rows: int = 240):
    """
    Main validation function for cleaned NSE business growth data.
    """

    if df.empty:
        raise ValueError("Clean dataframe is empty.")

    validate_required_columns(df)
    validate_row_count(df, expected_rows=expected_rows)
    validate_segment_instrument_pairs(df)
    validate_missing_values(df)
    validate_duplicates(df)
    validate_financial_quarter_mapping(df)

    print("Validation passed successfully!")
    print(f"Validated rows: {len(df)}")
    print(f"Segments found: {df['segment'].nunique()}")
    print(f"Financial years found: {df['financial_year'].nunique()}")

    return True