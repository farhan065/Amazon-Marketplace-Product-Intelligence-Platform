from urllib.parse import urlparse

import numpy as np
import pandas as pd

from .data_loader import (
    load_local_thumbnail_index,
    load_thumbnail_data,
)


INVALID_TEXT_VALUES = {
    "",
    "nan",
    "none",
    "unknown",
    "unavailable",
}


def _clean_asin(asin):
    return str(asin).strip().upper()


def _valid_url(value):
    if pd.isna(value):
        return False

    value = str(value).strip()

    if not value:
        return False

    parsed_url = urlparse(value)

    return (
        parsed_url.scheme in {"http", "https"}
        and bool(parsed_url.netloc)
    )


def _similarity_description(score):
    if score >= 0.85:
        return "Very high visual similarity"

    if score >= 0.70:
        return "High visual similarity"

    if score >= 0.50:
        return "Moderate visual similarity"

    return "Related visual characteristics"


def get_thumbnail_metadata():
    _, _, _, _, metadata = load_thumbnail_data()

    return metadata.copy()


def search_thumbnail_products(query="", limit=50):
    assignments, _, _, _, _ = load_thumbnail_data()

    query = str(query).strip().lower()
    limit = max(1, int(limit))

    if not query:
        return assignments.head(limit).copy()

    searchable_columns = [
        column
        for column in [
            "asin",
            "title",
            "brand",
            "keyword_list",
            "cluster_name",
        ]
        if column in assignments.columns
    ]

    searchable_text = (
        assignments[searchable_columns]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
    )

    matched_products = assignments[
        searchable_text.str.contains(
            query,
            regex=False,
            na=False,
        )
    ]

    return matched_products.head(limit).copy()


def get_thumbnail_product(asin):
    assignments, _, _, _, _ = load_thumbnail_data()

    clean_asin = _clean_asin(asin)

    matched_product = assignments[
        assignments["asin"].eq(clean_asin)
    ]

    if matched_product.empty:
        raise KeyError(
            f"ASIN '{clean_asin}' was not found."
        )

    return matched_product.iloc[0].to_dict()


def get_visual_group_overview():
    assignments, interpretations, _, _, _ = (
        load_thumbnail_data()
    )

    product_counts = (
        assignments
        .groupby(
            ["cluster_id", "cluster_name"]
        )
        .size()
        .rename("product_count")
        .reset_index()
    )

    overview = interpretations.merge(
        product_counts,
        on=["cluster_id", "cluster_name"],
        how="left",
    )

    overview["product_count"] = (
        overview["product_count"]
        .fillna(0)
        .astype(int)
    )

    return (
        overview
        .sort_values("cluster_id")
        .reset_index(drop=True)
    )


def get_visual_group_products(
    cluster_id,
    limit=None,
):
    assignments, _, _, _, _ = load_thumbnail_data()

    cluster_id = int(cluster_id)

    group_products = assignments[
        assignments["cluster_id"].eq(cluster_id)
    ].copy()

    if "centroid_similarity" in group_products.columns:
        group_products = group_products.sort_values(
            "centroid_similarity",
            ascending=False,
        )

    group_products = group_products.reset_index(
        drop=True
    )

    if limit is not None:
        group_products = group_products.head(
            max(1, int(limit))
        )

    return group_products


def get_visual_group_interpretation(cluster_id):
    _, interpretations, _, _, _ = (
        load_thumbnail_data()
    )

    cluster_id = int(cluster_id)

    matched_group = interpretations[
        interpretations["cluster_id"].eq(
            cluster_id
        )
    ]

    if matched_group.empty:
        raise KeyError(
            f"Visual group {cluster_id + 1:02d} "
            "was not found."
        )

    return matched_group.iloc[0].to_dict()


def get_similar_thumbnails(
    asin,
    top_k=5,
    exclude_exact_duplicates=True,
):
    assignments, _, embeddings, _, _ = (
        load_thumbnail_data()
    )

    clean_asin = _clean_asin(asin)
    top_k = max(1, int(top_k))

    matching_positions = np.flatnonzero(
        assignments["asin"]
        .to_numpy()
        == clean_asin
    )

    if len(matching_positions) == 0:
        raise KeyError(
            f"ASIN '{clean_asin}' was not found."
        )

    selected_position = int(
        matching_positions[0]
    )

    selected_product = assignments.iloc[
        selected_position
    ]

    selected_embedding = embeddings[
        selected_position
    ]

    similarity_scores = (
        embeddings @ selected_embedding
    )

    candidate_mask = np.ones(
        len(assignments),
        dtype=bool,
    )

    # Never return the selected product itself.
    candidate_mask[selected_position] = False

    # Avoid showing an exact duplicate thumbnail as a result.
    if exclude_exact_duplicates:
        selected_canonical_asin = (
            selected_product["canonical_asin"]
        )

        candidate_mask &= (
            assignments["canonical_asin"]
            .to_numpy()
            != selected_canonical_asin
        )

    candidate_positions = np.flatnonzero(
        candidate_mask
    )

    ranked_positions = candidate_positions[
        np.argsort(
            similarity_scores[candidate_positions]
        )[::-1]
    ][:top_k]

    results = assignments.iloc[
        ranked_positions
    ].copy()

    results["similarity_score"] = (
        similarity_scores[ranked_positions]
    )

    results["same_visual_group"] = (
        results["cluster_id"]
        .eq(int(selected_product["cluster_id"]))
    )

    results["recommendation_reason"] = [
        (
            f"{_similarity_description(score)} "
            f"({score:.3f}). "
            + (
                "Same visual group."
                if same_group
                else "Neighbouring visual pattern."
            )
        )
        for score, same_group in zip(
            results["similarity_score"],
            results["same_visual_group"],
        )
    ]

    return results.reset_index(drop=True)


def get_thumbnail_source(product):
    """
    Return a downloaded local thumbnail when available.
    Otherwise return the product image URL.
    """

    asin = _clean_asin(
        product.get("asin", "")
    )

    local_image_index = (
        load_local_thumbnail_index()
    )

    local_image_path = local_image_index.get(
        asin
    )

    if local_image_path is not None:
        return str(local_image_path)

    image_url = product.get(
        "image_url",
        "",
    )

    if _valid_url(image_url):
        return str(image_url).strip()

    return None