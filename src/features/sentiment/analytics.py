from collections.abc import Iterable

import pandas as pd

from .constants import SENTIMENT_LABELS


def get_overview_metrics(
    reviews: pd.DataFrame,
    products: pd.DataFrame,
) -> dict:
    """Calculate application-wide sentiment metrics."""

    # Shared variant reviews count once globally.
    unique_reviews = reviews.drop_duplicates(
        subset=["review_id"],
        keep="first",
    )

    sentiment_counts = (
        unique_reviews["sentiment_label"]
        .value_counts()
        .reindex(
            SENTIMENT_LABELS,
            fill_value=0,
        )
    )

    total_reviews = len(unique_reviews)

    metrics = {
        "total_products": int(len(products)),
        "products_with_reviews": int(
            products["has_reviews"].sum()
        ),
        "products_without_reviews": int(
            (~products["has_reviews"]).sum()
        ),
        "unique_reviews": int(total_reviews),
        "low_confidence_reviews": int(
            unique_reviews[
                "sentiment_low_confidence"
            ].sum()
        ),
        "average_confidence": float(
            unique_reviews[
                "sentiment_confidence"
            ].mean()
        ),
    }

    for label in SENTIMENT_LABELS:
        count = int(sentiment_counts[label])

        percentage = (
            count / total_reviews * 100
            if total_reviews
            else 0.0
        )

        metrics[f"{label}_count"] = count
        metrics[f"{label}_percentage"] = (
            percentage
        )

    metrics["dominant_sentiment"] = (
        sentiment_counts.idxmax()
        if total_reviews
        else "unavailable"
    )

    return metrics


def get_overview_distribution(
    reviews: pd.DataFrame,
) -> pd.DataFrame:
    """Return unique-review sentiment distribution."""

    unique_reviews = reviews.drop_duplicates(
        subset=["review_id"],
        keep="first",
    )

    distribution = (
        unique_reviews["sentiment_label"]
        .value_counts()
        .reindex(
            SENTIMENT_LABELS,
            fill_value=0,
        )
        .rename_axis("sentiment")
        .reset_index(name="count")
    )

    total = distribution["count"].sum()

    distribution["percentage"] = (
        distribution["count"]
        .div(total)
        .mul(100)
        .fillna(0)
        .round(2)
    )

    return distribution


def filter_products(
    products: pd.DataFrame,
    category: str | None = None,
    search_text: str = "",
) -> pd.DataFrame:
    """Filter products by keyword/category and search text."""

    filtered_products = products.copy()

    if category:
        filtered_products = filtered_products[
            filtered_products["category"].eq(
                category
            )
        ]

    cleaned_search = search_text.strip()

    if cleaned_search:
        searchable_columns = [
            column
            for column in [
                "asin",
                "title",
                "brand",
            ]
            if column in filtered_products.columns
        ]

        search_mask = pd.Series(
            False,
            index=filtered_products.index,
        )

        for column in searchable_columns:
            search_mask = (
                search_mask
                | filtered_products[column]
                .astype(str)
                .str.contains(
                    cleaned_search,
                    case=False,
                    na=False,
                    regex=False,
                )
            )

        filtered_products = (
            filtered_products[search_mask]
        )

    sort_columns = [
        column
        for column in [
            "review_count",
            "title",
            "asin",
        ]
        if column in filtered_products.columns
    ]

    if sort_columns:
        filtered_products = (
            filtered_products.sort_values(
                sort_columns,
                ascending=[
                    False
                    if column == "review_count"
                    else True
                    for column in sort_columns
                ],
            )
        )

    return filtered_products.reset_index(
        drop=True
    )


def get_product_details(
    products: pd.DataFrame,
    asin: str,
) -> dict:
    """Return one product summary as a dictionary."""

    selected_product = products[
        products["asin"].eq(str(asin))
    ]

    if selected_product.empty:
        raise KeyError(
            f"Product ASIN was not found: {asin}"
        )

    return selected_product.iloc[0].to_dict()


def get_product_reviews(
    reviews: pd.DataFrame,
    asin: str,
    sentiments: Iterable[str] | None = None,
    low_confidence_only: bool = False,
) -> pd.DataFrame:
    """Return filtered reviews for one product."""

    product_reviews = reviews[
        reviews["asin"].eq(str(asin))
    ].copy()

    if sentiments:
        selected_sentiments = {
            str(label).strip().lower()
            for label in sentiments
        }

        invalid_sentiments = (
            selected_sentiments
            - set(SENTIMENT_LABELS)
        )

        if invalid_sentiments:
            raise ValueError(
                "Invalid sentiment filters: "
                f"{sorted(invalid_sentiments)}"
            )

        product_reviews = product_reviews[
            product_reviews[
                "sentiment_label"
            ].isin(selected_sentiments)
        ]

    if low_confidence_only:
        product_reviews = product_reviews[
            product_reviews[
                "sentiment_low_confidence"
            ]
        ]

    if "sentiment_confidence" in (
        product_reviews.columns
    ):
        product_reviews = (
            product_reviews.sort_values(
                "sentiment_confidence",
                ascending=False,
            )
        )

    return product_reviews.reset_index(
        drop=True
    )


def filter_keyword_summary(
    keyword_summary: pd.DataFrame,
    selected_keywords: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Filter the prepared keyword/category summary."""

    filtered_summary = keyword_summary.copy()

    if selected_keywords:
        selected_keywords = {
            str(keyword).strip()
            for keyword in selected_keywords
        }

        filtered_summary = filtered_summary[
            filtered_summary[
                "category"
            ].isin(selected_keywords)
        ]

    return (
        filtered_summary
        .sort_values(
            "review_count",
            ascending=False,
        )
        .reset_index(drop=True)
    )