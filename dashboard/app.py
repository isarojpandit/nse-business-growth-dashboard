import sys
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px


DB_PATH = Path("data/nse_business_growth.db")
RAW_EXCEL_PATH = Path("data/raw/Business growth & Volume Dashboard.xlsx")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from scripts.run_pipeline import run_pipeline


st.set_page_config(
    page_title="NSE Business Growth Dashboard",
    page_icon="📈",
    layout="wide"
)


@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql_query(
        """
        SELECT *
        FROM nse_business_growth
        """,
        conn
    )

    conn.close()

    df["month_date"] = pd.to_datetime(df["month_date"], errors="coerce")
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["turnover"] = pd.to_numeric(df["turnover"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

    df["mom_turnover_change"] = pd.to_numeric(
        df["mom_turnover_change"],
        errors="coerce"
    )

    df["mom_volume_change"] = pd.to_numeric(
        df["mom_volume_change"],
        errors="coerce"
    )

    df["month_name"] = df["month_date"].dt.strftime("%b")

    month_order = {
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
        "Mar": 12
    }

    df["financial_month_order"] = df["month_name"].map(month_order)

    return df


def save_uploaded_excel(uploaded_file):
    """
    Save uploaded Excel file into data/raw folder with the standard file name.
    This allows the existing pipeline to run without any code change.
    """

    RAW_EXCEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(RAW_EXCEL_PATH, "wb") as file:
        file.write(uploaded_file.getbuffer())

    return RAW_EXCEL_PATH


def get_last_updated_time():
    if not DB_PATH.exists():
        return "Database not created yet"

    modified_timestamp = DB_PATH.stat().st_mtime
    modified_time = datetime.fromtimestamp(modified_timestamp)

    return modified_time.strftime("%d-%b-%Y %I:%M %p")


def format_number(value):
    if pd.isna(value):
        return "N/A"

    if abs(value) >= 1_00_00_000:
        return f"{value / 1_00_00_000:.2f} Cr"

    if abs(value) >= 1_00_000:
        return f"{value / 1_00_000:.2f} L"

    return f"{value:,.2f}"


def format_percent(value):
    if pd.isna(value):
        return "N/A"

    return f"{value * 100:.2f}%"


def format_dataframe_for_display(df):
    display_df = df.copy()

    number_columns = [
        "turnover",
        "volume",
        "turnover_3m_ma",
        "volume_3m_ma",
        "average_turnover",
        "average_volume",
        "total_turnover",
        "total_volume"
    ]

    percent_columns = [
        "mom_turnover_change",
        "mom_volume_change",
        "qoq_turnover_change",
        "qoq_volume_change"
    ]

    for col in number_columns:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(format_number)

    for col in percent_columns:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(format_percent)

    return display_df


def create_quarterly_data(df):
    quarterly_df = (
        df.groupby(
            ["segment", "instrument", "financial_year", "financial_quarter"],
            as_index=False
        )
        .agg(
            average_turnover=("turnover", "mean"),
            average_volume=("volume", "mean"),
            quarter_start=("month_date", "min")
        )
    )

    quarter_order = {
        "Q1": 1,
        "Q2": 2,
        "Q3": 3,
        "Q4": 4
    }

    quarterly_df["quarter_order"] = quarterly_df["financial_quarter"].map(
        quarter_order
    )

    quarterly_df = quarterly_df.sort_values(
        ["segment", "instrument", "financial_year", "quarter_order"]
    )

    quarterly_df["financial_period"] = (
        quarterly_df["financial_year"]
        + " "
        + quarterly_df["financial_quarter"]
    )

    quarterly_df["qoq_turnover_change"] = (
        quarterly_df
        .groupby(["segment", "instrument"])["average_turnover"]
        .pct_change()
    )

    quarterly_df["qoq_volume_change"] = (
        quarterly_df
        .groupby(["segment", "instrument"])["average_volume"]
        .pct_change()
    )

    return quarterly_df


def add_moving_average(df):
    df = df.sort_values("month_date").copy()

    df["turnover_3m_ma"] = (
        df["turnover"]
        .rolling(window=3, min_periods=1)
        .mean()
    )

    df["volume_3m_ma"] = (
        df["volume"]
        .rolling(window=3, min_periods=1)
        .mean()
    )

    return df


def get_business_insight(filtered_df):
    latest_row = filtered_df.dropna(subset=["month_date"]).tail(1)

    if latest_row.empty:
        return "No data available for selected filters."

    latest = latest_row.iloc[0]

    turnover_change = latest["mom_turnover_change"]
    volume_change = latest["mom_volume_change"]

    if pd.isna(turnover_change) or pd.isna(volume_change):
        return (
            f"For {latest['month_label']}, previous month comparison is not available."
        )

    turnover_text = "increased" if turnover_change > 0 else "decreased"
    volume_text = "increased" if volume_change > 0 else "decreased"

    if turnover_change > 0 and volume_change > 0:
        interpretation = (
            "This indicates strong business growth because both turnover and volume improved."
        )
    elif turnover_change > 0 and volume_change < 0:
        interpretation = (
            "This indicates value growth, but trading participation weakened compared to the previous month."
        )
    elif turnover_change < 0 and volume_change > 0:
        interpretation = (
            "This indicates higher participation, but lower average business value."
        )
    else:
        interpretation = (
            "This indicates a weak month because both turnover and volume declined."
        )

    return (
        f"In {latest['month_label']}, turnover {turnover_text} by "
        f"{format_percent(turnover_change)} and volume {volume_text} by "
        f"{format_percent(volume_change)}. {interpretation}"
    )


def show_data_quality_summary(df):
    total_rows = len(df)
    missing_turnover = df["turnover"].isna().sum()
    missing_volume = df["volume"].isna().sum()

    duplicate_rows = df.duplicated(
        subset=[
            "segment",
            "instrument",
            "month_label",
            "financial_year",
            "financial_quarter"
        ]
    ).sum()

    latest_month = df["month_date"].max()
    earliest_month = df["month_date"].min()

    if pd.notna(latest_month):
        latest_month_text = latest_month.strftime("%b-%Y")
    else:
        latest_month_text = "N/A"

    if pd.notna(earliest_month):
        earliest_month_text = earliest_month.strftime("%b-%Y")
    else:
        earliest_month_text = "N/A"

    st.subheader("Data Quality Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Rows", f"{total_rows}")
    col2.metric("Missing Turnover", f"{missing_turnover}")
    col3.metric("Missing Volume", f"{missing_volume}")
    col4.metric("Duplicate Rows", f"{duplicate_rows}")

    col5, col6, col7 = st.columns(3)

    col5.metric("Earliest Month", earliest_month_text)
    col6.metric("Latest Month", latest_month_text)
    col7.metric("Last DB Update", get_last_updated_time())


def show_kpi_cards(filtered_df):
    latest_row = filtered_df.dropna(subset=["month_date"]).tail(1)

    if latest_row.empty:
        st.warning("No data found for selected filters.")
        return False

    latest = latest_row.iloc[0]

    total_turnover = filtered_df["turnover"].sum()
    avg_turnover = filtered_df["turnover"].mean()
    total_volume = filtered_df["volume"].sum()
    avg_volume = filtered_df["volume"].mean()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Latest Month",
        latest["month_label"]
    )

    col2.metric(
        "Latest Turnover",
        format_number(latest["turnover"]),
        format_percent(latest["mom_turnover_change"])
    )

    col3.metric(
        "Latest Volume",
        format_number(latest["volume"]),
        format_percent(latest["mom_volume_change"])
    )

    col4.metric(
        "Financial Period",
        f"{latest['financial_year']} {latest['financial_quarter']}"
    )

    st.write("")

    col5, col6, col7, col8 = st.columns(4)

    col5.metric(
        "Total Turnover",
        format_number(total_turnover)
    )

    col6.metric(
        "Average Turnover",
        format_number(avg_turnover)
    )

    col7.metric(
        "Total Volume",
        format_number(total_volume)
    )

    col8.metric(
        "Average Volume",
        format_number(avg_volume)
    )

    return True


def show_best_worst_cards(filtered_df):
    if filtered_df.empty:
        return

    best_turnover = filtered_df.loc[filtered_df["turnover"].idxmax()]
    worst_turnover = filtered_df.loc[filtered_df["turnover"].idxmin()]
    best_volume = filtered_df.loc[filtered_df["volume"].idxmax()]
    worst_volume = filtered_df.loc[filtered_df["volume"].idxmin()]

    st.subheader("Best / Worst Month Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Highest Turnover Month",
        best_turnover["month_label"],
        format_number(best_turnover["turnover"])
    )

    col2.metric(
        "Lowest Turnover Month",
        worst_turnover["month_label"],
        format_number(worst_turnover["turnover"])
    )

    col3.metric(
        "Highest Volume Month",
        best_volume["month_label"],
        format_number(best_volume["volume"])
    )

    col4.metric(
        "Lowest Volume Month",
        worst_volume["month_label"],
        format_number(worst_volume["volume"])
    )


def make_line_with_moving_average(
    df,
    y_actual,
    y_ma,
    chart_title,
    y_axis_title,
    actual_name,
    ma_name
):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["month_date"],
            y=df[y_actual],
            mode="lines+markers",
            name=actual_name,
            text=df["month_label"],
            hovertemplate="%{text}<br>Value: %{y}<extra></extra>"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["month_date"],
            y=df[y_ma],
            mode="lines+markers",
            name=ma_name,
            text=df["month_label"],
            hovertemplate="%{text}<br>3M MA: %{y}<extra></extra>"
        )
    )

    fig.update_layout(
        title=chart_title,
        xaxis_title="Month",
        yaxis_title=y_axis_title,
        legend_title="Metric",
        height=450
    )

    fig.update_xaxes(
        tickformat="%b-%Y",
        tickangle=-45
    )

    return fig


