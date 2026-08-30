from pathlib import Path
import sys

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


from src.features.sentiment.data_loader import (  # noqa: E402
    load_sentiment_data,
)

from src.features.sentiment.views import (  # noqa: E402
    apply_sentiment_styles,
    render_custom_classifier,
    render_keyword_summary,
    render_overview,
    render_product_analysis,
    render_sentiment_header,
)


# ------------------------------------------------------------
# Page configuration
# ------------------------------------------------------------

st.set_page_config(
    page_title="Sentiment Intelligence",
    page_icon="📊",
    layout="wide",
)


# ------------------------------------------------------------
# Data loading
# ------------------------------------------------------------

@st.cache_data(show_spinner=False)
def get_application_data():
    return load_sentiment_data()


# ------------------------------------------------------------
# Page header and navigation
# ------------------------------------------------------------

apply_sentiment_styles()

st.page_link(
    "app.py",
    label="Home",
    icon="🏠",
)

render_sentiment_header()


# ------------------------------------------------------------
# Load application data
# ------------------------------------------------------------

try:
    with st.spinner(
        "Please wait a few seconds while sentiment "
        "data is loading..."
    ):
        reviews, products, keyword_summary = (
            get_application_data()
        )

except (
    FileNotFoundError,
    OSError,
    ValueError,
) as error:
    st.error(
        "The sentiment application data could not be loaded."
    )

    st.code(str(error))

    st.info(
        "Confirm that the three prepared sentiment CSV "
        "files are inside data/processed, then restart "
        "the application."
    )

    st.stop()


# ------------------------------------------------------------
# Sentiment feature tabs
# ------------------------------------------------------------

(
    overview_tab,
    product_tab,
    keyword_tab,
    classifier_tab,
) = st.tabs(
    [
        "Overview",
        "Product Analysis",
        "Keyword Summary",
        "Custom Classifier",
    ]
)


# ------------------------------------------------------------
# Overview
# ------------------------------------------------------------

with overview_tab:
    render_overview(
        reviews,
        products,
        keyword_summary,
    )


# ------------------------------------------------------------
# Product-level analysis
# ------------------------------------------------------------

with product_tab:
    render_product_analysis(
        reviews,
        products,
    )


# ------------------------------------------------------------
# Keyword summary
# ------------------------------------------------------------

with keyword_tab:
    render_keyword_summary(
        keyword_summary,
    )


# ------------------------------------------------------------
# Custom review classifier
# ------------------------------------------------------------

with classifier_tab:
    render_custom_classifier()