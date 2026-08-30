import pandas as pd
import plotly.express as px
import streamlit as st

from .styles import SENTIMENT_COLORS


def render_custom_classifier() -> None:
    st.subheader("Custom-review sentiment classifier")
    st.caption(
        "Enter a new customer review to receive a RoBERTa "
        "sentiment prediction and class probabilities."
    )

    input_column, information_column = st.columns(
        [1.7, 1], gap="large"
    )
    with input_column:
        with st.form("custom_review_form"):
            review_text = st.text_area(
                "Review text",
                height=190,
                max_chars=5000,
                placeholder=(
                    "Example: The sound quality is excellent, "
                    "but the battery does not last very long."
                ),
                key="custom_review_text",
            )
            submitted = st.form_submit_button(
                "Analyze sentiment",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            cleaned_text = " ".join(review_text.split())
            if not cleaned_text:
                st.warning("Enter a review before running the classifier.")
            else:
                _run_prediction(cleaned_text)

    with information_column:
        st.markdown("#### How to interpret the result")
        st.write(
            "The class with the highest negative, neutral or "
            "positive probability becomes the prediction."
        )
        st.info(
            "The first prediction can take longer while the saved "
            "RoBERTa model loads. Predictions below 70% confidence "
            "are marked as uncertain."
        )
        with st.expander("Known model limitation"):
            st.write(
                "Neutral and mixed-sentiment reviews remain the "
                "most difficult class, even though RoBERTa performed "
                "better than the classical candidate models."
            )

    result = st.session_state.get("custom_sentiment_result")
    submitted_text = st.session_state.get("custom_sentiment_input")
    if result and submitted_text:
        _render_result(result, submitted_text)


def _run_prediction(review_text: str) -> None:
    try:
        with st.spinner(
            "Please wait a few seconds while RoBERTa loads and "
            "analyzes the review..."
        ):
            # Lazy import: transformers/torch load only after submission.
            from ..inference import predict_sentiment

            result = predict_sentiment(review_text)
        st.session_state["custom_sentiment_result"] = result
        st.session_state["custom_sentiment_input"] = review_text
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        st.error("The review could not be analyzed.")
        st.code(str(error))


def _render_result(result: dict, review_text: str) -> None:
    st.divider()
    st.subheader("Prediction result")
    sentiment = str(result["predicted_sentiment"]).lower()
    confidence = float(result["confidence"])
    messages = {
        "negative": (st.error, "Negative sentiment detected"),
        "neutral": (st.warning, "Neutral or mixed sentiment detected"),
        "positive": (st.success, "Positive sentiment detected"),
    }
    message_function, message = messages.get(
        sentiment,
        (st.info, f"{sentiment.title()} sentiment detected"),
    )
    message_function(message)

    columns = st.columns(3)
    columns[0].metric("Predicted sentiment", sentiment.title())
    columns[1].metric("Confidence", f"{confidence:.1%}")
    source = (
        "Saved local model"
        if result.get("model_source") == "local"
        else "Hugging Face fallback"
    )
    columns[2].metric("Model source", source)

    if result.get("low_confidence", confidence < 0.70):
        st.warning(
            "This is a low-confidence prediction. Interpret it "
            "carefully, especially for neutral or mixed language."
        )

    probabilities = result["probabilities"]
    chart_data = pd.DataFrame(
        {
            "sentiment": ["negative", "neutral", "positive"],
            "probability": [
                probabilities["negative"],
                probabilities["neutral"],
                probabilities["positive"],
            ],
        }
    )
    chart_column, text_column = st.columns([1.25, 1], gap="large")
    with chart_column:
        st.markdown("#### Class probabilities")
        figure = px.bar(
            chart_data,
            x="probability",
            y="sentiment",
            color="sentiment",
            orientation="h",
            text="probability",
            color_discrete_map=SENTIMENT_COLORS,
        )
        figure.update_traces(
            texttemplate="%{x:.1%}", textposition="outside"
        )
        figure.update_layout(
            height=330,
            showlegend=False,
            xaxis=dict(range=[0, 1], tickformat=".0%"),
            margin=dict(l=20, r=40, t=20, b=20),
        )
        st.plotly_chart(figure, use_container_width=True)

    with text_column:
        st.markdown("#### Analyzed review")
        st.text_area(
            "Submitted text",
            value=review_text,
            height=180,
            disabled=True,
            label_visibility="collapsed",
        )
        st.caption(
            f"{len(review_text.split()):,} words · "
            f"{len(review_text):,} characters"
        )
        if st.button("Clear prediction", key="clear_custom_prediction"):
            st.session_state.pop("custom_sentiment_result", None)
            st.session_state.pop("custom_sentiment_input", None)
            st.rerun()
