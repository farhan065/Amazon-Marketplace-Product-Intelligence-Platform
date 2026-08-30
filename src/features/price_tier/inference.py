from functools import lru_cache
import re

import joblib
import numpy as np
import pandas as pd

from .constants import (
    LABEL_ORDER,
    MODEL_FEATURES,
    MODEL_PATH,
)


PRICE_AMOUNT_PATTERN = re.compile(
    r"""
    (?:
        [$£€]\s*\d[\d,.]*
        |
        \b(?:usd|gbp|eur)\s*\d[\d,.]*
    )
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


def _prepare_text(value):
    if value is None or pd.isna(value):
        return ""

    text = str(value).strip()

    text = PRICE_AMOUNT_PATTERN.sub(
        " ",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def _prepare_category(value):
    if value is None or pd.isna(value):
        return "Unknown"

    text = str(value).strip()

    if text.lower() in {
        "",
        "nan",
        "none",
        "unknown",
    }:
        return "Unknown"

    return text


def _parse_number(value, absolute=False):
    if value is None or pd.isna(value):
        return np.nan

    cleaned = str(value).replace(",", "").strip()

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        cleaned,
    )

    if not match:
        return np.nan

    number = float(match.group())

    if absolute:
        number = abs(number)

    return number


def prepare_price_tier_features(
    title="",
    description="",
    brand=None,
    keyword=None,
    marketplace=None,
    review_count=None,
    average_rating=None,
):
    clean_title = _prepare_text(title)
    clean_description = _prepare_text(description)
    clean_brand = _prepare_category(brand)
    clean_keyword = _prepare_category(keyword)
    clean_marketplace = _prepare_category(
        marketplace
    )

    numeric_review_count = _parse_number(
        review_count,
        absolute=True,
    )

    numeric_rating = _parse_number(
        average_rating,
    )

    if (
        not np.isnan(numeric_rating)
        and not 0 <= numeric_rating <= 5
    ):
        numeric_rating = np.nan

    log_review_count = (
        np.log1p(numeric_review_count)
        if not np.isnan(numeric_review_count)
        else np.nan
    )

    combined_text = (
        clean_title
        + " "
        + clean_description
    ).strip()

    features = pd.DataFrame(
        [
            {
                "combined_text": combined_text,
                "brand": clean_brand,
                "keyword": clean_keyword,
                "marketplace": clean_marketplace,
                "log_review_count": log_review_count,
                "average_rating": numeric_rating,
                "title_length": len(
                    clean_title.split()
                ),
                "description_length": len(
                    clean_description.split()
                ),
                "title_missing": int(
                    clean_title == ""
                ),
                "description_missing": int(
                    clean_description == ""
                ),
                "brand_missing": int(
                    clean_brand == "Unknown"
                ),
                "review_count_missing": int(
                    np.isnan(numeric_review_count)
                ),
                "rating_missing": int(
                    np.isnan(numeric_rating)
                ),
            }
        ]
    )

    return features[MODEL_FEATURES]


@lru_cache(maxsize=1)
def load_price_tier_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Price Tier model was not found:\n"
            f"{MODEL_PATH}"
        )

    return joblib.load(MODEL_PATH)


def predict_price_tier(
    title="",
    description="",
    brand=None,
    keyword=None,
    marketplace=None,
    review_count=None,
    average_rating=None,
):
    features = prepare_price_tier_features(
        title=title,
        description=description,
        brand=brand,
        keyword=keyword,
        marketplace=marketplace,
        review_count=review_count,
        average_rating=average_rating,
    )

    model = load_price_tier_model()

    prediction = model.predict(features)[0]

    probabilities = model.predict_proba(
        features
    )[0]

    probability_lookup = dict(
        zip(
            model.classes_,
            probabilities,
        )
    )

    ordered_probabilities = {
        tier: float(
            probability_lookup.get(tier, 0.0)
        )
        for tier in LABEL_ORDER
    }

    confidence = ordered_probabilities[
        prediction
    ]

    reason = (
        f"Classified as {prediction} from product text, "
        f"brand, marketplace context, review count and "
        f"rating signals. Confidence: {confidence:.1%}. "
        "Product price was not used."
    )

    return {
        "predicted_price_tier": prediction,
        "prediction_confidence": confidence,
        "budget_probability": (
            ordered_probabilities["Budget"]
        ),
        "mid_range_probability": (
            ordered_probabilities["Mid-range"]
        ),
        "premium_probability": (
            ordered_probabilities["Premium"]
        ),
        "prediction_reason": reason,
    }