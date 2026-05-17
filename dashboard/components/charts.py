import pandas as pd
import plotly.graph_objects as go


TIME_RANGE_OPTIONS = [
    "Last 1 Year",
    "Last 3 Years",
    "Last 5 Years",
    "Last 10 Years",
    "Full History",
]


def prepare_month_date(df):
    df = df.copy()
    df["month_date"] = pd.to_datetime(df["month_date"], errors="coerce")
    df = df.dropna(subset=["month_date"])
    return df


def apply_time_range_filter(df, time_range):
    df = prepare_month_date(df)

    if df.empty or time_range == "Full History":
        return df

    max_date = df["month_date"].max()

    years_map = {
        "Last 1 Year": 1,
        "Last 3 Years": 3,
        "Last 5 Years": 5,
        "Last 10 Years": 10,
    }

    years = years_map.get(time_range)

    if years is None:
        return df

    min_date = max_date - pd.DateOffset(years=years)

    return df[df["month_date"] >= min_date].copy()


def get_volume_axis_label(df):
    segments = set(df["segment"].dropna().unique())

    if len(segments) == 1 and "Capital Market" in segments:
        return "Average Daily Volume (Lakhs)"

    if "Capital Market" in segments and len(segments) > 1:
        return "Average Daily Volume (Lakhs / Contracts)"

    return "Average Daily Volume (Contracts)"


