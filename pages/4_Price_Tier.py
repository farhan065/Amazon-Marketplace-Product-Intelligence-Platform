import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# Make project root importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from src.features.price_tier import (  # noqa: E402
    get_price_tier_overview,
    get_product_by_asin,
    load_price_tier_data,
    load_price_tier_metadata,
    predict_price_tier,
    search_price_tier_products,
)


st.set_page_config(
    page_title="Price Tier Classification",
    page_icon="💰",
    layout="wide",
)


TIER_ORDER = [
    "Budget",
    "Mid-range",
    "Premium",
]

TIER_COLORS = {
    "Budget": "#10B981",
    "Mid-range": "#F59E0B",
    "Premium": "#8B5CF6",
}


st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        div[data-testid="stMetric"] {
            background: rgba(120, 120, 120, 0.06);
            border: 1px solid rgba(120, 120, 120, 0.18);
            border-radius: 14px;
            padding: 16px;
        }

        .price-header {
            padding: 22px 26px;
            border-radius: 18px;
            margin-bottom: 22px;
            background: linear-gradient(
                120deg,
                rgba(16, 185, 129, 0.16),
                rgba(245, 158, 11, 0.12),
                rgba(139, 92, 246, 0.16)
            );
            border: 1px solid rgba(139, 92, 246, 0.22);
        }

        .price-header h1 {
            margin: 0;
            font-size: 2.1rem;
        }

        .price-header p {
            margin: 8px 0 0;
            opacity: 0.78;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <section class="price-header">
        <h1>💰 Price Tier Classification</h1>
        <p>
            Classify products as Budget, Mid-range or Premium
            using product attributes. Product price is excluded
            from the prediction model.
        </p>
    </section>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def get_application_data():
    return (
        load_price_tier_data(),
        get_price_tier_overview(),
        load_price_tier_metadata(),
    )


def safe_text(
    value,
    default="Not available",
):
    if value is None or pd.isna(value):
        return default

    text = str(value).strip()

    if text.lower() in {
        "",
        "nan",
        "none",
        "unknown",
    }:
        return default

    return text


def product_option(
    asin,
    product_lookup,
):
    title = safe_text(
        product_lookup[asin].get("title"),
        "Untitled product",
    )

    if len(title) > 65:
        title = title[:62] + "..."

    return f"{asin} — {title}"


def probability_table(result):
    return pd.DataFrame(
        {
            "Price tier": TIER_ORDER,
            "Probability": [
                float(
                    result[
                        "budget_probability"
                    ]
                ),
                float(
                    result[
                        "mid_range_probability"
                    ]
                ),
                float(
                    result[
                        "premium_probability"
                    ]
                ),
            ],
        }
    )


def show_probability_chart(result):
    probabilities = probability_table(
        result
    )

    figure = px.bar(
        probabilities,
        x="Price tier",
        y="Probability",
        color="Price tier",
        color_discrete_map=TIER_COLORS,
        category_orders={
            "Price tier": TIER_ORDER
        },
        text=probabilities[
            "Probability"
        ].map(
            lambda value: f"{value:.1%}"
        ),
    )

    figure.update_traces(
        textposition="outside"
    )

    figure.update_layout(
        showlegend=False,
        height=350,
        xaxis_title=None,
        yaxis_title="Predicted probability",
        yaxis_tickformat=".0%",
        yaxis_range=[0, 1.08],
        margin=dict(
            l=20,
            r=20,
            t=30,
            b=20,
        ),
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
    )


try:
    with st.spinner(
        "Loading Price Tier data..."
    ):
        products, overview, metadata = (
            get_application_data()
        )
except (
    FileNotFoundError,
    OSError,
    ValueError,
) as error:
    st.error(
        "Price Tier application data could not be loaded."
    )
    st.code(str(error))
    st.info(
        "Confirm that the Step 6 files are available "
        "inside data/processed and models/price_tier."
    )
    st.stop()


overview_tab, classification_tab, explorer_tab = (
    st.tabs(
        [
            "Tier Overview",
            "Product Classification",
            "Tier Explorer",
        ]
    )
)


# ============================================================
# Tab 1: Tier Overview
# ============================================================

with overview_tab:
    st.subheader("Price tier overview")

    dominant_tier = (
        overview.sort_values(
            "product_count",
            ascending=False,
        )
        .iloc[0][
            "predicted_price_tier"
        ]
    )

    average_confidence = products[
        "prediction_confidence"
    ].mean()

    metric_one, metric_two, metric_three = (
        st.columns(3)
    )

    metric_one.metric(
        "Classified products",
        f"{len(products):,}",
    )

    metric_two.metric(
        "Largest tier",
        dominant_tier,
    )

    metric_three.metric(
        "Average confidence",
        f"{average_confidence:.1%}",
    )

    chart_column, table_column = st.columns(
        [1.5, 1],
        gap="large",
    )

    with chart_column:
        figure = px.bar(
            overview,
            x="predicted_price_tier",
            y="product_count",
            color="predicted_price_tier",
            color_discrete_map=TIER_COLORS,
            category_orders={
                "predicted_price_tier": (
                    TIER_ORDER
                )
            },
            text="product_count",
            labels={
                "predicted_price_tier": (
                    "Price tier"
                ),
                "product_count": (
                    "Products"
                ),
            },
        )

        figure.update_layout(
            showlegend=False,
            height=400,
            xaxis_title=None,
            margin=dict(
                l=20,
                r=20,
                t=30,
                b=20,
            ),
        )

        st.plotly_chart(
            figure,
            use_container_width=True,
        )

    with table_column:
        overview_display = (
            overview.copy()
        )

        overview_display[
            "average_confidence"
        ] = overview_display[
            "average_confidence"
        ].map(
            lambda value: f"{value:.1%}"
        )

        overview_display[
            "share_percentage"
        ] = overview_display[
            "share_percentage"
        ].map(
            lambda value: f"{value:.1f}%"
        )

        overview_display = (
            overview_display.rename(
                columns={
                    "predicted_price_tier": (
                        "Price tier"
                    ),
                    "product_count": (
                        "Products"
                    ),
                    "average_confidence": (
                        "Average confidence"
                    ),
                    "share_percentage": (
                        "Catalogue share"
                    ),
                }
            )
        )

        st.dataframe(
            overview_display,
            hide_index=True,
            use_container_width=True,
        )

    selected_method = (
        metadata
        .get(
            "model_decision",
            {},
        )
        .get(
            "selected_method",
            "Selected classification model",
        )
    )

    st.info(
        f"Model: {selected_method}. Prices were used only "
        "to create training labels. Price is not included "
        "in the prediction features."
    )


# ============================================================
# Tab 2: Product Classification
# ============================================================

with classification_tab:
    st.subheader("Classify a product")

    classification_mode = st.radio(
        "Choose classification mode",
        [
            "Existing product",
            "Custom product",
        ],
        horizontal=True,
    )

    if classification_mode == (
        "Existing product"
    ):
        product_lookup = (
            products
            .set_index("asin")
            .to_dict(orient="index")
        )

        selected_asin = st.selectbox(
            "Select product",
            options=sorted(
                product_lookup.keys()
            ),
            format_func=lambda asin: (
                product_option(
                    asin,
                    product_lookup,
                )
            ),
        )

        product = get_product_by_asin(
            selected_asin
        )

        st.markdown(
            f"### {safe_text(product.get('title'))}"
        )

        st.caption(
            f"ASIN: {selected_asin}"
        )

        metric_one, metric_two, metric_three = (
            st.columns(3)
        )

        metric_one.metric(
            "Predicted tier",
            product[
                "predicted_price_tier"
            ],
        )

        metric_two.metric(
            "Confidence",
            (
                f"{product['prediction_confidence']:.1%}"
            ),
        )

        metric_three.metric(
            "Brand",
            safe_text(
                product.get("brand")
            ),
        )

        show_probability_chart(
            product
        )

        st.markdown(
            "#### Classification explanation"
        )

        st.info(
            safe_text(
                product.get(
                    "prediction_reason"
                ),
                (
                    "No classification explanation "
                    "is available."
                ),
            )
        )

        detail_one, detail_two, detail_three = (
            st.columns(3)
        )

        detail_one.write("**Keyword**")
        detail_one.write(
            safe_text(
                product.get("keyword")
            )
        )

        detail_two.write("**Review count**")
        detail_two.write(
            safe_text(
                product.get("review_count")
            )
        )

        detail_three.write("**Average rating**")
        detail_three.write(
            safe_text(
                product.get("average_rating")
            )
        )

        st.caption(
            "Any displayed product price is reference data only. "
            "It was not provided to the model."
        )

    else:
        st.caption(
            "No price field is provided because price is "
            "intentionally excluded from model features."
        )

        with st.form(
            "custom_price_tier_form"
        ):
            title = st.text_input(
                "Product title"
            )

            description = st.text_area(
                "Product description",
                height=120,
            )

            left_column, right_column = (
                st.columns(2)
            )

            with left_column:
                brand = st.text_input(
                    "Brand"
                )

                keyword = st.text_input(
                    "Collection keyword"
                )

                marketplace = st.text_input(
                    "Marketplace",
                    value="Amazon",
                )

            with right_column:
                review_count = st.text_input(
                    "Review count",
                    help=(
                        "A negative scraped review count "
                        "is converted to its absolute value."
                    ),
                )

                average_rating = st.text_input(
                    "Average rating",
                    help=(
                        "Examples: 4.5 or "
                        "'4.5 out of 5'."
                    ),
                )

            classify_button = (
                st.form_submit_button(
                    "Classify product",
                    type="primary",
                    use_container_width=True,
                )
            )

        if classify_button:
            has_information = any(
                str(value).strip()
                for value in [
                    title,
                    description,
                    brand,
                    keyword,
                ]
            )

            if not has_information:
                st.warning(
                    "Provide at least a title, description, "
                    "brand or collection keyword."
                )
            else:
                try:
                    with st.spinner(
                        "Classifying product..."
                    ):
                        result = (
                            predict_price_tier(
                                title=title,
                                description=(
                                    description
                                ),
                                brand=brand,
                                keyword=keyword,
                                marketplace=(
                                    marketplace
                                ),
                                review_count=(
                                    review_count
                                ),
                                average_rating=(
                                    average_rating
                                ),
                            )
                        )
                except Exception as error:
                    st.error(
                        "The product could not be classified."
                    )
                    st.code(str(error))
                else:
                    result_one, result_two = (
                        st.columns(2)
                    )

                    result_one.metric(
                        "Predicted tier",
                        result[
                            "predicted_price_tier"
                        ],
                    )

                    result_two.metric(
                        "Confidence",
                        (
                            f"{result['prediction_confidence']:.1%}"
                        ),
                    )

                    show_probability_chart(
                        result
                    )

                    st.info(
                        result[
                            "prediction_reason"
                        ]
                    )


# ============================================================
# Tab 3: Tier Explorer
# ============================================================

with explorer_tab:
    st.subheader(
        "Explore classified products"
    )

    filter_one, filter_two, filter_three = (
        st.columns([1, 1, 2])
    )

    with filter_one:
        selected_tier = st.selectbox(
            "Price tier",
            [
                "All",
                "Budget",
                "Mid-range",
                "Premium",
            ],
        )

    available_keywords = ["All"]

    if "keyword" in products.columns:
        keywords = (
            products["keyword"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        keywords = sorted(
            keywords[
                keywords.ne("")
            ]
            .unique()
            .tolist()
        )

        available_keywords.extend(
            keywords
        )

    with filter_two:
        selected_keyword = st.selectbox(
            "Collection keyword",
            available_keywords,
        )

    with filter_three:
        search_query = st.text_input(
            "Search ASIN, title or brand"
        )

    result_limit = st.slider(
        "Maximum products",
        min_value=10,
        max_value=100,
        value=30,
        step=10,
    )

    filtered_products = (
        search_price_tier_products(
            query=search_query,
            tier=selected_tier,
            keyword=selected_keyword,
            limit=result_limit,
        )
    )

    st.write(
        f"Showing **{len(filtered_products):,}** products"
    )

    display_columns = [
        column
        for column in [
            "asin",
            "title",
            "brand",
            "keyword",
            "predicted_price_tier",
            "prediction_confidence",
            "review_count",
            "average_rating",
            "price",
        ]
        if column in filtered_products.columns
    ]

    explorer_display = (
        filtered_products[
            display_columns
        ].copy()
    )

    if "prediction_confidence" in (
        explorer_display.columns
    ):
        explorer_display[
            "prediction_confidence"
        ] = explorer_display[
            "prediction_confidence"
        ].map(
            lambda value: f"{value:.1%}"
        )

    explorer_display = (
        explorer_display.rename(
            columns={
                "asin": "ASIN",
                "title": "Title",
                "brand": "Brand",
                "keyword": "Keyword",
                "predicted_price_tier": (
                    "Predicted tier"
                ),
                "prediction_confidence": (
                    "Confidence"
                ),
                "review_count": (
                    "Review count"
                ),
                "average_rating": (
                    "Rating"
                ),
                "price": (
                    "Reference price"
                ),
            }
        )
    )

    st.dataframe(
        explorer_display,
        hide_index=True,
        use_container_width=True,
    )

    if "price" in filtered_products.columns:
        st.caption(
            "Reference price is displayed only for context "
            "and was not used by the model."
        )