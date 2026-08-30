from pathlib import Path
import sys

import streamlit as st


# Supports both `streamlit run app.py` and direct page execution.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features.sentiment.data_loader import load_sentiment_data
from src.features.sentiment.views import (
    apply_sentiment_styles,
    render_custom_classifier,
    render_keyword_summary,
    render_overview,
    render_product_analysis,
    render_sentiment_header,
)


st.set_page_config(
    page_title="Sentiment Intelligence",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def get_application_data():
    return load_sentiment_data()


apply_sentiment_styles()
render_sentiment_header()

try:
    with st.spinner(
        "Please wait a few seconds while sentiment data is loading..."
    ):
        reviews, products, keyword_summary = get_application_data()
except (FileNotFoundError, OSError, ValueError) as error:
    st.error("The sentiment application data could not be loaded.")
    st.code(str(error))
    st.info(
        "Confirm the three prepared sentiment CSV files are inside "
        "data/processed, then restart the application."
    )
    st.stop()

overview_tab, product_tab, keyword_tab, classifier_tab = st.tabs(
    [
        "Overview",
        "Product Analysis",
        "Keyword Summary",
        "Custom Classifier",
    ]
)

with overview_tab:
    render_overview(reviews, products, keyword_summary)

with product_tab:
    render_product_analysis(reviews, products)

with keyword_tab:
    render_keyword_summary(keyword_summary)

with classifier_tab:
    render_custom_classifier()