def format_large_axis(fig):
    fig.update_layout(
        hovermode="x unified",
        margin=dict(l=20, r=20, t=60, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    fig.update_xaxes(
        rangeslider=dict(visible=True),
        rangeselector=dict(
            buttons=[
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(count=3, label="3Y", step="year", stepmode="backward"),
                dict(count=5, label="5Y", step="year", stepmode="backward"),
                dict(count=10, label="10Y", step="year", stepmode="backward"),
                dict(step="all", label="Full"),
            ]
        ),
        showgrid=True,
    )

    fig.update_yaxes(
        autorange=True,
        showgrid=True,
        zeroline=True,
    )

    return fig


def add_moving_average(df, value_col, window):
    df = df.sort_values("month_date").copy()

    ma_col = f"{value_col}_ma_{window}"

    df[ma_col] = (
        df[value_col]
        .rolling(window=window, min_periods=1)
        .mean()
    )

    return df, ma_col


def create_monthly_turnover_chart(df, ma_window=6, show_ma=True):
    df = prepare_month_date(df)
    df = df.sort_values("month_date")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["month_date"],
            y=df["turnover"],
            mode="lines+markers",
            name="Actual Turnover",
            line=dict(width=2),
            marker=dict(size=5),
            hovertemplate=(
                "Month=%{x|%b-%Y}<br>"
                "Turnover=%{y:,.2f} ₹ Cr"
                "<extra></extra>"
            ),
        )
    )

    if show_ma:
        df, ma_col = add_moving_average(df, "turnover", ma_window)

        fig.add_trace(
            go.Scatter(
                x=df["month_date"],
                y=df[ma_col],
                mode="lines",
                name=f"{ma_window}M Moving Average",
                line=dict(width=3, dash="dot"),
                hovertemplate=(
                    "Month=%{x|%b-%Y}<br>"
                    f"{ma_window}M MA=%{{y:,.2f}} ₹ Cr"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=f"Monthly Average Turnover with {ma_window}M Moving Average",
        xaxis_title="Month",
        yaxis_title="Average Daily Turnover (₹ Cr)",
    )

    return format_large_axis(fig)


def create_monthly_volume_chart(df, ma_window=6, show_ma=True):
    df = prepare_month_date(df)
    df = df.sort_values("month_date")

    volume_label = get_volume_axis_label(df)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["month_date"],
            y=df["volume"],
            mode="lines+markers",
            name="Actual Volume",
            line=dict(width=2),
            marker=dict(size=5),
            hovertemplate=(
                "Month=%{x|%b-%Y}<br>"
                "Volume=%{y:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    if show_ma:
        df, ma_col = add_moving_average(df, "volume", ma_window)

        fig.add_trace(
            go.Scatter(
                x=df["month_date"],
                y=df[ma_col],
                mode="lines",
                name=f"{ma_window}M Moving Average",
                line=dict(width=3, dash="dot"),
                hovertemplate=(
                    "Month=%{x|%b-%Y}<br>"
                    f"{ma_window}M MA=%{{y:,.2f}}"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=f"Monthly Average Volume with {ma_window}M Moving Average",
        xaxis_title="Month",
        yaxis_title=volume_label,
    )

    return format_large_axis(fig)


def create_change_bar_chart(
    df,
    change_col,
    title,
    yaxis_title,
    cap_percent=200,
):
    df = prepare_month_date(df)
    df = df.sort_values("month_date").copy()

    df["actual_change_pct"] = df[change_col] * 100

    cap_value = cap_percent

    df["display_change_pct"] = df["actual_change_pct"].clip(
        lower=-cap_value,
        upper=cap_value,
    )

    df["bar_color"] = df["actual_change_pct"].apply(
        lambda value: "#2ca02c" if value >= 0 else "#d62728"
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df["month_date"],
            y=df["display_change_pct"],
            marker_color=df["bar_color"],
            name="Change %",
            customdata=df[["actual_change_pct"]],
            hovertemplate=(
                "Month=%{x|%b-%Y}<br>"
                "Displayed Change=%{y:.2f}%<br>"
                "Actual Change=%{customdata[0]:.2f}%"
                "<extra></extra>"
            ),
        )
    )

    fig.add_hline(
        y=0,
        line_width=1,
        line_dash="dash",
        line_color="black",
    )

    fig.update_layout(
        title=f"{title} (Capped at ±{cap_percent}%)",
        xaxis_title="Month",
        yaxis_title=yaxis_title,
        showlegend=False,
    )

    return format_large_axis(fig)


def create_mom_turnover_chart(df, cap_percent=200):
    return create_change_bar_chart(
        df=df,
        change_col="mom_turnover_change",
        title="MoM % Change — Turnover",
        yaxis_title="MoM Change (%)",
        cap_percent=cap_percent,
    )


def create_mom_volume_chart(df, cap_percent=200):
    return create_change_bar_chart(
        df=df,
        change_col="mom_volume_change",
        title="MoM % Change — Volume",
        yaxis_title="MoM Change (%)",
        cap_percent=cap_percent,
    )


def build_quarterly_data(df):
    df = prepare_month_date(df).copy()

    df["fy_start_year"] = df["financial_year"].str.extract(r"FY (\d{4})").astype(float)

    quarter_order = {
        "Q1": 1,
        "Q2": 2,
        "Q3": 3,
        "Q4": 4,
    }

    df["fq_order"] = df["financial_quarter"].map(quarter_order)

    quarter_df = (
        df.groupby(
            [
                "segment",
                "instrument",
                "financial_year",
                "financial_quarter",
                "fy_start_year",
                "fq_order",
            ],
            as_index=False,
        )
        .agg(
            average_turnover=("turnover", "mean"),
            average_volume=("volume", "mean"),
            quarter_start=("month_date", "min"),
        )
    )

    quarter_df = quarter_df.sort_values(
        ["segment", "instrument", "fy_start_year", "fq_order"]
    )

    quarter_df["financial_period"] = (
        quarter_df["financial_year"]
        + " "
        + quarter_df["financial_quarter"]
    )

    quarter_df["qoq_turnover_change"] = (
        quarter_df.groupby(["segment", "instrument"])["average_turnover"].pct_change()
    )

    quarter_df["qoq_volume_change"] = (
        quarter_df.groupby(["segment", "instrument"])["average_volume"].pct_change()
    )

    return quarter_df


def create_quarterly_turnover_chart(df, ma_window=4, show_ma=True):
    quarter_df = build_quarterly_data(df)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=quarter_df["quarter_start"],
            y=quarter_df["average_turnover"],
            mode="lines+markers",
            name="Quarterly Avg Turnover",
            hovertemplate=(
                "Quarter=%{customdata}<br>"
                "Turnover=%{y:,.2f} ₹ Cr"
                "<extra></extra>"
            ),
            customdata=quarter_df["financial_period"],
        )
    )

    if show_ma:
        quarter_df = quarter_df.sort_values("quarter_start")
        quarter_df["turnover_q_ma"] = (
            quarter_df["average_turnover"]
            .rolling(window=ma_window, min_periods=1)
            .mean()
        )

        fig.add_trace(
            go.Scatter(
                x=quarter_df["quarter_start"],
                y=quarter_df["turnover_q_ma"],
                mode="lines",
                name=f"{ma_window}Q Moving Average",
                line=dict(width=3, dash="dot"),
            )
        )

    fig.update_layout(
        title=f"Quarterly Average Turnover with {ma_window}Q Moving Average",
        xaxis_title="Financial Quarter",
        yaxis_title="Average Daily Turnover (₹ Cr)",
    )

    return format_large_axis(fig)


def create_quarterly_volume_chart(df, ma_window=4, show_ma=True):
    quarter_df = build_quarterly_data(df)

    volume_label = get_volume_axis_label(df)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=quarter_df["quarter_start"],
            y=quarter_df["average_volume"],
            mode="lines+markers",
            name="Quarterly Avg Volume",
            hovertemplate=(
                "Quarter=%{customdata}<br>"
                "Volume=%{y:,.2f}"
                "<extra></extra>"
            ),
            customdata=quarter_df["financial_period"],
        )
    )

    if show_ma:
        quarter_df = quarter_df.sort_values("quarter_start")
        quarter_df["volume_q_ma"] = (
            quarter_df["average_volume"]
            .rolling(window=ma_window, min_periods=1)
            .mean()
        )

        fig.add_trace(
            go.Scatter(
                x=quarter_df["quarter_start"],
                y=quarter_df["volume_q_ma"],
                mode="lines",
                name=f"{ma_window}Q Moving Average",
                line=dict(width=3, dash="dot"),
            )
        )

    fig.update_layout(
        title=f"Quarterly Average Volume with {ma_window}Q Moving Average",
        xaxis_title="Financial Quarter",
        yaxis_title=volume_label,
    )

    return format_large_axis(fig)


