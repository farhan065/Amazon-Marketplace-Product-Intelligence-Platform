from functools import lru_cache
import json
import re

import pandas as pd

from .constants import (
    FEATURE_SUMMARY_PATH,
    LABEL_ORDER,
    MODEL_DECISION_PATH,
    MODEL_METADATA_PATH,
    PREDICTIONS_PATH,
)


REQUIRED_PREDICTION_COLUMNS = {
    "asin",
    "title",
    "predicted_price_tier",
    "prediction_confidence",
    "budget_probability",
    "mid_range_probability",
    "premium_probability",
    "prediction_reason",
}


def _validate_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required Price Tier file was not found:\n{path}"
        )


def _normalize_column_name(column):
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(column).lower(),
    ).strip("_")


def _standardize_prediction_columns(data):
    """
    Convert alternative Step 6 probability-column names into
    the canonical names expected by the local application.
    """

    normalized_lookup = {
        _normalize_column_name(column): column
        for column in data.columns
    }

    column_aliases = {
        "budget_probability": {
            "budget_probability",
            "probability_budget",
            "budget_prob",
            "prob_budget",
            "budget_score",
            "budget",
        },
        "mid_range_probability": {
            "mid_range_probability",
            "midrange_probability",
            "probability_mid_range",
            "probability_midrange",
            "mid_range_prob",
            "midrange_prob",
            "prob_mid_range",
            "mid_range_score",
            "mid_range",
            "midrange",
        },
        "premium_probability": {
            "premium_probability",
            "probability_premium",
            "premium_prob",
            "prob_premium",
            "premium_score",
            "premium",
        },
    }

    rename_columns = {}

    for canonical_name, possible_names in (
        column_aliases.items()
    ):
        if canonical_name in data.columns:
            continue

        for possible_name in possible_names:
            source_column = normalized_lookup.get(
                possible_name
            )

            if source_column is not None:
                rename_columns[
                    source_column
                ] = canonical_name
                break

    return data.rename(
        columns=rename_columns
    )


@lru_cache(maxsize=1)
def _load_predictions():
    _validate_file(PREDICTIONS_PATH)

    data = pd.read_csv(
        PREDICTIONS_PATH,
        dtype={"asin": str},
        low_memory=False,
    )

    data = _standardize_prediction_columns(
        data
    )

    missing_columns = (
        REQUIRED_PREDICTION_COLUMNS
        - set(data.columns)
    )

    if missing_columns:
        available_columns = ", ".join(
            map(str, data.columns)
        )

        raise ValueError(
            "Price Tier prediction columns are missing:\n"
            + ", ".join(
                sorted(missing_columns)
            )
            + "\n\nAvailable CSV columns:\n"
            + available_columns
        )

    data["asin"] = (
        data["asin"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    data["title"] = (
        data["title"]
        .fillna("Untitled product")
        .astype(str)
        .str.strip()
    )

    data["predicted_price_tier"] = (
        data["predicted_price_tier"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    data["prediction_reason"] = (
        data["prediction_reason"]
        .fillna(
            "Classification reason is unavailable."
        )
        .astype(str)
        .str.strip()
    )

    invalid_tiers = (
        set(
            data[
                "predicted_price_tier"
            ].unique()
        )
        - set(LABEL_ORDER)
    )

    if invalid_tiers:
        raise ValueError(
            "Unexpected predicted tiers:\n"
            + ", ".join(
                sorted(invalid_tiers)
            )
        )

    probability_columns = [
        "budget_probability",
        "mid_range_probability",
        "premium_probability",
        "prediction_confidence",
    ]

    for column in probability_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    if data[
        probability_columns
    ].isna().any().any():
        invalid_columns = (
            data[
                probability_columns
            ]
            .columns[
                data[
                    probability_columns
                ]
                .isna()
                .any()
            ]
            .tolist()
        )

        raise ValueError(
            "Invalid or missing numeric values exist in:\n"
            + ", ".join(invalid_columns)
        )

    probability_sum = (
        data["budget_probability"]
        + data["mid_range_probability"]
        + data["premium_probability"]
    )

    if not probability_sum.between(
        0.99,
        1.01,
        inclusive="both",
    ).all():
        raise ValueError(
            "Tier probabilities do not sum to approximately 1."
        )

    if data["asin"].eq("").any():
        raise ValueError(
            "Blank ASIN values exist in the prediction file."
        )

    if data["asin"].duplicated().any():
        raise ValueError(
            "Duplicate ASIN values exist in the prediction file."
        )

    return data.reset_index(
        drop=True
    )


def load_price_tier_data():
    return _load_predictions().copy()


@lru_cache(maxsize=1)
def load_price_tier_metadata():
    metadata = {}

    if MODEL_METADATA_PATH.exists():
        with open(
            MODEL_METADATA_PATH,
            encoding="utf-8",
        ) as file:
            metadata.update(
                json.load(file)
            )

    if MODEL_DECISION_PATH.exists():
        with open(
            MODEL_DECISION_PATH,
            encoding="utf-8",
        ) as file:
            metadata[
                "model_decision"
            ] = json.load(file)

    return metadata.copy()


@lru_cache(maxsize=1)
def _load_feature_summary():
    _validate_file(
        FEATURE_SUMMARY_PATH
    )

    return pd.read_csv(
        FEATURE_SUMMARY_PATH,
        low_memory=False,
    )


def load_feature_summary():
    return _load_feature_summary().copy()


def get_product_by_asin(asin):
    normalized_asin = (
        str(asin)
        .strip()
        .upper()
    )

    data = _load_predictions()

    result = data[
        data["asin"].eq(
            normalized_asin
        )
    ]

    if result.empty:
        raise KeyError(
            "Product ASIN was not found: "
            f"{normalized_asin}"
        )

    return result.iloc[0].copy()


def search_price_tier_products(
    query="",
    tier=None,
    keyword=None,
    limit=50,
):
    data = _load_predictions().copy()

    if tier and tier != "All":
        if tier not in LABEL_ORDER:
            raise ValueError(
                "Unsupported price tier: "
                f"{tier}"
            )

        data = data[
            data[
                "predicted_price_tier"
            ].eq(tier)
        ]

    if (
        keyword
        and keyword != "All"
        and "keyword" in data.columns
    ):
        data = data[
            data["keyword"]
            .fillna("")
            .astype(str)
            .eq(keyword)
        ]

    query = str(query).strip()

    if query:
        searchable_columns = [
            column
            for column in [
                "asin",
                "title",
                "brand",
                "keyword",
                "marketplace",
            ]
            if column in data.columns
        ]

        search_text = (
            data[searchable_columns]
            .fillna("")
            .astype(str)
            .agg(
                " ".join,
                axis=1,
            )
        )

        data = data[
            search_text.str.contains(
                query,
                case=False,
                regex=False,
                na=False,
            )
        ]

    return (
        data
        .head(limit)
        .reset_index(drop=True)
    )


def get_price_tier_overview():
    data = _load_predictions()

    overview = (
        data.groupby(
            "predicted_price_tier",
            observed=True,
        )
        .agg(
            product_count=(
                "asin",
                "nunique",
            ),
            average_confidence=(
                "prediction_confidence",
                "mean",
            ),
        )
        .reindex(LABEL_ORDER)
        .fillna(0)
        .reset_index()
    )

    overview[
        "share_percentage"
    ] = (
        overview["product_count"]
        / max(len(data), 1)
        * 100
    )

    return overview