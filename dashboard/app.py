import sys
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from dashboard.components.charts import (
    create_monthly_turnover_chart,
    create_monthly_volume_chart,
    create_mom_turnover_chart,
    create_mom_volume_chart,
    create_quarterly_turnover_chart,
    create_quarterly_volume_chart,
    create_qoq_turnover_chart,
    create_qoq_volume_chart,
    create_comparative_chart,
)


DB_PATH = PROJECT_ROOT / "data" / "nse_business_growth.db"
CSV_PATH = PROJECT_ROOT / "data" / "processed" / "clean_nse_business_growth_from_nse.csv"
TABLE_NAME = "nse_business_growth"


MONTH_ORDER = {
    "Apr": 1,
    "May": 2,
    "Jun": 3,
    "Jul": 4,
    "Aug": 5,
    "Sep": 6,
    "Oct": 7,
    "Nov": 8,
    "Dec": 9,
    "Jan": 10,
    "Feb": 11,
    "Mar": 12,
}


st.set_page_config(
    page_title="NSE Business Growth Dashboard",
    page_icon="📈",
    layout="wide",
)


def inject_custom_css():
    st.markdown(
        """
        <style>
            .main {
                background-color: #f8fafc;
            }

            .block-container {
                padding-top: 3rem;
                padding-bottom: 2rem;
            }

            .dashboard-title {
                font-size: 2.45rem;
                font-weight: 900;
                line-height: 1.28;
                letter-spacing: 0.6px;
                margin-top: 0.6rem;
                margin-bottom: 0.4rem;
                padding-top: 0.2rem;
                padding-bottom: 0.25rem;
                overflow: visible;

                background: linear-gradient(
                    90deg,
                    #0f172a,
                    #2563eb,
                    #16a34a,
                    #0f172a
                );
                background-size: 300% 300%;
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                animation: titleGradient 5s ease infinite;
            }

            @keyframes titleGradient {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }

            .dashboard-subtitle {
                font-size: 1rem;
                color: #475569;
                margin-top: 0.2rem;
                margin-bottom: 1.5rem;
            }

            .metric-card {
                background: white;
                border-radius: 14px;
                padding: 18px 20px;
                box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08);
                border: 1px solid #e2e8f0;
                min-height: 112px;
            }

            .metric-label {
                font-size: 0.82rem;
                color: #64748b;
                font-weight: 700;
                margin-bottom: 8px;
            }

            .metric-value {
                font-size: 1.55rem;
                color: #0f172a;
                font-weight: 900;
                line-height: 1.2;
            }

            .delta-pill-positive {
                display: inline-block;
                margin-top: 10px;
                padding: 4px 10px;
                border-radius: 999px;
                background: #dcfce7;
                color: #166534;
                font-weight: 700;
                font-size: 0.82rem;
            }

            .delta-pill-negative {
                display: inline-block;
                margin-top: 10px;
                padding: 4px 10px;
                border-radius: 999px;
                background: #fee2e2;
                color: #991b1b;
                font-weight: 700;
                font-size: 0.82rem;
            }

            .delta-pill-neutral {
                display: inline-block;
                margin-top: 10px;
                padding: 4px 10px;
                border-radius: 999px;
                background: #e5e7eb;
                color: #374151;
                font-weight: 700;
                font-size: 0.82rem;
            }

            .note-box {
                background: #fff7ed;
                border: 1px solid #fed7aa;
                color: #9a3412;
                padding: 12px 14px;
                border-radius: 10px;
                font-size: 0.92rem;
                margin-bottom: 1rem;
            }

            .insight-box {
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                color: #1e40af;
                padding: 13px 15px;
                border-radius: 10px;
                font-size: 0.95rem;
                margin-top: 1rem;
                margin-bottom: 1rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_data_from_db():
    if not DB_PATH.exists():
        return pd.DataFrame()

    try:
        conn = sqlite3.connect(DB_PATH)

        query = f"""
        SELECT
            segment,
            instrument,
            year,
            month_label,
            month_date,
            calendar_quarter,
            financial_year,
            financial_quarter,
            turnover,
            volume,
            mom_turnover_change,
            mom_volume_change
        FROM {TABLE_NAME}
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        return df

    except Exception as error:
        st.warning(f"Could not load SQLite database: {error}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_data_from_csv():
    if not CSV_PATH.exists():
        return pd.DataFrame()

    return pd.read_csv(
        CSV_PATH,
        keep_default_na=False,
    )


def clean_loaded_data(df):
    if df.empty:
        return df

    df = df.copy()

    df["segment"] = df["segment"].astype(str).str.strip()

    df["instrument"] = (
        df["instrument"]
        .replace("", "NA")
        .fillna("NA")
        .astype(str)
        .str.strip()
    )

    df["month_label"] = df["month_label"].astype(str).str.strip()

    df["month_date"] = pd.to_datetime(
        df["month_date"],
        errors="coerce",
    )

    df = df.dropna(subset=["month_date"])

    numeric_columns = [
        "turnover",
        "volume",
        "mom_turnover_change",
        "mom_volume_change",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["year"] = pd.to_numeric(
        df["year"],
        errors="coerce",
    ).astype("Int64")

    df["month_name"] = df["month_date"].dt.strftime("%b")

    df = df.sort_values(
        ["segment", "instrument", "month_date"]
    )

    return df


def load_dashboard_data():
    df = load_data_from_db()

    if df.empty:
        df = load_data_from_csv()

    return clean_loaded_data(df)


def format_indian_number(value, decimals=2):
    if pd.isna(value):
        return "-"

    value = float(value)
    abs_value = abs(value)

    if abs_value >= 1_00_00_000:
        return f"{value / 1_00_00_000:,.{decimals}f}Cr"

    if abs_value >= 1_00_000:
        return f"{value / 1_00_000:,.{decimals}f}L"

    if abs_value >= 1_000:
        return f"{value / 1_000:,.{decimals}f}K"

    return f"{value:,.{decimals}f}"


def format_turnover_cr(value):
    if pd.isna(value):
        return "-"

    value = float(value)
    abs_value = abs(value)

    if abs_value >= 1_00_000:
        return f"₹ {value / 1_00_000:,.2f}L Cr"

    if abs_value >= 1_000:
        return f"₹ {value / 1_000:,.2f}K Cr"

    return f"₹ {value:,.2f} Cr"


def get_delta_class(value):
    if pd.isna(value):
        return "delta-pill-neutral"

    if value > 0:
        return "delta-pill-positive"

    if value < 0:
        return "delta-pill-negative"

    return "delta-pill-neutral"


def get_delta_arrow(value):
    if pd.isna(value):
        return "→"

    if value > 0:
        return "↑"

    if value < 0:
        return "↓"

    return "→"


def format_delta(value):
    if pd.isna(value):
        return "No previous data"

    arrow = get_delta_arrow(value)
    return f"{arrow} {abs(value) * 100:,.2f}%"


def render_metric_card(label, value, delta=None):
    delta_html = ""

    if delta is not None:
        delta_class = get_delta_class(delta)
        delta_text = format_delta(delta)

        delta_html = (
            f'<div class="{delta_class}">'
            f'{delta_text}'
            f'</div>'
        )

    card_html = (
        '<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        f'{delta_html}'
        '</div>'
    )

    st.markdown(
        card_html,
        unsafe_allow_html=True,
    )


def get_latest_selected_rows(df):
    if df.empty:
        return None, None

    ordered_df = df.sort_values("month_date").copy()
    latest_row = ordered_df.tail(1).iloc[0]

    previous_row = None

    if len(ordered_df) >= 2:
        previous_row = ordered_df.iloc[-2]

    return latest_row, previous_row


def get_volume_unit_text(segment):
    if segment == "Capital Market":
        return "Lakhs/day"

    return "Contracts/day"


def render_selected_kpis(filtered_df, selected_segment):
    if filtered_df.empty:
        return

    latest_row, previous_row = get_latest_selected_rows(filtered_df)

    if latest_row is None:
        return

    latest_turnover = latest_row["turnover"]
    latest_volume = latest_row["volume"]

    turnover_delta = latest_row["mom_turnover_change"]
    volume_delta = latest_row["mom_volume_change"]

    latest_month = latest_row["month_date"].strftime("%b-%Y")

    financial_period = (
        f"{latest_row['financial_year']} "
        f"{latest_row['financial_quarter']}"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        render_metric_card(
            "Latest Month",
            latest_month,
        )

    with c2:
        render_metric_card(
            "Latest Turnover",
            format_turnover_cr(latest_turnover),
            turnover_delta,
        )

    with c3:
        render_metric_card(
            f"Latest Volume ({get_volume_unit_text(selected_segment)})",
            format_indian_number(latest_volume),
            volume_delta,
        )

    with c4:
        render_metric_card(
            "Financial Period",
            financial_period,
        )


def render_sidebar_filters(df):
    st.sidebar.header("Filters")

    segments = sorted(df["segment"].dropna().unique())

    selected_segment = st.sidebar.selectbox(
        "Segment",
        segments,
        index=0,
    )

    segment_df = df[df["segment"] == selected_segment].copy()

    instruments = sorted(segment_df["instrument"].dropna().unique())

    selected_instrument = st.sidebar.selectbox(
        "Instrument",
        instruments,
        index=0,
    )

    instrument_df = segment_df[
        segment_df["instrument"] == selected_instrument
    ].copy()

    years = sorted(
        instrument_df["financial_year"].dropna().unique(),
        reverse=True,
    )

    selected_financial_years = st.sidebar.multiselect(
        "Financial Year",
        years,
        default=years,
        help="All available financial years are selected by default.",
    )

    available_months = sorted(
        instrument_df["month_name"].dropna().unique(),
        key=lambda month: MONTH_ORDER.get(month, 99),
    )

    selected_months = st.sidebar.multiselect(
        "Month",
        available_months,
        default=available_months,
        help="Select specific months if you want seasonal/month-wise analysis.",
    )

    quarters = ["Q1", "Q2", "Q3", "Q4"]

    selected_quarters = st.sidebar.multiselect(
        "Financial Quarter",
        quarters,
        default=quarters,
    )

    st.sidebar.divider()

    show_moving_average = st.sidebar.checkbox(
        "Show Moving Average",
        value=True,
    )

    ma_window = st.sidebar.select_slider(
        "Moving Average Window",
        options=list(range(2, 13)),
        value=6,
        help="Moving average window from 2 to 12. Applied only on trend charts.",
    )

    change_cap = st.sidebar.selectbox(
        "MoM / QoQ Display Cap",
        [100, 200, 300, 500],
        index=1,
        help="Extreme percentage changes are capped visually. Tooltip still shows actual value.",
    )

    filtered_df = df[
        (df["segment"] == selected_segment)
        & (df["instrument"] == selected_instrument)
    ].copy()

    if selected_financial_years:
        filtered_df = filtered_df[
            filtered_df["financial_year"].isin(selected_financial_years)
        ].copy()

    if selected_months:
        filtered_df = filtered_df[
            filtered_df["month_name"].isin(selected_months)
        ].copy()

    if selected_quarters:
        filtered_df = filtered_df[
            filtered_df["financial_quarter"].isin(selected_quarters)
        ].copy()

    return {
        "selected_segment": selected_segment,
        "selected_instrument": selected_instrument,
        "selected_financial_years": selected_financial_years,
        "selected_months": selected_months,
        "selected_quarters": selected_quarters,
        "show_moving_average": show_moving_average,
        "ma_window": ma_window,
        "change_cap": change_cap,
        "filtered_df": filtered_df,
    }


def render_data_note():
    st.markdown(
        """
        <div class="note-box">
            <b>Note:</b> Turnover is shown as average daily turnover in ₹ Crores.
            Volume for Capital Market is in Lakhs/day. Derivatives volume is in Contracts/day.
            MoM and QoQ charts are capped visually to avoid outlier distortion.
            Charts include their own 1Y / 3Y / 5Y / 10Y / Full range controls.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_insight_box(filtered_df):
    if filtered_df.empty or len(filtered_df) < 2:
        return

    latest_row, previous_row = get_latest_selected_rows(filtered_df)

    if latest_row is None or previous_row is None:
        return

    month = latest_row["month_date"].strftime("%b-%Y")

    turnover_delta = latest_row["mom_turnover_change"]
    volume_delta = latest_row["mom_volume_change"]

    if pd.isna(turnover_delta) or pd.isna(volume_delta):
        return

    turnover_word = "increased" if turnover_delta > 0 else "decreased"
    volume_word = "increased" if volume_delta > 0 else "decreased"

    st.markdown(
        f"""
        <div class="insight-box">
            In <b>{month}</b>, turnover <b>{turnover_word}</b> by
            <b>{abs(turnover_delta) * 100:,.2f}%</b> and volume
            <b>{volume_word}</b> by <b>{abs(volume_delta) * 100:,.2f}%</b>
            compared to the previous month.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview_tab(df, filtered_df, selected_segment, ma_window, show_moving_average):
    st.subheader("Overview Summary")

    if filtered_df.empty:
        st.warning("No data available for selected filters.")
        return

    total_turnover = filtered_df["turnover"].sum()
    average_turnover = filtered_df["turnover"].mean()
    total_volume = filtered_df["volume"].sum()
    average_volume = filtered_df["volume"].mean()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        render_metric_card(
            "Total Turnover",
            format_turnover_cr(total_turnover),
        )

    with c2:
        render_metric_card(
            "Average Turnover",
            format_turnover_cr(average_turnover),
        )

    with c3:
        render_metric_card(
            f"Total Volume ({get_volume_unit_text(selected_segment)})",
            format_indian_number(total_volume),
        )

    with c4:
        render_metric_card(
            f"Average Volume ({get_volume_unit_text(selected_segment)})",
            format_indian_number(average_volume),
        )

    render_insight_box(filtered_df)

    st.divider()

    st.subheader("Best / Worst Month Summary")

    highest_turnover_row = filtered_df.loc[filtered_df["turnover"].idxmax()]
    lowest_turnover_row = filtered_df.loc[filtered_df["turnover"].idxmin()]
    highest_volume_row = filtered_df.loc[filtered_df["volume"].idxmax()]
    lowest_volume_row = filtered_df.loc[filtered_df["volume"].idxmin()]

    b1, b2, b3, b4 = st.columns(4)

    with b1:
        render_metric_card(
            "Highest Turnover Month",
            highest_turnover_row["month_date"].strftime("%b-%Y"),
            highest_turnover_row["mom_turnover_change"],
        )

    with b2:
        render_metric_card(
            "Lowest Turnover Month",
            lowest_turnover_row["month_date"].strftime("%b-%Y"),
            lowest_turnover_row["mom_turnover_change"],
        )

    with b3:
        render_metric_card(
            "Highest Volume Month",
            highest_volume_row["month_date"].strftime("%b-%Y"),
            highest_volume_row["mom_volume_change"],
        )

    with b4:
        render_metric_card(
            "Lowest Volume Month",
            lowest_volume_row["month_date"].strftime("%b-%Y"),
            lowest_volume_row["mom_volume_change"],
        )

    st.divider()

    c5, c6 = st.columns(2)

    with c5:
        st.plotly_chart(
            create_monthly_turnover_chart(
                filtered_df,
                ma_window=ma_window,
                show_ma=show_moving_average,
            ),
            width="stretch",
            key="overview_monthly_turnover_chart",
        )

    with c6:
        st.plotly_chart(
            create_monthly_volume_chart(
                filtered_df,
                ma_window=ma_window,
                show_ma=show_moving_average,
            ),
            width="stretch",
            key="overview_monthly_volume_chart",
        )


def render_monthly_tab(filtered_df, ma_window, show_moving_average, change_cap):
    st.subheader("Monthly Analysis")

    if filtered_df.empty:
        st.warning("No monthly data available for selected filters.")
        return

    c1, c2 = st.columns(2)

    with c1:
        st.plotly_chart(
            create_monthly_turnover_chart(
                filtered_df,
                ma_window=ma_window,
                show_ma=show_moving_average,
            ),
            width="stretch",
            key="monthly_turnover_chart",
        )

    with c2:
        st.plotly_chart(
            create_monthly_volume_chart(
                filtered_df,
                ma_window=ma_window,
                show_ma=show_moving_average,
            ),
            width="stretch",
            key="monthly_volume_chart",
        )

    st.divider()

    st.caption(
        "MoM charts use green/red bars and visual capping. Moving average is intentionally not applied on MoM charts."
    )

    c3, c4 = st.columns(2)

    with c3:
        st.plotly_chart(
            create_mom_turnover_chart(
                filtered_df,
                cap_percent=change_cap,
            ),
            width="stretch",
            key="monthly_mom_turnover_chart",
        )

    with c4:
        st.plotly_chart(
            create_mom_volume_chart(
                filtered_df,
                cap_percent=change_cap,
            ),
            width="stretch",
            key="monthly_mom_volume_chart",
        )


def render_quarterly_tab(filtered_df, ma_window, show_moving_average, change_cap):
    st.subheader("Quarterly Analysis")

    if filtered_df.empty:
        st.warning("No quarterly data available for selected filters.")
        return

    c1, c2 = st.columns(2)

    with c1:
        st.plotly_chart(
            create_quarterly_turnover_chart(
                filtered_df,
                ma_window=ma_window,
                show_ma=show_moving_average,
            ),
            width="stretch",
            key="quarterly_turnover_chart",
        )

    with c2:
        st.plotly_chart(
            create_quarterly_volume_chart(
                filtered_df,
                ma_window=ma_window,
                show_ma=show_moving_average,
            ),
            width="stretch",
            key="quarterly_volume_chart",
        )

    st.divider()

    st.caption(
        "QoQ charts use green/red bars and visual capping. Moving average is intentionally not applied on QoQ charts."
    )

    c3, c4 = st.columns(2)

    with c3:
        st.plotly_chart(
            create_qoq_turnover_chart(
                filtered_df,
                cap_percent=change_cap,
            ),
            width="stretch",
            key="quarterly_qoq_turnover_chart",
        )

    with c4:
        st.plotly_chart(
            create_qoq_volume_chart(
                filtered_df,
                cap_percent=change_cap,
            ),
            width="stretch",
            key="quarterly_qoq_volume_chart",
        )


def render_comparative_tab(df, base_filters):
    st.subheader("Comparative View")

    comparison_df = df.copy()

    if base_filters["selected_financial_years"]:
        comparison_df = comparison_df[
            comparison_df["financial_year"].isin(
                base_filters["selected_financial_years"]
            )
        ].copy()

    if base_filters["selected_months"]:
        comparison_df = comparison_df[
            comparison_df["month_name"].isin(
                base_filters["selected_months"]
            )
        ].copy()

    if base_filters["selected_quarters"]:
        comparison_df = comparison_df[
            comparison_df["financial_quarter"].isin(
                base_filters["selected_quarters"]
            )
        ].copy()

    comparison_df["pair"] = (
        comparison_df["segment"].astype(str)
        + " — "
        + comparison_df["instrument"].astype(str)
    )

    available_pairs = sorted(
        comparison_df["pair"].dropna().unique()
    )

    if not available_pairs:
        st.warning("No data available for comparison.")
        return

    default_pairs = available_pairs[:3]

    selected_pairs = st.multiselect(
        "Select segment/instrument pairs to compare",
        available_pairs,
        default=default_pairs,
        help="Choose only the pairs you want to compare. Too many lines can make the chart crowded.",
        key="comparative_selected_pairs",
    )

    c1, c2 = st.columns(2)

    with c1:
        comparison_metric = st.radio(
            "Metric",
            ["turnover", "volume"],
            horizontal=True,
            format_func=lambda value: (
                "Turnover" if value == "turnover" else "Volume"
            ),
            key="comparison_metric_radio",
        )

    with c2:
        comparison_mode = st.radio(
            "Comparison Mode",
            ["Indexed Growth", "Absolute Value"],
            horizontal=True,
            help="Indexed Growth normalizes each selected series to 100 at the first selected period.",
            key="comparison_mode_radio",
        )

    st.plotly_chart(
        create_comparative_chart(
            comparison_df,
            selected_pairs=selected_pairs,
            metric=comparison_metric,
            comparison_mode=comparison_mode,
        ),
        width="stretch",
        key="comparative_chart",
    )

    st.caption(
        "Recommendation: Use Indexed Growth when comparing segments with very different scales."
    )


def render_data_quality_tab(df):
    st.subheader("Data Quality")

    if df.empty:
        st.warning("No data available.")
        return

    total_rows = len(df)

    duplicate_count = df.duplicated(
        subset=["segment", "instrument", "month_label"]
    ).sum()

    missing_turnover = df["turnover"].isna().sum()
    missing_volume = df["volume"].isna().sum()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        render_metric_card("Total Rows", f"{total_rows:,}")

    with c2:
        render_metric_card("Duplicate Keys", f"{duplicate_count:,}")

    with c3:
        render_metric_card("Missing Turnover", f"{missing_turnover:,}")

    with c4:
        render_metric_card("Missing Volume", f"{missing_volume:,}")

    st.divider()

    st.write("Rows by Segment and Instrument")

    summary = (
        df.groupby(["segment", "instrument"])
        .agg(
            rows=("month_label", "count"),
            start_month=("month_date", "min"),
            end_month=("month_date", "max"),
            avg_turnover=("turnover", "mean"),
            avg_volume=("volume", "mean"),
        )
        .reset_index()
    )

    summary["start_month"] = summary["start_month"].dt.strftime("%b-%Y")
    summary["end_month"] = summary["end_month"].dt.strftime("%b-%Y")

    st.dataframe(
        summary,
        width="stretch",
        hide_index=True,
    )

    st.divider()

    st.write("Raw Data Preview")

    preview_df = df.sort_values(
        ["segment", "instrument", "month_date"],
        ascending=[True, True, False],
    )

    st.dataframe(
        preview_df.head(500),
        width="stretch",
        hide_index=True,
    )


def render_download_section(df):
    st.sidebar.divider()
    st.sidebar.subheader("Download")

    csv_data = df.to_csv(index=False).encode("utf-8-sig")

    st.sidebar.download_button(
        label="Download Filtered CSV",
        data=csv_data,
        file_name="nse_business_growth_filtered.csv",
        mime="text/csv",
    )


def main():
    inject_custom_css()

    st.markdown(
        """
        <div class="dashboard-title">
            📈 NSE Business Growth Dashboard
        </div>
        <div class="dashboard-subtitle">
            Historical monthly business growth analysis across NSE market segments.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.sidebar.button("Refresh Dashboard Data"):
        st.cache_data.clear()
        st.rerun()

    df = load_dashboard_data()

    if df.empty:
        st.error(
            "No data found. Please run the data pipeline or load the SQLite database first."
        )
        st.stop()

    filter_state = render_sidebar_filters(df)
    filtered_df = filter_state["filtered_df"]

    render_download_section(filtered_df)
    render_data_note()

    render_selected_kpis(
        filtered_df=filtered_df,
        selected_segment=filter_state["selected_segment"],
    )

    st.divider()

    selected_label = (
        f"{filter_state['selected_segment']} — "
        f"{filter_state['selected_instrument']} | "
        f"Full History"
    )

    st.markdown(f"### Current Selection: `{selected_label}`")

    tabs = st.tabs(
        [
            "Overview",
            "Monthly Analysis",
            "Quarterly Analysis",
            "Comparative View",
            "Data Quality",
        ]
    )

    with tabs[0]:
        render_overview_tab(
            df=df,
            filtered_df=filtered_df,
            selected_segment=filter_state["selected_segment"],
            ma_window=filter_state["ma_window"],
            show_moving_average=filter_state["show_moving_average"],
        )

    with tabs[1]:
        render_monthly_tab(
            filtered_df=filtered_df,
            ma_window=filter_state["ma_window"],
            show_moving_average=filter_state["show_moving_average"],
            change_cap=filter_state["change_cap"],
        )

    with tabs[2]:
        render_quarterly_tab(
            filtered_df=filtered_df,
            ma_window=filter_state["ma_window"],
            show_moving_average=filter_state["show_moving_average"],
            change_cap=filter_state["change_cap"],
        )

    with tabs[3]:
        render_comparative_tab(
            df=df,
            base_filters=filter_state,
        )

    with tabs[4]:
        render_data_quality_tab(df)


if __name__ == "__main__":
    main()