def create_qoq_turnover_chart(df, cap_percent=200):
    quarter_df = build_quarterly_data(df)

    quarter_df = quarter_df.rename(
        columns={
            "quarter_start": "month_date",
            "qoq_turnover_change": "qoq_change",
        }
    )

    return create_change_bar_chart(
        df=quarter_df,
        change_col="qoq_change",
        title="QoQ % Change — Turnover",
        yaxis_title="QoQ Change (%)",
        cap_percent=cap_percent,
    )


def create_qoq_volume_chart(df, cap_percent=200):
    quarter_df = build_quarterly_data(df)

    quarter_df = quarter_df.rename(
        columns={
            "quarter_start": "month_date",
            "qoq_volume_change": "qoq_change",
        }
    )

    return create_change_bar_chart(
        df=quarter_df,
        change_col="qoq_change",
        title="QoQ % Change — Volume",
        yaxis_title="QoQ Change (%)",
        cap_percent=cap_percent,
    )


def create_comparative_chart(
    df,
    selected_pairs,
    metric="turnover",
    comparison_mode="Indexed Growth",
):
    df = prepare_month_date(df)
    df = df.sort_values("month_date").copy()

    df["pair"] = df["segment"] + " — " + df["instrument"]

    if selected_pairs:
        df = df[df["pair"].isin(selected_pairs)].copy()

    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available for selected comparison")
        return fig

    metric_label = (
        "Average Daily Turnover (₹ Cr)"
        if metric == "turnover"
        else get_volume_axis_label(df)
    )

    value_col = metric

    if comparison_mode == "Indexed Growth":
        indexed_frames = []

        for pair, pair_df in df.groupby("pair"):
            pair_df = pair_df.sort_values("month_date").copy()

            base_value = pair_df[value_col].replace(0, pd.NA).dropna()

            if base_value.empty:
                continue

            base = base_value.iloc[0]

            pair_df["comparison_value"] = pair_df[value_col] / base * 100
            indexed_frames.append(pair_df)

        if indexed_frames:
            df = pd.concat(indexed_frames, ignore_index=True)
        else:
            df["comparison_value"] = None

        yaxis_title = "Indexed Growth (Base = 100)"
        title = f"Comparative View — {metric.title()} Indexed Growth"

    else:
        df["comparison_value"] = df[value_col]
        yaxis_title = metric_label
        title = f"Comparative View — Absolute {metric.title()}"

    fig = go.Figure()

    for pair, pair_df in df.groupby("pair"):
        fig.add_trace(
            go.Scatter(
                x=pair_df["month_date"],
                y=pair_df["comparison_value"],
                mode="lines+markers",
                name=pair,
                marker=dict(size=5),
                hovertemplate=(
                    "Month=%{x|%b-%Y}<br>"
                    "Value=%{y:,.2f}<br>"
                    f"Series={pair}"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Month",
        yaxis_title=yaxis_title,
    )

    return format_large_axis(fig)