def add_zero_line(fig):
    fig.add_hline(
        y=0,
        line_dash="dash"
    )

    fig.update_layout(
        yaxis_tickformat=".0%",
        bargap=0.25,
        height=450
    )

    return fig


def make_mom_bar_chart(
    df,
    y_column,
    chart_title,
    y_axis_title
):
    fig = px.bar(
        df,
        x="month_date",
        y=y_column,
        title=chart_title,
        hover_data=[
            "month_label",
            "financial_year",
            "financial_quarter"
        ]
    )

    fig.update_layout(
        xaxis_title="Month",
        yaxis_title=y_axis_title,
        yaxis_tickformat=".0%",
        bargap=0.25,
        height=450
    )

    fig.update_xaxes(
        tickformat="%b-%Y",
        tickangle=-45
    )

    fig = add_zero_line(fig)

    return fig


def make_qoq_bar_chart(
    df,
    y_column,
    chart_title,
    y_axis_title
):
    fig = px.bar(
        df,
        x="financial_period",
        y=y_column,
        title=chart_title,
        hover_data=[
            "financial_year",
            "financial_quarter"
        ]
    )

    fig.update_layout(
        xaxis_title="Financial Quarter",
        yaxis_title=y_axis_title,
        yaxis_tickformat=".0%",
        bargap=0.25,
        height=450
    )

    fig.update_xaxes(
        tickangle=-45
    )

    fig = add_zero_line(fig)

    return fig


