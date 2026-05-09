import pandas as pd


def fix_month_label(value):
    """
    Fix month labels like:
    - Jan-2023
    - Excel serial number like 45809
    """

    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        try:
            date_value = pd.to_datetime(value, unit="D", origin="1899-12-30")
            return date_value.strftime("%b-%Y")
        except Exception:
            return str(value)

    if isinstance(value, pd.Timestamp):
        return value.strftime("%b-%Y")

    value = str(value).strip()

    try:
        date_value = pd.to_datetime(value)
        return date_value.strftime("%b-%Y")
    except Exception:
        return value


def build_month_label(months_value, year_value, fallback_month_value=None):
    """
    Build reliable month label using Months + Year.

    Example:
    Months = Oct
    Year = 2025
    Output = Oct-2025

    We prefer Months + Year because Excel's Month column may contain wrong labels
    or Excel serial numbers.
    """

    if not pd.isna(months_value) and not pd.isna(year_value):
        try:
            month_text = str(months_value).strip()
            year_int = int(float(year_value))

            date_value = pd.to_datetime(
                f"{month_text}-{year_int}",
                format="%b-%Y",
                errors="coerce"
            )

            if pd.isna(date_value):
                date_value = pd.to_datetime(
                    f"{month_text} {year_int}",
                    errors="coerce"
                )

            if not pd.isna(date_value):
                return date_value.strftime("%b-%Y")

        except Exception:
            pass

    return fix_month_label(fallback_month_value)


def month_label_to_date(month_label):
    """
    Convert Jan-2023 to 2023-01-01
    """

    if pd.isna(month_label) or month_label is None:
        return None

    try:
        return pd.to_datetime(month_label, format="%b-%Y")
    except Exception:
        try:
            return pd.to_datetime(month_label)
        except Exception:
            return None


def get_financial_year(month_date):
    """
    Indian Financial Year:
    Apr-Mar

    Apr-2023 to Mar-2024 = FY 2023-24
    """

    if pd.isna(month_date) or month_date is None:
        return None

    year = month_date.year
    month = month_date.month

    if month >= 4:
        return f"FY {year}-{str(year + 1)[-2:]}"
    else:
        return f"FY {year - 1}-{str(year)[-2:]}"


def get_financial_quarter(month_date):
    """
    Indian Financial Quarter:
    Q1 = Apr, May, Jun
    Q2 = Jul, Aug, Sep
    Q3 = Oct, Nov, Dec
    Q4 = Jan, Feb, Mar
    """

    if pd.isna(month_date) or month_date is None:
        return None

    month = month_date.month

    if month in [4, 5, 6]:
        return "Q1"
    elif month in [7, 8, 9]:
        return "Q2"
    elif month in [10, 11, 12]:
        return "Q3"
    elif month in [1, 2, 3]:
        return "Q4"

    return None


def make_clean_row(
    segment,
    instrument,
    year,
    month_label,
    month_date,
    quarter,
    turnover,
    volume,
    mom_turnover_change,
    mom_volume_change
):
    """
    Common row format for database.
    """

    financial_year = get_financial_year(month_date)
    financial_quarter = get_financial_quarter(month_date)

    return {
        "segment": segment,
        "instrument": instrument,
        "year": year,
        "month_label": month_label,
        "month_date": month_date.date() if month_date is not None else None,
        "calendar_quarter": quarter,
        "financial_year": financial_year,
        "financial_quarter": financial_quarter,
        "turnover": turnover,
        "volume": volume,
        "mom_turnover_change": mom_turnover_change,
        "mom_volume_change": mom_volume_change,
    }


