import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import linear_kernel

from .constants import DEFAULT_TOP_K
from .data_loader import load_recommendation_assets


INVALID_TEXT_VALUES = {
    "",
    "unknown",
    "nan",
    "none",
}


def _clean_value(value):
    value = str(value).strip()

    if value.lower() in INVALID_TEXT_VALUES:
        return ""

    return value


def _split_keywords(value):
    return {
        keyword.strip().lower()
        for keyword in str(value).split(" | ")
        if keyword.strip()
    }


def _get_shared_terms(
    tfidf_matrix,
    feature_names,
    selected_index,
    recommended_index,
    limit=3,
):
    overlap = tfidf_matrix[
        selected_index
    ].multiply(
        tfidf_matrix[recommended_index]
    )

    if overlap.nnz == 0:
        return []

    sorted_positions = np.argsort(
        overlap.data
    )[::-1]

    shared_terms = []

    for position in sorted_positions:
        term = str(
            feature_names[
                overlap.indices[position]
            ]
        ).strip()

        if (
            len(term) < 3
            or term in shared_terms
        ):
            continue

        shared_terms.append(term)

        if len(shared_terms) == limit:
            break

    return shared_terms


def _build_reason(
    selected_product,
    recommended_product,
    shared_terms,
):
    reasons = []

    if shared_terms:
        reasons.append(
            "Similar product details: "
            + ", ".join(shared_terms)
        )

    selected_keywords = _split_keywords(
        selected_product.get(
            "keyword_list",
            "",
        )
    )

    recommended_keywords = _split_keywords(
        recommended_product.get(
            "keyword_list",
            "",
        )
    )

    shared_keywords = sorted(
        selected_keywords
        & recommended_keywords
    )

    if shared_keywords:
        reasons.append(
            "Same product group: "
            + shared_keywords[0]
        )

    selected_brand = _clean_value(
        selected_product.get("brand", "")
    )

    recommended_brand = _clean_value(
        recommended_product.get("brand", "")
    )

    if (
        selected_brand
        and recommended_brand
        and selected_brand.lower()
        == recommended_brand.lower()
    ):
        reasons.append(
            f"Same brand: {selected_brand}"
        )

    if not reasons:
        return (
            "Similar title and description content."
        )

    return ". ".join(reasons[:2]) + "."


def get_product_by_asin(asin):
    (
        products,
        _,
        _,
        _,
        asin_to_index,
    ) = load_recommendation_assets()

    asin = str(asin).strip()

    if asin not in asin_to_index:
        raise ValueError(
            f"ASIN not found: {asin}"
        )

    return products.iloc[
        asin_to_index[asin]
    ].copy()


def search_products(query="", limit=20):
    (
        products,
        _,
        _,
        _,
        _,
    ) = load_recommendation_assets()

    query = str(query).strip().lower()

    searchable_columns = [
        column
        for column in [
            "asin",
            "title",
            "brand",
            "keyword_list",
        ]
        if column in products.columns
    ]

    if not query:
        results = products.head(limit)
    else:
        search_text = (
            products[searchable_columns]
            .fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
            .str.lower()
        )

        results = products[
            search_text.str.contains(
                query,
                regex=False,
            )
        ].head(limit)

    return results.reset_index(drop=True)


def recommend_by_asin(
    asin,
    top_k=DEFAULT_TOP_K,
):
    (
        products,
        vectorizer,
        tfidf_matrix,
        _,
        asin_to_index,
    ) = load_recommendation_assets()

    asin = str(asin).strip()

    if asin not in asin_to_index:
        raise ValueError(
            f"ASIN not found: {asin}"
        )

    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1."
        )

    selected_index = asin_to_index[asin]

    similarity_scores = linear_kernel(
        tfidf_matrix[selected_index],
        tfidf_matrix,
    ).ravel()

    similarity_scores[
        selected_index
    ] = -np.inf

    asin_values = (
        products["asin"]
        .astype(str)
        .to_numpy()
    )

    ranked_indices = np.lexsort(
        (
            asin_values,
            -similarity_scores,
        )
    )

    top_k = min(
        int(top_k),
        len(products) - 1,
    )

    recommended_indices = (
        ranked_indices[:top_k]
    )

    results = products.iloc[
        recommended_indices
    ].copy()

    results.insert(
        0,
        "rank",
        range(1, len(results) + 1),
    )

    results["similarity_score"] = (
        similarity_scores[
            recommended_indices
        ]
    )

    selected_product = products.iloc[
        selected_index
    ]

    feature_names = (
        vectorizer.get_feature_names_out()
    )

    results["recommendation_reason"] = [
        _build_reason(
            selected_product=selected_product,
            recommended_product=(
                products.iloc[
                    recommended_index
                ]
            ),
            shared_terms=_get_shared_terms(
                tfidf_matrix=tfidf_matrix,
                feature_names=feature_names,
                selected_index=selected_index,
                recommended_index=(
                    recommended_index
                ),
            ),
        )
        for recommended_index
        in recommended_indices
    ]

    return results.reset_index(drop=True)