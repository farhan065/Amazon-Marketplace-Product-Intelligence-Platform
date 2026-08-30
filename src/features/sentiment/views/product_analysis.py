import pandas as pd
import plotly.express as px
import streamlit as st

from ..analytics import (
    filter_products,
    get_product_details,
    get_product_reviews,
)
from .styles import SENTIMENT_COLORS


def _format_price(value) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value).strip() or "N/A"


def _format_confidence(value) -> str:
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "N/A"


def _render_product_identity(details: dict, asin: str) -> None:
    image_column, information_column = st.columns(
        [1, 3],
        gap="large",
    )

    with image_column:
        image_url = str(details.get("image_url", "")).strip()
        if image_url.startswith("http"):
            st.image(image_url, use_container_width=True)
        else:
            st.info("No product image is available.")

    with information_column:
        title = str(details.get("title", "Untitled product"))
        brand = str(details.get("brand", "Unknown brand")).strip()
        st.markdown(f"### {title}")
        st.write(f"**ASIN:** `{asin}`")
        st.write(f"**Brand:** {brand or 'Unknown brand'}")
        st.write(
            "**Keyword/category:** "
            f"{details.get('category', 'N/A')}"
        )
        st.write(f"**Price:** {_format_price(details.get('price'))}")

        product_url = str(details.get("product_url", "")).strip()
        if product_url.startswith("http"):
            st.link_button("View Amazon product", product_url)


def _render_product_metrics(details: dict) -> None:
    review_count = int(details.get("review_count", 0) or 0)
    positive_value = details.get("positive_percentage", 0)
    try:
        positive_display = f"{float(positive_value):.1f}%"
    except (TypeError, ValueError):
        positive_display = "0.0%"

    dominant = str(
        details.get("dominant_sentiment", "no_reviews")
    ).replace("_", " ").title()

    columns = st.columns(4)
    columns[0].metric("Collected reviews", f"{review_count:,}")
    columns[1].metric("Dominant sentiment", dominant)
    columns[2].metric("Positive share", positive_display)
    columns[3].metric(
        "Average confidence",
        _format_confidence(
            details.get("average_sentiment_confidence")
        ),
    )


def _render_product_distribution(details: dict) -> None:
    distribution = pd.DataFrame(
        {
            "sentiment": ["negative", "neutral", "positive"],
            "count": [
                int(details.get("negative_count", 0)),
                int(details.get("neutral_count", 0)),
                int(details.get("positive_count", 0)),
            ],
            "percentage": [
                details.get("negative_percentage", 0),
                details.get("neutral_percentage", 0),
                details.get("positive_percentage", 0),
            ],
        }
    )

    chart_column, table_column = st.columns([1.25, 1], gap="large")

    with chart_column:
        st.subheader("Product sentiment distribution")
        figure = px.pie(
            distribution,
            names="sentiment",
            values="count",
            hole=0.60,
            color="sentiment",
            color_discrete_map=SENTIMENT_COLORS,
        )
        figure.update_traces(
            textposition="outside",
            texttemplate="%{label}<br>%{percent:.1%}",
        )
        figure.update_layout(
            height=390,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(figure, use_container_width=True)

    with table_column:
        st.subheader("Sentiment breakdown")
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


def _render_review_table(reviews, selected_asin: str) -> None:
    st.divider()
    st.subheader("Individual reviews")

    sentiment_column, confidence_column = st.columns([2, 1])
    with sentiment_column:
        selected_sentiments = st.multiselect(
            "Sentiment filter",
            options=["negative", "neutral", "positive"],
            default=["negative", "neutral", "positive"],
            format_func=str.title,
            key="product_sentiment_filter",
        )
    with confidence_column:
        low_confidence_only = st.checkbox(
            "Low-confidence only",
            key="product_low_confidence",
        )

    selected_reviews = get_product_reviews(
        reviews=reviews,
        asin=selected_asin,
        sentiments=selected_sentiments,
        low_confidence_only=low_confidence_only,
    )
    st.caption(f"{len(selected_reviews):,} matching reviews")

    if selected_reviews.empty:
        st.info("No reviews match the selected filters.")
        return

    preferred_columns = [
        "review_id",
        "review_rating",
        "headline",
        "model_text",
        "sentiment_label",
        "sentiment_confidence",
        "sentiment_low_confidence",
    ]
    available_columns = [
        column
        for column in preferred_columns
        if column in selected_reviews.columns
    ]
    table = selected_reviews[available_columns].rename(
        columns={
            "review_id": "Review ID",
            "review_rating": "Rating",
            "headline": "Headline",
            "model_text": "Review Text",
            "sentiment_label": "Sentiment",
            "sentiment_confidence": "Confidence",
            "sentiment_low_confidence": "Low Confidence",
        }
    )
    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        height=430,
        column_config={
            "Confidence": st.column_config.ProgressColumn(
                min_value=0.0,
                max_value=1.0,
                format="%.2f",
            ),
            "Review Text": st.column_config.TextColumn(width="large"),
        },
    )
    st.download_button(
        "Download filtered reviews",
        data=selected_reviews.to_csv(index=False).encode("utf-8"),
        file_name=f"{selected_asin}_sentiment_reviews.csv",
        mime="text/csv",
        key="download_product_reviews",
    )


def render_product_analysis(reviews, products) -> None:
    st.subheader("Product-level sentiment analysis")
    st.caption(
        "Search for a product and inspect its customer "
        "sentiment, confidence and individual reviews."
    )

    filter_column, search_column = st.columns([1, 2])
    categories = sorted(products["category"].astype(str).unique())

    with filter_column:
        selected_category = st.selectbox(
            "Keyword/category",
            options=["All keywords", *categories],
            key="product_category_filter",
        )
    with search_column:
        search_text = st.text_input(
            "Search products",
            placeholder="Enter an ASIN, title or brand",
            key="product_search",
        )

    category = (
        None if selected_category == "All keywords" else selected_category
    )
    filtered = filter_products(products, category, search_text)
    st.caption(f"{len(filtered):,} products found")

    if filtered.empty:
        st.warning("No products match the selected filters.")
        return

    options = {}
    for _, row in filtered.iterrows():
        asin = str(row["asin"])
        title = str(row.get("title", "Untitled product")).strip()
        options[f"{(title or 'Untitled product')[:90]} — {asin}"] = asin

    selected_label = st.selectbox(
        "Select a product",
        options=list(options),
        key="selected_product",
    )
    selected_asin = options[selected_label]
    details = get_product_details(products, selected_asin)

    st.divider()
    _render_product_identity(details, selected_asin)
    _render_product_metrics(details)

    if not details.get("has_reviews", False):
        st.info(
            "This product has no collected reviews. "
            "Sentiment analysis is unavailable."
        )
        return

    st.divider()
    _render_product_distribution(details)
    _render_review_table(reviews, selected_asin)
