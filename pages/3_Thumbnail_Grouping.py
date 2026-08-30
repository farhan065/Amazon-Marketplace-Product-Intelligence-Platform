# ============================================================
# Thumbnail Grouping Streamlit Page
# ============================================================

import sys
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st


# Make the project root importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from src.features.thumbnail_grouping import (  # noqa: E402
    get_similar_thumbnails,
    get_thumbnail_metadata,
    get_thumbnail_product,
    get_thumbnail_source,
    get_visual_group_interpretation,
    get_visual_group_overview,
    get_visual_group_products,
    load_thumbnail_data,
    search_thumbnail_products,
)


# ============================================================
# Page configuration
# ============================================================

st.set_page_config(
    page_title="Thumbnail Grouping",
    page_icon="🖼️",
    layout="wide",
)


st.markdown(
    """
    <style>
        .block-container {
            max-width: 1220px;
            padding-top: 1.8rem;
            padding-bottom: 3rem;
        }

        .thumbnail-hero {
            padding: 2rem 2.2rem;
            margin-bottom: 1.5rem;
            border-radius: 20px;
            color: white;
            background:
                linear-gradient(
                    125deg,
                    #312e81,
                    #2563eb 58%,
                    #0891b2
                );
            box-shadow:
                0 16px 40px
                rgba(37, 99, 235, 0.20);
        }

        .thumbnail-hero h1 {
            margin: 0 0 0.45rem;
            font-size: 2.25rem;
        }

        .thumbnail-hero p {
            margin: 0;
            opacity: 0.9;
            font-size: 1.02rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 15px;
        }

        .group-note {
            padding: 0.8rem 1rem;
            border-left: 4px solid #2563eb;
            border-radius: 8px;
            background: rgba(37, 99, 235, 0.08);
            margin: 0.7rem 0 1rem;
        }

        .visual-group-badge {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.6rem;
            padding: 0.65rem 0.8rem;
            margin: 0.65rem 0;
            border-radius: 9px;
            background: rgba(37, 99, 235, 0.12);
            border: 1px solid rgba(59, 130, 246, 0.30);
        }

        .visual-group-badge span {
            font-size: 0.84rem;
            opacity: 0.75;
        }

        .visual-group-badge strong {
            color: #60a5fa;
            white-space: nowrap;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# Display helpers
# ============================================================

INVALID_VALUES = {
    "",
    "nan",
    "none",
    "unknown",
    "unavailable",
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


def display_number(
    value,
    decimals=3,
    default="N/A",
):
    try:
        if pd.isna(value):
            return default

        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return default


def display_percentage(
    value,
    decimals=1,
    default="N/A",
):
    try:
        if pd.isna(value):
            return default

        return f"{float(value):.{decimals}%}"
    except (TypeError, ValueError):
        return default


def valid_url(value):
    if pd.isna(value):
        return False

    return str(value).strip().startswith(
        ("http://", "https://")
    )


def shorten_text(
    value,
    maximum_length=75,
):
    value = display_text(
        value,
        "Untitled product",
    )

    if len(value) <= maximum_length:
        return value

    return (
        value[: maximum_length - 3]
        + "..."
    )


def format_product_option(
    asin,
    product_lookup,
):
    product = product_lookup[asin]

    title = shorten_text(
        product.get("title"),
        80,
    )

    return f"{title} — {asin}"


def render_product_image(
    product,
    caption=None,
):
    image_source = get_thumbnail_source(
        product
    )

    if image_source:
        st.image(
            image_source,
            caption=caption,
            use_container_width=True,
        )
    else:
        st.info(
            "Thumbnail unavailable."
        )


def render_product_link(product):
    product_url = product.get(
        "product_url",
        "",
    )

    if valid_url(product_url):
        st.link_button(
            "View product",
            str(product_url).strip(),
            use_container_width=True,
        )


def render_visual_group_badge(group_name):
    safe_group_name = escape(
        display_text(group_name)
    )

    st.markdown(
        f"""
        <div class="visual-group-badge">
            <span>Visual group</span>
            <strong>{safe_group_name}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Cached application loading
# ============================================================

@st.cache_resource(show_spinner=False)
def load_thumbnail_application():
    load_thumbnail_data()

    metadata = get_thumbnail_metadata()
    overview = get_visual_group_overview()

    return metadata, overview


# ============================================================
# Header and initial loading
# ============================================================

st.markdown(
    """
    <section class="thumbnail-hero">
        <h1>🖼️ Thumbnail Grouping</h1>
        <p>
            Explore visually similar Amazon product thumbnails
            discovered using DINOv2, PCA and KMeans clustering.
        </p>
    </section>
    """,
    unsafe_allow_html=True,
)


try:
    with st.spinner(
        "Please wait a few seconds while thumbnail "
        "groups are loading..."
    ):
        metadata, group_overview = (
            load_thumbnail_application()
        )

except (
    FileNotFoundError,
    OSError,
    ValueError,
    KeyError,
) as error:
    st.error(
        "The thumbnail-grouping application data "
        "could not be loaded."
    )

    st.code(
        str(error)
    )

    st.info(
        "Confirm that the thumbnail model artifacts are "
        "inside models/thumbnail_grouping and the prepared "
        "CSV files are inside data/processed."
    )

    st.stop()


# ============================================================
# Main sections
# ============================================================

overview_tab, explorer_tab, similar_tab = st.tabs(
    [
        "📊 Visual Overview",
        "🗂️ Group Explorer",
        "🔎 Similar Thumbnails",
    ]
)


# ============================================================
# Tab 1: Visual Overview
# ============================================================

with overview_tab:
    st.subheader(
        "Visual grouping overview"
    )

    st.caption(
        "The groups were created using image embeddings only. "
        "Titles, keywords, brands and categories were not used "
        "during clustering."
    )

    metric_columns = st.columns(4)

    with metric_columns[0]:
        st.metric(
            "Products",
            int(
                metadata.get(
                    "product_count",
                    981,
                )
            ),
        )

    with metric_columns[1]:
        st.metric(
            "Unique images",
            int(
                metadata.get(
                    "unique_image_count",
                    979,
                )
            ),
        )

    with metric_columns[2]:
        st.metric(
            "Visual groups",
            int(
                metadata.get(
                    "selected_k",
                    len(group_overview),
                )
            ),
        )

    with metric_columns[3]:
        st.metric(
            "Silhouette score",
            display_number(
                metadata.get(
                    "cosine_silhouette_score",
                    0.4229,
                ),
                decimals=4,
            ),
        )

    st.divider()

    chart_column, explanation_column = st.columns(
        [2, 1],
        gap="large",
    )

    with chart_column:
        st.markdown(
            "#### Products per visual group"
        )

        chart_data = (
            group_overview[
                [
                    "cluster_name",
                    "product_count",
                ]
            ]
            .set_index("cluster_name")
        )

        st.bar_chart(
            chart_data,
            use_container_width=True,
        )

    with explanation_column:
        st.markdown(
            "#### Model decision"
        )

        st.markdown(
            """
            - **Extractor:** DINOv2-Small
            - **PCA dimensions:** 171
            - **Algorithm:** KMeans
            - **Selected groups:** 26
            - **Elbow reference:** 13
            """
        )

        st.markdown(
            """
            <div class="group-note">
                K=26 was selected because it produced the
                highest cosine Silhouette Score among the
                evaluated configurations.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "#### Group quality summary"
    )

    overview_columns = [
        column
        for column in [
            "cluster_name",
            "product_count",
            "average_silhouette",
            "negative_silhouette_share",
            "average_centroid_similarity",
            "visual_cohesion",
        ]
        if column in group_overview.columns
    ]

    overview_display = group_overview[
        overview_columns
    ].copy()

    overview_display = overview_display.rename(
        columns={
            "cluster_name": "Visual group",
            "product_count": "Products",
            "average_silhouette": "Average silhouette",
            "negative_silhouette_share": "Negative share",
            "average_centroid_similarity": (
                "Centroid similarity"
            ),
            "visual_cohesion": "Visual cohesion",
        }
    )

    if "Negative share" in overview_display.columns:
        overview_display["Negative share"] = (
            overview_display["Negative share"]
            * 100
        )

    st.dataframe(
        overview_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Average silhouette": (
                st.column_config.NumberColumn(
                    format="%.3f"
                )
            ),
            "Negative share": (
                st.column_config.NumberColumn(
                    format="%.1f%%"
                )
            ),
            "Centroid similarity": (
                st.column_config.NumberColumn(
                    format="%.3f"
                )
            ),
        },
    )

    st.info(
        "These groups represent recurring visual patterns such "
        "as shape, color, composition, background, packaging "
        "and camera angle. They are not official product categories."
    )


# ============================================================
# Tab 2: Group Explorer
# ============================================================

with explorer_tab:
    st.subheader(
        "Explore a visual group"
    )

    st.caption(
        "Select a group to inspect its interpretation and "
        "representative product thumbnails."
    )

    group_lookup = {
        int(row["cluster_id"]): row
        for _, row in group_overview.iterrows()
    }

    group_options = list(
        group_lookup.keys()
    )

    def format_group_option(cluster_id):
        group = group_lookup[cluster_id]

        return (
            f"{group['cluster_name']} "
            f"— {int(group['product_count'])} products"
        )

    control_column, limit_column = st.columns(
        [2, 1]
    )

    with control_column:
        selected_cluster_id = st.selectbox(
            "Choose a visual group",
            options=group_options,
            format_func=format_group_option,
        )

    with limit_column:
        group_display_limit = st.slider(
            "Thumbnails to display",
            min_value=4,
            max_value=24,
            value=12,
            step=4,
        )

    try:
        with st.spinner(
            "Loading the selected visual group..."
        ):
            selected_interpretation = (
                get_visual_group_interpretation(
                    selected_cluster_id
                )
            )

            selected_group_products = (
                get_visual_group_products(
                    selected_cluster_id,
                    limit=group_display_limit,
                )
            )

    except (
        KeyError,
        ValueError,
        OSError,
    ) as error:
        st.error(
            "The selected visual group could not be loaded."
        )
        st.code(str(error))
        st.stop()

    selected_group_summary = group_lookup[
        selected_cluster_id
    ]

    st.markdown(
        f"### {display_text(selected_interpretation.get('cluster_name'))}"
    )

    quality_columns = st.columns(4)

    with quality_columns[0]:
        st.metric(
            "Products",
            int(
                selected_group_summary[
                    "product_count"
                ]
            ),
        )

    with quality_columns[1]:
        st.metric(
            "Average silhouette",
            display_number(
                selected_interpretation.get(
                    "average_silhouette"
                )
            ),
        )

    with quality_columns[2]:
        st.metric(
            "Centroid similarity",
            display_number(
                selected_interpretation.get(
                    "average_centroid_similarity"
                )
            ),
        )

    with quality_columns[3]:
        st.metric(
            "Visual cohesion",
            display_text(
                selected_interpretation.get(
                    "visual_cohesion"
                )
            ).title(),
        )

    interpretation_text = display_text(
        selected_interpretation.get(
            "interpretation"
        ),
        (
            "The interpretation is unavailable for "
            "this visual group."
        ),
    )

    st.info(
        interpretation_text
    )

    evidence_column, audit_column = st.columns(
        2,
        gap="large",
    )

    with evidence_column:
        st.markdown(
            "#### Visual evidence"
        )

        st.write(
            "**Common title terms:** "
            + display_text(
                selected_interpretation.get(
                    "common_title_terms"
                )
            )
        )

        st.write(
            "**Negative silhouette share:** "
            + display_percentage(
                selected_interpretation.get(
                    "negative_silhouette_share"
                )
            )
        )

    with audit_column:
        st.markdown(
            "#### Post-clustering audit"
        )

        st.write(
            "**Most frequent keyword:** "
            + display_text(
                selected_interpretation.get(
                    "dominant_keyword_audit"
                )
            )
        )

        st.write(
            "**Keyword share:** "
            + display_percentage(
                selected_interpretation.get(
                    "dominant_keyword_share"
                )
            )
        )

        st.caption(
            "Keyword information was used only after "
            "clustering to explain the result."
        )

    st.divider()

    st.markdown(
        "#### Representative thumbnails"
    )

    if selected_group_products.empty:
        st.warning(
            "No products were found in this visual group."
        )
    else:
        products_per_row = 4

        for start_index in range(
            0,
            len(selected_group_products),
            products_per_row,
        ):
            product_columns = st.columns(
                products_per_row,
                gap="medium",
            )

            current_products = (
                selected_group_products.iloc[
                    start_index:
                    start_index + products_per_row
                ]
            )

            for product_column, (_, product) in zip(
                product_columns,
                current_products.iterrows(),
            ):
                with product_column:
                    with st.container(border=True):
                        render_product_image(
                            product
                        )

                        st.markdown(
                            "##### "
                            + shorten_text(
                                product.get("title"),
                                65,
                            )
                        )

                        st.caption(
                            f"ASIN: {product['asin']}"
                        )

                        st.write(
                            "**Brand:** "
                            + display_text(
                                product.get("brand")
                            )
                        )

                        st.write(
                            "**Centroid similarity:** "
                            + display_number(
                                product.get(
                                    "centroid_similarity"
                                )
                            )
                        )

                        render_product_link(
                            product
                        )


# ============================================================
# Tab 3: Similar Thumbnails
# ============================================================

with similar_tab:
    st.subheader(
        "Find visually similar thumbnails"
    )

    st.caption(
        "Choose an existing product to retrieve thumbnails "
        "with the nearest visual embeddings."
    )

    search_query = st.text_input(
        "Search the product catalogue",
        placeholder=(
            "Search by title, ASIN, brand, keyword "
            "or visual group"
        ),
        key="thumbnail_product_search",
    )

    search_results = search_thumbnail_products(
        query=search_query,
        limit=50,
    )

    if search_results.empty:
        st.warning(
            "No products matched your search."
        )
    else:
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
            format_func=lambda asin: format_product_option(
                asin,
                product_lookup,
            ),
            key="thumbnail_selected_product",
        )

        selected_product = get_thumbnail_product(
            selected_asin
        )

        selected_image_column, selected_info_column = (
            st.columns(
                [1, 3],
                gap="large",
            )
        )

        with selected_image_column:
            render_product_image(
                selected_product,
                caption=selected_product["asin"],
            )

        with selected_info_column:
            st.markdown(
                "### "
                + display_text(
                    selected_product.get("title"),
                    "Untitled product",
                )
            )

            selected_metrics = st.columns(2)

            with selected_metrics[0]:
                st.metric(
                    "Brand",
                    display_text(
                        selected_product.get(
                            "brand"
                        )
                    ),
                )

            with selected_metrics[1]:
                st.metric(
                    "Centroid similarity",
                    display_number(
                        selected_product.get(
                            "centroid_similarity"
                        )
                    ),
                )

            render_visual_group_badge(
                selected_product.get(
                    "cluster_name"
                )
            )

            st.caption(
                "Product keyword: "
                + display_text(
                    selected_product.get(
                        "keyword_list"
                    )
                )
            )

            render_product_link(
                selected_product
            )

        st.divider()

        control_column, button_column = st.columns(
            [1, 2]
        )

        with control_column:
            top_k = st.slider(
                "Number of similar thumbnails",
                min_value=3,
                max_value=12,
                value=6,
                key="thumbnail_top_k",
            )

        with button_column:
            st.write("")

            find_similar = st.button(
                "Find similar thumbnails",
                type="primary",
                use_container_width=True,
            )

        if find_similar:
            try:
                with st.spinner(
                    "Comparing visual embeddings. "
                    "Please wait..."
                ):
                    similar_results = (
                        get_similar_thumbnails(
                            selected_asin,
                            top_k=top_k,
                        )
                    )

                st.session_state[
                    "thumbnail_similar_results"
                ] = similar_results

                st.session_state[
                    "thumbnail_result_asin"
                ] = selected_asin

            except (
                KeyError,
                ValueError,
                OSError,
            ) as error:
                st.error(
                    "Similar thumbnails could not be generated."
                )
                st.code(str(error))

        stored_asin = st.session_state.get(
            "thumbnail_result_asin"
        )

        similar_results = st.session_state.get(
            "thumbnail_similar_results"
        )

        if (
            similar_results is not None
            and stored_asin == selected_asin
        ):
            st.markdown(
                "### Similar thumbnail results"
            )

            result_columns_per_row = 3

            for start_index in range(
                0,
                len(similar_results),
                result_columns_per_row,
            ):
                result_columns = st.columns(
                    result_columns_per_row,
                    gap="large",
                )

                current_results = similar_results.iloc[
                    start_index:
                    start_index + result_columns_per_row
                ]

                for result_column, (_, result) in zip(
                    result_columns,
                    current_results.iterrows(),
                ):
                    with result_column:
                        with st.container(border=True):
                            render_product_image(
                                result
                            )

                            st.markdown(
                                "#### "
                                + shorten_text(
                                    result.get("title"),
                                    70,
                                )
                            )

                            st.caption(
                                f"ASIN: {result['asin']}"
                            )

                            st.metric(
                                "Visual similarity",
                                display_number(
                                    result.get(
                                        "similarity_score"
                                    )
                                ),
                            )

                            render_visual_group_badge(
                                result.get(
                                    "cluster_name"
                                )
                            )

                            st.info(
                                display_text(
                                    result.get(
                                        "recommendation_reason"
                                    )
                                )
                            )

                            render_product_link(
                                result
                            )

        elif not find_similar:
            st.info(
                "Select a product and click "
                "'Find similar thumbnails' to begin."
            )


st.divider()

st.caption(
    "Thumbnail groups are generated from visual embeddings. "
    "Product metadata is used only for display and interpretation."
)