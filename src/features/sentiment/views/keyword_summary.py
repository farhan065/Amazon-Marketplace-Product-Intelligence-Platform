import plotly.express as px
import streamlit as st

from ..analytics import filter_keyword_summary
from .styles import SENTIMENT_COLORS


def render_keyword_summary(keyword_summary) -> None:
    st.subheader("Keyword/category sentiment summary")
    st.caption(
        "Compare customer sentiment across the Amazon search "
        "keywords used during data collection."
    )

    if keyword_summary.empty:
        st.info("No keyword summary data is available.")
        return

    filter_column, count_column = st.columns([2, 1])
    available = sorted(
        keyword_summary["category"].dropna().astype(str).unique()
    )
    with filter_column:
        selected = st.multiselect(
            "Select keywords",
            options=available,
            placeholder="Leave empty to include all keywords",
            key="keyword_summary_filter",
        )

    maximum = min(20, len(keyword_summary))
    with count_column:
        display_count = st.slider(
            "Keywords to display",
            min_value=1,
            max_value=maximum,
            value=min(10, maximum),
            key="keyword_display_count",
        )

    max_reviews = int(keyword_summary["review_count"].max())
    minimum_reviews = st.slider(
        "Minimum collected reviews",
        min_value=0,
        max_value=max_reviews,
        value=0,
        key="keyword_minimum_reviews",
    )

    filtered = filter_keyword_summary(
        keyword_summary,
        selected or None,
    )
    filtered = filtered[
        filtered["review_count"].ge(minimum_reviews)
    ].head(display_count).reset_index(drop=True)

    if filtered.empty:
        st.warning("No keywords match the selected filters.")
        return

    most_positive = filtered.sort_values(
        ["positive_percentage", "review_count"],
        ascending=[False, False],
    ).iloc[0]
    columns = st.columns(4)
    columns[0].metric("Keywords displayed", f"{len(filtered):,}")
    columns[1].metric(
        "Products represented",
        f"{int(filtered['product_count'].sum()):,}",
    )
    columns[2].metric(
        "Unique reviews",
        f"{int(filtered['review_count'].sum()):,}",
    )
    columns[3].metric(
        "Highest positive share",
        str(most_positive["category"]),
        delta=f"{float(most_positive['positive_percentage']):.1f}%",
        delta_color="off",
    )

    count_tab, percentage_tab = st.tabs(
        ["Review counts", "Sentiment percentages"]
    )
    with count_tab:
        _render_chart(filtered, "count", "Unique reviews")
    with percentage_tab:
        _render_chart(filtered, "percentage", "Percentage")

    table = filtered[
        [
            "category",
            "product_count",
            "review_count",
            "negative_percentage",
            "neutral_percentage",
            "positive_percentage",
            "dominant_sentiment",
        ]
    ].copy()
    table["dominant_sentiment"] = (
        table["dominant_sentiment"]
        .astype(str)
        .str.replace("_", " ", regex=False)
        .str.title()
    )
    table = table.rename(
        columns={
            "category": "Keyword",
            "product_count": "Products",
            "review_count": "Reviews",
            "negative_percentage": "Negative %",
            "neutral_percentage": "Neutral %",
            "positive_percentage": "Positive %",
            "dominant_sentiment": "Dominant Sentiment",
        }
    )
    st.subheader("Keyword comparison table")
    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        column_config={
            name: st.column_config.NumberColumn(format="%.2f%%")
            for name in ("Negative %", "Neutral %", "Positive %")
        },
    )
    st.caption(
        "Reviews shared across Amazon variants are counted only "
        "once inside each keyword summary."
    )
    st.download_button(
        "Download keyword summary",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="keyword_sentiment_summary.csv",
        mime="text/csv",
        key="download_keyword_summary",
    )


def _render_chart(data, value_type: str, axis_label: str) -> None:
    columns = [
        f"negative_{value_type}",
        f"neutral_{value_type}",
        f"positive_{value_type}",
    ]
    chart_data = data.melt(
        id_vars=["category"],
        value_vars=columns,
        var_name="sentiment",
        value_name="value",
    )
    chart_data["sentiment"] = chart_data["sentiment"].str.replace(
        f"_{value_type}", "", regex=False
    )
    figure = px.bar(
        chart_data,
        x="value",
        y="category",
        color="sentiment",
        orientation="h",
        barmode="stack",
        color_discrete_map=SENTIMENT_COLORS,
        labels={
            "category": "Keyword",
            "value": axis_label,
            "sentiment": "Sentiment",
        },
        category_orders={
            "category": list(reversed(data["category"].tolist()))
        },
    )
    figure.update_layout(
        height=max(420, len(data) * 42),
        margin=dict(l=20, r=20, t=20, b=20),
    )
    if value_type == "percentage":
        figure.update_xaxes(ticksuffix="%")
    st.plotly_chart(figure, use_container_width=True)
