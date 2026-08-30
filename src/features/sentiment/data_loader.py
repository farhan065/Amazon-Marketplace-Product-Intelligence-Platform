from functools import lru_cache
from pathlib import Path

import pandas as pd

from .constants import (
    KEYWORD_SENTIMENT_PATH,
    PRODUCT_SENTIMENT_PATH,
    REVIEWS_SENTIMENT_PATH,
)


REVIEW_REQUIRED_COLUMNS = {
    "asin",
    "review_id",
    "category",
    "model_text",
    "sentiment_label",
    "sentiment_confidence",
    "negative_probability",
    "neutral_probability",
    "positive_probability",
    "sentiment_low_confidence",
}

PRODUCT_REQUIRED_COLUMNS = {
    "asin",
    "category",
    "review_count",
    "negative_count",
    "neutral_count",
    "positive_count",
    "negative_percentage",
    "neutral_percentage",
    "positive_percentage",
    "dominant_sentiment",
    "has_reviews",
}

KEYWORD_REQUIRED_COLUMNS = {
    "category",
    "product_count",
    "review_count",
    "negative_count",
    "neutral_count",
    "positive_count",
    "negative_percentage",
    "neutral_percentage",
    "positive_percentage",
    "dominant_sentiment",
}


def _read_csv(
    file_path: Path,
    required_columns: set[str],
) -> pd.DataFrame:
    """Read a CSV file and validate its columns."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Required sentiment data was not found: "
            f"{file_path}"
        )

    dataframe = pd.read_csv(
        file_path,
        keep_default_na=False,
    )

    missing_columns = (
        required_columns
        - set(dataframe.columns)
    )

    if missing_columns:
        raise ValueError(
            f"{file_path.name} is missing columns: "
            f"{sorted(missing_columns)}"
        )

    return dataframe


def _to_boolean(
    series: pd.Series,
) -> pd.Series:
    """Convert CSV boolean values safely."""

    return (
        series
        .astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "false": False,
            "1": True,
            "0": False,
        })
        .fillna(False)
        .astype(bool)
    )


@lru_cache(maxsize=1)
def _load_review_data() -> pd.DataFrame:
    reviews = _read_csv(
        REVIEWS_SENTIMENT_PATH,
        REVIEW_REQUIRED_COLUMNS,
    )

    reviews["asin"] = reviews["asin"].astype(str)
    reviews["review_id"] = (
        reviews["review_id"].astype(str)
    )

    reviews["sentiment_label"] = (
        reviews["sentiment_label"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    reviews["sentiment_low_confidence"] = (
        _to_boolean(
            reviews[
                "sentiment_low_confidence"
            ]
        )
    )

    numeric_columns = [
        "sentiment_confidence",
        "negative_probability",
        "neutral_probability",
        "positive_probability",
    ]

    for column in numeric_columns:
        reviews[column] = pd.to_numeric(
            reviews[column],
            errors="coerce",
        )

    return reviews


@lru_cache(maxsize=1)
def _load_product_data() -> pd.DataFrame:
    products = _read_csv(
        PRODUCT_SENTIMENT_PATH,
        PRODUCT_REQUIRED_COLUMNS,
    )

    products["asin"] = products["asin"].astype(
        str
    )

    products["has_reviews"] = _to_boolean(
        products["has_reviews"]
    )

    return products


@lru_cache(maxsize=1)
def _load_keyword_data() -> pd.DataFrame:
    return _read_csv(
        KEYWORD_SENTIMENT_PATH,
        KEYWORD_REQUIRED_COLUMNS,
    )


def load_sentiment_data():
    """Return safe copies of all sentiment datasets."""

    return (
        _load_review_data().copy(),
        _load_product_data().copy(),
        _load_keyword_data().copy(),
    )