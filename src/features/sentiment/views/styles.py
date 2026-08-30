import streamlit as st


SENTIMENT_COLORS = {
    "negative": "#EF4444",
    "neutral": "#F59E0B",
    "positive": "#10B981",
}


def apply_sentiment_styles() -> None:
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

            .sentiment-header {
                padding: 22px 26px;
                border-radius: 18px;
                margin-bottom: 22px;
                background: linear-gradient(
                    120deg,
                    rgba(37, 99, 235, 0.18),
                    rgba(16, 185, 129, 0.12)
                );
                border: 1px solid rgba(59, 130, 246, 0.22);
            }

            .sentiment-header h1 {
                margin: 0;
                font-size: 2.1rem;
            }

            .sentiment-header p {
                margin: 8px 0 0;
                opacity: 0.78;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sentiment_header() -> None:
    st.markdown(
        """
        <div class="sentiment-header">
            <h1>Sentiment Intelligence</h1>
            <p>
                Explore customer opinion across products and search
                keywords using CardiffNLP RoBERTa predictions.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
