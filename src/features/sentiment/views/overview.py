import plotly.express as px
import streamlit as st

from ..analytics import (
    get_overview_distribution,
    get_overview_metrics,
)
from .styles import SENTIMENT_COLORS


def render_overview(reviews, products, keyword_summary) -> None:
    metrics = get_overview_metrics(reviews, products)
    distribution = get_overview_distribution(reviews)

    st.subheader("Marketplace overview")

    metric_columns = st.columns(5)
    metric_columns[0].metric(
        "Products",
        f"{metrics['total_products']:,}",
    )
    metric_columns[1].metric(
        "Unique reviews",
        f"{metrics['unique_reviews']:,}",
    )
    metric_columns[2].metric(
        "Positive reviews",
        f"{metrics['positive_percentage']:.1f}%",
    )
    metric_columns[3].metric(
        "Average confidence",
        f"{metrics['average_confidence']:.1%}",
    )
    metric_columns[4].metric(
        "Low-confidence reviews",
        f"{metrics['low_confidence_reviews']:,}",
    )

    chart_column, summary_column = st.columns(
        [1.35, 1],
        gap="large",
    )

    with chart_column:
        st.subheader("Overall sentiment distribution")
        figure = px.pie(
            distribution,
            names="sentiment",
            values="count",
            hole=0.62,
            color="sentiment",
            color_discrete_map=SENTIMENT_COLORS,
        )
        figure.update_traces(
            textposition="outside",
            texttemplate="%{label}<br>%{percent:.1%}",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Reviews: %{value:,}<br>"
                "Share: %{percent:.1%}<extra></extra>"
            ),
        )
        figure.update_layout(
            height=430,
            margin=dict(l=20, r=20, t=30, b=20),
        )
        st.plotly_chart(figure, use_container_width=True)

    with summary_column:
        st.subheader("Sentiment summary")
        table = distribution.copy()
        table["sentiment"] = table["sentiment"].str.title()
        table = table.rename(
            columns={
                "sentiment": "Sentiment",
                "count": "Reviews",
                "percentage": "Percentage",
            }
        )
        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Percentage": st.column_config.NumberColumn(
                    format="%.2f%%"
                )
            },
        )
        st.info(
            "Shared Amazon variant reviews are counted only "
            "once in the overview."
        )
        st.metric(
            "Dominant sentiment",
            metrics["dominant_sentiment"].title(),
        )

    st.divider()
    st.subheader("Most reviewed keywords")

    top_keywords = keyword_summary.nlargest(
        10,
        "review_count",
    ).copy()
    chart_data = top_keywords.melt(
        id_vars=["category"],
        value_vars=[
            "negative_count",
            "neutral_count",
            "positive_count",
        ],
        var_name="sentiment",
        value_name="reviews",
    )
    chart_data["sentiment"] = chart_data["sentiment"].str.replace(
        "_count",
        "",
        regex=False,
    )

    figure = px.bar(
        chart_data,
        x="category",
        y="reviews",
        color="sentiment",
        barmode="stack",
        color_discrete_map=SENTIMENT_COLORS,
        labels={
            "category": "Keyword",
            "reviews": "Unique reviews",
            "sentiment": "Sentiment",
        },
    )
    figure.update_layout(
        height=430,
        xaxis_tickangle=-30,
        margin=dict(l=20, r=20, t=20, b=80),
    )
    st.plotly_chart(figure, use_container_width=True)
