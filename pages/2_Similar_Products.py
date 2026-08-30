# ============================================================
# Similar Product Recommendation Page
# ============================================================

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


# ------------------------------------------------------------
# Project imports
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from src.features.recommendation import (  # noqa: E402
    get_product_by_asin,
    recommend_by_asin,
    search_products,
)


# ------------------------------------------------------------
# Page configuration
# ------------------------------------------------------------

st.set_page_config(
    page_title="Similar Product Intelligence",
    page_icon="🔎",
    layout="wide",
)


# ------------------------------------------------------------
# Page styling
# ------------------------------------------------------------

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

        .recommendation-header {
            padding: 22px 26px;
            border-radius: 18px;
            margin-bottom: 22px;
            background: linear-gradient(
                120deg,
                rgba(37, 99, 235, 0.18),
                rgba(124, 58, 237, 0.12)
            );
            border: 1px solid rgba(59, 130, 246, 0.22);
        }

        .recommendation-header h1 {
            margin: 0;
            font-size: 2.1rem;
        }

        .recommendation-header p {
            margin: 8px 0 0;
            opacity: 0.78;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# Navigation and header
# ------------------------------------------------------------

st.page_link(
    "app.py",
    label="Home",
    icon="🏠",
)

st.markdown(
    """
    <div class="recommendation-header">
        <h1>Similar Product Intelligence</h1>
        <p>
            Search the product catalogue and discover comparable
            products using explainable TF-IDF recommendations.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# Display helpers
# ------------------------------------------------------------

INVALID_VALUES = {
    "",
    "nan",
    "none",
    "unknown",
}


def display_text(
    value,
    default="Not available",
):
    if pd.isna(value):
        return default

    value = str(value).strip()

    if value.lower() in INVALID_VALUES:
        return default

    return value


def valid_url(value):
    if pd.isna(value):
        return False

    return str(value).strip().startswith(
        ("http://", "https://")
    )


def format_product_option(
    asin,
    product_lookup,
):
    product = product_lookup[asin]

    title = display_text(
        product.get("title"),
        "Untitled product",
    )

    if len(title) > 80:
        title = title[:77] + "..."

    return f"{title} — {asin}"


# ------------------------------------------------------------
# Product search
# ------------------------------------------------------------

st.subheader("Select a product")

search_query = st.text_input(
    "Search the catalogue",
    placeholder=(
        "Search by product title, ASIN, brand or keyword"
    ),
)

try:
    with st.spinner(
        "Please wait while the product catalogue "
        "is loading..."
    ):
        search_results = search_products(
            query=search_query,
            limit=50,
        )

except (
    FileNotFoundError,
    OSError,
    ValueError,
) as error:
    st.error(
        "The recommendation catalogue could not be loaded."
    )

    st.code(str(error))

    st.info(
        "Confirm that the four final recommendation "
        "artifacts exist inside models/recommendation."
    )

    st.stop()


if search_results.empty:
    st.warning(
        "No products matched your search. Try another "
        "title, brand, ASIN or keyword."
    )

    st.stop()


product_lookup = {
    str(row["asin"]): row
    for _, row in search_results.iterrows()
}

product_options = list(
    product_lookup.keys()
)

selected_asin = st.selectbox(
    "Choose a product",
    options=product_options,
    format_func=lambda asin: (
        format_product_option(
            asin,
            product_lookup,
        )
    ),
)


# ------------------------------------------------------------
# Selected product overview
# ------------------------------------------------------------

try:
    selected_product = get_product_by_asin(
        selected_asin
    )

except ValueError as error:
    st.error(str(error))
    st.stop()


st.subheader("Selected product")

image_column, information_column = st.columns(
    [1, 3],
    gap="large",
)

with image_column:
    selected_image_url = (
        selected_product.get(
            "image_url",
            "",
        )
    )

    if valid_url(selected_image_url):
        st.image(
            selected_image_url,
            use_container_width=True,
        )
    else:
        st.info(
            "Product image unavailable."
        )


with information_column:
    st.markdown(
        "### "
        + display_text(
            selected_product.get("title")
        )
    )

    detail_columns = st.columns(3)

    with detail_columns[0]:
        st.metric(
            "Brand",
            display_text(
                selected_product.get("brand")
            ),
        )

    with detail_columns[1]:
        st.metric(
            "Rating",
            display_text(
                selected_product.get(
                    "avg_rating"
                )
            ),
        )

    with detail_columns[2]:
        st.metric(
            "Price",
            display_text(
                selected_product.get("price")
            ),
        )

    st.caption(
        "Product group: "
        + display_text(
            selected_product.get(
                "keyword_list"
            )
        )
    )

    selected_product_url = (
        selected_product.get(
            "product_url",
            "",
        )
    )

    if valid_url(selected_product_url):
        st.link_button(
            "View selected product",
            selected_product_url,
        )


# ------------------------------------------------------------
# Recommendation controls
# ------------------------------------------------------------

st.divider()

control_column, button_column = st.columns(
    [1, 2]
)

with control_column:
    top_k = st.slider(
        "Number of recommendations",
        min_value=3,
        max_value=10,
        value=5,
    )


with button_column:
    st.write("")

    generate_recommendations = st.button(
        "Find similar products",
        type="primary",
        use_container_width=True,
    )


# ------------------------------------------------------------
# Generate recommendations
# ------------------------------------------------------------

if generate_recommendations:
    try:
        with st.spinner(
            "Finding the most similar products. "
            "Please wait a few seconds..."
        ):
            recommendation_results = (
                recommend_by_asin(
                    selected_asin,
                    top_k=top_k,
                )
            )

        st.session_state[
            "recommendation_results"
        ] = recommendation_results

        st.session_state[
            "recommendation_source_asin"
        ] = selected_asin

    except (
        FileNotFoundError,
        OSError,
        ValueError,
    ) as error:
        st.error(
            "Recommendations could not be generated."
        )

        st.code(str(error))


saved_results = st.session_state.get(
    "recommendation_results"
)

saved_source_asin = st.session_state.get(
    "recommendation_source_asin"
)


# ------------------------------------------------------------
# Recommendation results
# ------------------------------------------------------------

if (
    saved_results is not None
    and saved_source_asin == selected_asin
):
    st.subheader("Recommended products")

    st.caption(
        f"Showing {len(saved_results)} products "
        "ranked by TF-IDF content similarity."
    )

    result_columns = st.columns(
        2,
        gap="large",
    )

    for position, (_, product) in enumerate(
        saved_results.iterrows()
    ):
        with result_columns[position % 2]:

            with st.container(border=True):

                image_url = product.get(
                    "image_url",
                    "",
                )

                if valid_url(image_url):
                    st.image(
                        image_url,
                        use_container_width=True,
                    )
                else:
                    st.info(
                        "Product image unavailable."
                    )

                st.markdown(
                    f"#### {int(product['rank'])}. "
                    + display_text(
                        product.get("title")
                    )
                )

                information_columns = (
                    st.columns(3)
                )

                with information_columns[0]:
                    st.caption("Brand")

                    st.write(
                        display_text(
                            product.get("brand")
                        )
                    )

                with information_columns[1]:
                    st.caption("Rating")

                    st.write(
                        display_text(
                            product.get(
                                "avg_rating"
                            )
                        )
                    )

                with information_columns[2]:
                    st.caption("Price")

                    st.write(
                        display_text(
                            product.get("price")
                        )
                    )

                similarity_score = float(
                    product[
                        "similarity_score"
                    ]
                )

                safe_similarity_score = max(
                    0.0,
                    min(
                        similarity_score,
                        1.0,
                    ),
                )

                st.caption(
                    "TF-IDF similarity score"
                )

                st.progress(
                    safe_similarity_score
                )

                st.write(
                    f"**Score:** "
                    f"{similarity_score:.4f}"
                )

                st.info(
                    "**Why recommended:** "
                    + display_text(
                        product.get(
                            "recommendation_reason"
                        )
                    )
                )

                product_url = product.get(
                    "product_url",
                    "",
                )

                if valid_url(product_url):
                    st.link_button(
                        "View on Amazon",
                        product_url,
                        use_container_width=True,
                    )


elif saved_results is not None:
    st.info(
        "The selected product has changed. "
        "Click “Find similar products” to generate "
        "new recommendations."
    )


else:
    st.info(
        "Select a product and click "
        "“Find similar products” to begin."
    )