def main():
    st.title("📈 NSE Business Growth & Volume Dashboard")
    st.caption("Automated dashboard using Excel → SQLite → Streamlit")

    st.sidebar.header("Data Upload & Refresh")

    uploaded_file = st.sidebar.file_uploader(
        "Upload Excel File",
        type=["xlsx"]
    )

    if uploaded_file is not None:
        if st.sidebar.button("⬆️ Upload & Run Pipeline"):
            saved_path = save_uploaded_excel(uploaded_file)

            st.sidebar.success(
                f"Excel file uploaded successfully: {saved_path}"
            )

            with st.spinner("Running pipeline from uploaded Excel file..."):
                success, message = run_pipeline()

            if success:
                st.sidebar.success(message)
                st.cache_data.clear()
                st.rerun()
            else:
                st.sidebar.error(message)

    if st.sidebar.button("🔄 Run Pipeline from Existing Excel"):
        with st.spinner("Reading Excel, cleaning data, and updating database..."):
            success, message = run_pipeline()

        if success:
            st.sidebar.success(message)
            st.cache_data.clear()
            st.rerun()
        else:
            st.sidebar.error(message)

    if st.sidebar.button("♻️ Refresh Dashboard Only"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.divider()
    st.sidebar.header("Filters")

    if not DB_PATH.exists():
        st.warning("Database not found.")
        st.info(
            "Please upload the Excel file from the sidebar and click "
            "'Upload & Run Pipeline'."
        )
        return

    df = load_data()

    if df.empty:
        st.warning("No data found in database.")
        return

    quarterly_df = create_quarterly_data(df)

    segments = sorted(df["segment"].dropna().unique())
    selected_segment = st.sidebar.selectbox(
        "Segment",
        segments
    )

    segment_df = df[df["segment"] == selected_segment].copy()

    instruments = sorted(segment_df["instrument"].dropna().unique())
    selected_instrument = st.sidebar.selectbox(
        "Instrument",
        instruments
    )

    financial_years = sorted(segment_df["financial_year"].dropna().unique())
    selected_financial_years = st.sidebar.multiselect(
        "Financial Year",
        financial_years,
        default=financial_years
    )

    quarter_order_list = ["Q1", "Q2", "Q3", "Q4"]
    available_quarters = [
        quarter
        for quarter in quarter_order_list
        if quarter in segment_df["financial_quarter"].dropna().unique()
    ]

    selected_quarters = st.sidebar.multiselect(
        "Financial Quarter",
        available_quarters,
        default=available_quarters
    )

    month_order_list = [
        "Apr", "May", "Jun",
        "Jul", "Aug", "Sep",
        "Oct", "Nov", "Dec",
        "Jan", "Feb", "Mar"
    ]

    available_months = [
        month
        for month in month_order_list
        if month in segment_df["month_name"].dropna().unique()
    ]

    selected_months = st.sidebar.multiselect(
        "Month",
        available_months,
        default=available_months
    )

    filtered_df = segment_df[
        (segment_df["instrument"] == selected_instrument)
        & (segment_df["financial_year"].isin(selected_financial_years))
        & (segment_df["financial_quarter"].isin(selected_quarters))
        & (segment_df["month_name"].isin(selected_months))
    ].copy()

    filtered_df = filtered_df.sort_values("month_date")
    filtered_df = add_moving_average(filtered_df)

    st.subheader(f"{selected_segment} — {selected_instrument}")

    has_data = show_kpi_cards(filtered_df)

    if not has_data:
        return

    st.info(get_business_insight(filtered_df))

    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Overview",
            "Monthly Analysis",
            "Quarterly Analysis",
            "Comparative View",
            "Data Quality"
        ]
    )

    with tab1:
        st.subheader("Overview Summary")

        show_best_worst_cards(filtered_df)

        st.write("")

        fy_summary = (
            filtered_df
            .groupby("financial_year", as_index=False)
            .agg(
                total_turnover=("turnover", "sum"),
                average_turnover=("turnover", "mean"),
                total_volume=("volume", "sum"),
                average_volume=("volume", "mean")
            )
        )

        st.subheader("Financial Year Summary")

        st.dataframe(
            format_dataframe_for_display(fy_summary),
            use_container_width=True
        )

        st.download_button(
            label="⬇️ Download FY Summary",
            data=fy_summary.to_csv(index=False),
            file_name="nse_financial_year_summary.csv",
            mime="text/csv"
        )

    with tab2:
        st.subheader("Monthly Performance with 3-Month Moving Average")

        col1, col2 = st.columns(2)

        with col1:
            fig_turnover = make_line_with_moving_average(
                df=filtered_df,
                y_actual="turnover",
                y_ma="turnover_3m_ma",
                chart_title="Monthly Average Turnover + 3M Moving Average",
                y_axis_title="Turnover",
                actual_name="Actual Turnover",
                ma_name="3M Moving Average"
            )

            st.plotly_chart(fig_turnover, use_container_width=True)

        with col2:
            fig_volume = make_line_with_moving_average(
                df=filtered_df,
                y_actual="volume",
                y_ma="volume_3m_ma",
                chart_title="Average Volume + 3M Moving Average",
                y_axis_title="Volume",
                actual_name="Actual Volume",
                ma_name="3M Moving Average"
            )

            st.plotly_chart(fig_volume, use_container_width=True)

        col3, col4 = st.columns(2)

        with col3:
            fig_mom_turnover = make_mom_bar_chart(
                df=filtered_df,
                y_column="mom_turnover_change",
                chart_title="MoM % Change — Turnover",
                y_axis_title="MoM Change"
            )

            st.plotly_chart(fig_mom_turnover, use_container_width=True)

        with col4:
            fig_mom_volume = make_mom_bar_chart(
                df=filtered_df,
                y_column="mom_volume_change",
                chart_title="MoM % Change — Volume",
                y_axis_title="MoM Change"
            )

            st.plotly_chart(fig_mom_volume, use_container_width=True)

        st.subheader("Monthly Data Preview")

        st.download_button(
            label="⬇️ Download Filtered Monthly Data",
            data=filtered_df.to_csv(index=False),
            file_name="nse_filtered_monthly_data.csv",
            mime="text/csv"
        )

        st.dataframe(
            format_dataframe_for_display(filtered_df),
            use_container_width=True
        )

    with tab3:
        st.subheader("Quarterly Performance")

        selected_quarterly_df = quarterly_df[
            (quarterly_df["segment"] == selected_segment)
            & (quarterly_df["instrument"] == selected_instrument)
            & (quarterly_df["financial_year"].isin(selected_financial_years))
            & (quarterly_df["financial_quarter"].isin(selected_quarters))
        ].copy()

        selected_quarterly_df = selected_quarterly_df.sort_values(
            ["financial_year", "quarter_order"]
        )

        col1, col2 = st.columns(2)

        with col1:
            fig_q_turnover = px.line(
                selected_quarterly_df,
                x="financial_period",
                y="average_turnover",
                markers=True,
                title="Quarterly Average Turnover"
            )

            fig_q_turnover.update_layout(
                xaxis_title="Financial Quarter",
                yaxis_title="Average Turnover",
                height=450
            )

            fig_q_turnover.update_xaxes(
                tickangle=-45
            )

            st.plotly_chart(fig_q_turnover, use_container_width=True)

        with col2:
            fig_q_volume = px.line(
                selected_quarterly_df,
                x="financial_period",
                y="average_volume",
                markers=True,
                title="Quarterly Average Volume"
            )

            fig_q_volume.update_layout(
                xaxis_title="Financial Quarter",
                yaxis_title="Average Volume",
                height=450
            )

            fig_q_volume.update_xaxes(
                tickangle=-45
            )

            st.plotly_chart(fig_q_volume, use_container_width=True)

        col3, col4 = st.columns(2)

        with col3:
            fig_qoq_turnover = make_qoq_bar_chart(
                df=selected_quarterly_df,
                y_column="qoq_turnover_change",
                chart_title="QoQ % Change — Turnover",
                y_axis_title="QoQ Change"
            )

            st.plotly_chart(fig_qoq_turnover, use_container_width=True)

        with col4:
            fig_qoq_volume = make_qoq_bar_chart(
                df=selected_quarterly_df,
                y_column="qoq_volume_change",
                chart_title="QoQ % Change — Volume",
                y_axis_title="QoQ Change"
            )

            st.plotly_chart(fig_qoq_volume, use_container_width=True)

        st.subheader("Quarterly Data Preview")

        st.download_button(
            label="⬇️ Download Quarterly Data",
            data=selected_quarterly_df.to_csv(index=False),
            file_name="nse_quarterly_data.csv",
            mime="text/csv"
        )

        st.dataframe(
            format_dataframe_for_display(selected_quarterly_df),
            use_container_width=True
        )

    with tab4:
        st.subheader("Comparative View")

        comparison_df = df.copy()

        if selected_financial_years:
            comparison_df = comparison_df[
                comparison_df["financial_year"].isin(selected_financial_years)
            ]

        if selected_quarters:
            comparison_df = comparison_df[
                comparison_df["financial_quarter"].isin(selected_quarters)
            ]

        if selected_months:
            comparison_df = comparison_df[
                comparison_df["month_name"].isin(selected_months)
            ]

        comparison_df = comparison_df.sort_values("month_date")

        fig_compare = px.line(
            comparison_df,
            x="month_date",
            y="turnover",
            color="segment",
            line_dash="instrument",
            markers=True,
            hover_data=[
                "month_label",
                "instrument",
                "financial_year",
                "financial_quarter"
            ],
            title="Turnover Comparison Across Segments"
        )

        fig_compare.update_layout(
            xaxis_title="Month",
            yaxis_title="Turnover",
            height=500
        )

        fig_compare.update_xaxes(
            tickformat="%b-%Y",
            tickangle=-45
        )

        st.plotly_chart(fig_compare, use_container_width=True)

        st.subheader("Segment Ranking")

        ranking_df = (
            comparison_df
            .groupby(["segment", "instrument"], as_index=False)
            .agg(
                total_turnover=("turnover", "sum"),
                average_turnover=("turnover", "mean"),
                total_volume=("volume", "sum"),
                average_volume=("volume", "mean")
            )
            .sort_values("total_turnover", ascending=False)
        )

        ranking_df["rank"] = range(1, len(ranking_df) + 1)

        ranking_df = ranking_df[
            [
                "rank",
                "segment",
                "instrument",
                "total_turnover",
                "average_turnover",
                "total_volume",
                "average_volume"
            ]
        ]

        st.dataframe(
            format_dataframe_for_display(ranking_df),
            use_container_width=True
        )

        st.subheader("YoY Growth — Same Month Across Financial Years")

        yoy_df = df.copy()
        yoy_df["month_name"] = yoy_df["month_date"].dt.strftime("%b")

        yoy_filtered = yoy_df[
            (yoy_df["segment"] == selected_segment)
            & (yoy_df["instrument"] == selected_instrument)
            & (yoy_df["financial_year"].isin(selected_financial_years))
        ].copy()

        fig_yoy = px.bar(
            yoy_filtered,
            x="month_name",
            y="turnover",
            color="financial_year",
            barmode="group",
            title=f"YoY Turnover Comparison — {selected_segment} / {selected_instrument}"
        )

        fig_yoy.update_layout(
            xaxis_title="Month",
            yaxis_title="Turnover",
            height=450
        )

        st.plotly_chart(fig_yoy, use_container_width=True)

        st.subheader("Comparison Data Preview")

        st.download_button(
            label="⬇️ Download Comparison Data",
            data=comparison_df.to_csv(index=False),
            file_name="nse_comparison_data.csv",
            mime="text/csv"
        )

        st.dataframe(
            format_dataframe_for_display(comparison_df),
            use_container_width=True
        )

    with tab5:
        show_data_quality_summary(df)

        st.subheader("Raw Database Preview")

        st.dataframe(
            format_dataframe_for_display(df),
            use_container_width=True
        )


if __name__ == "__main__":
    main()