def clean_table_sheet(df):
    """
    Convert Excel wide format into dashboard-friendly long format.

    Output columns:
    segment, instrument, year, month_label, month_date,
    calendar_quarter, financial_year, financial_quarter,
    turnover, volume, mom_turnover_change, mom_volume_change
    """

    clean_rows = []

    for _, row in df.iterrows():
        segment = row.get("Segments")
        year = row.get("Year")
        months_value = row.get("Months")
        fallback_month_value = row.get("Month")
        quarter = row.get("Qtr")

        month_label = build_month_label(
            months_value=months_value,
            year_value=year,
            fallback_month_value=fallback_month_value
        )

        month_date = month_label_to_date(month_label)

        if pd.isna(segment) or month_label is None:
            continue

        segment = str(segment).strip()

        if segment == "Equity Derivatives":
            clean_rows.append(
                make_clean_row(
                    segment=segment,
                    instrument="Futures",
                    year=year,
                    month_label=month_label,
                    month_date=month_date,
                    quarter=quarter,
                    turnover=row.get("Monthly Average Turnover\nIndex Futures"),
                    volume=row.get("Average Volume\nIndex Futures"),
                    mom_turnover_change=row.get("MoM % change Turnover\nIndex Futures"),
                    mom_volume_change=row.get("MoM % change Volume\nIndex Futures"),
                )
            )

            clean_rows.append(
                make_clean_row(
                    segment=segment,
                    instrument="Options",
                    year=year,
                    month_label=month_label,
                    month_date=month_date,
                    quarter=quarter,
                    turnover=row.get("Monthly Average Turnover\nIndex Options"),
                    volume=row.get("Average Volume\nIndex Options"),
                    mom_turnover_change=row.get("MoM % change Turnover\nIndex Options"),
                    mom_volume_change=row.get("MoM % change Volume\nIndex Options"),
                )
            )

        elif segment == "Currency Derivatives":
            clean_rows.append(
                make_clean_row(
                    segment=segment,
                    instrument="Futures",
                    year=year,
                    month_label=month_label,
                    month_date=month_date,
                    quarter=quarter,
                    turnover=row.get("Monthly Average Turnover\nIndex Futures"),
                    volume=row.get("Average Volume\nIndex Futures"),
                    mom_turnover_change=row.get("MoM % change Turnover\nIndex Futures"),
                    mom_volume_change=row.get("MoM % change Volume\nIndex Futures"),
                )
            )

            clean_rows.append(
                make_clean_row(
                    segment=segment,
                    instrument="Options",
                    year=year,
                    month_label=month_label,
                    month_date=month_date,
                    quarter=quarter,
                    turnover=row.get("Monthly Average Turnover\nIndex Options"),
                    volume=row.get("Average Volume\nIndex Options"),
                    mom_turnover_change=row.get("MoM % change Turnover\nIndex Options"),
                    mom_volume_change=row.get("MoM % change Volume\nIndex Options"),
                )
            )

        elif segment == "Capital Market":
            clean_rows.append(
                make_clean_row(
                    segment=segment,
                    instrument="NA",
                    year=year,
                    month_label=month_label,
                    month_date=month_date,
                    quarter=quarter,
                    turnover=row.get("Monthly Average Turnover\nIndex Futures"),
                    volume=row.get("Average Volume\nIndex Futures"),
                    mom_turnover_change=row.get("MoM % change Turnover\nIndex Futures"),
                    mom_volume_change=row.get("MoM % change Volume\nIndex Futures"),
                )
            )

        elif segment == "Interest Rate Derivatives":
            clean_rows.append(
                make_clean_row(
                    segment=segment,
                    instrument="NA",
                    year=year,
                    month_label=month_label,
                    month_date=month_date,
                    quarter=quarter,
                    turnover=row.get("Monthly Average Turnover\nIndex Futures"),
                    volume=row.get("Average Volume\nIndex Futures"),
                    mom_turnover_change=row.get("MoM % change Turnover\nIndex Futures"),
                    mom_volume_change=row.get("MoM % change Volume\nIndex Futures"),
                )
            )

    clean_df = pd.DataFrame(clean_rows)

    if not clean_df.empty:
        clean_df["year"] = pd.to_numeric(clean_df["year"], errors="coerce")
        clean_df["turnover"] = pd.to_numeric(clean_df["turnover"], errors="coerce")
        clean_df["volume"] = pd.to_numeric(clean_df["volume"], errors="coerce")
        clean_df["mom_turnover_change"] = pd.to_numeric(
            clean_df["mom_turnover_change"],
            errors="coerce"
        )
        clean_df["mom_volume_change"] = pd.to_numeric(
            clean_df["mom_volume_change"],
            errors="coerce"
        )

    return clean_df