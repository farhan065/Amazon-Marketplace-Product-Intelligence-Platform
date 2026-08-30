from functools import lru_cache
from typing import Any

import torch

from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)

from .constants import (
    HUGGINGFACE_MODEL_NAME,
    LOCAL_MODEL_DIR,
    LOW_CONFIDENCE_THRESHOLD,
    MAX_TOKEN_LENGTH,
    SENTIMENT_LABELS,
)


@lru_cache(maxsize=1)
def load_sentiment_resources():
    """Load and cache the RoBERTa tokenizer and model."""

    local_model_available = (
        LOCAL_MODEL_DIR / "config.json"
    ).exists()

    model_source = (
        str(LOCAL_MODEL_DIR)
        if local_model_available
        else HUGGINGFACE_MODEL_NAME
    )

    loading_options = {
        "local_files_only": local_model_available
    }

    tokenizer = AutoTokenizer.from_pretrained(
        model_source,
        **loading_options,
    )

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(
            model_source,
            **loading_options,
        )
        .to("cpu")
    )

    model.eval()

    source_type = (
        "local"
        if local_model_available
        else "huggingface"
    )

    return tokenizer, model, source_type


def predict_sentiment(
    review_text: str,
) -> dict[str, Any]:
    """Predict sentiment for one review."""

    if not isinstance(review_text, str):
        raise TypeError(
            "Review text must be a string."
        )

    cleaned_text = " ".join(
        review_text.split()
    )

    if not cleaned_text:
        raise ValueError(
            "Review text cannot be empty."
        )

    tokenizer, model, source_type = (
        load_sentiment_resources()
    )

    model_inputs = tokenizer(
        cleaned_text,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_TOKEN_LENGTH,
    )

    with torch.inference_mode():
        model_outputs = model(
            **model_inputs
        )

    probabilities = torch.softmax(
        model_outputs.logits,
        dim=-1,
    )[0].cpu().tolist()

    probability_scores = {}

    for class_index, score in enumerate(
        probabilities
    ):
        class_name = (
            model.config.id2label
            .get(
                class_index,
                SENTIMENT_LABELS[class_index],
            )
            .lower()
        )

        probability_scores[class_name] = float(
            score
        )

    predicted_label = max(
        probability_scores,
        key=probability_scores.get,
    )

    confidence = probability_scores[
        predicted_label
    ]

    return {
        "predicted_sentiment": predicted_label,
        "confidence": confidence,
        "low_confidence": (
            confidence
            < LOW_CONFIDENCE_THRESHOLD
        ),
        "probabilities": {
            label: probability_scores.get(
                label,
                0.0,
            )
            for label in SENTIMENT_LABELS
        },
        "model_source": source_type,
    }