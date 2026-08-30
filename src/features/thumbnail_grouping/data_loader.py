import json
import re
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from .constants import (
    ASSIGNMENTS_PATH,
    CENTROIDS_PATH,
    EMBEDDINGS_PATH,
    INTERPRETATION_PATH,
    KMEANS_MODEL_PATH,
    LOCAL_IMAGE_DIRECTORIES,
    METADATA_PATH,
    PCA_MODEL_PATH,
    PRODUCT_DATA_CANDIDATES,
    SUPPORTED_IMAGE_EXTENSIONS,
)


ASIN_PATTERN = re.compile(
    r"(?<![A-Z0-9])([A-Z0-9]{10})(?![A-Z0-9])",
    flags=re.IGNORECASE,
)

INVALID_METADATA_VALUES = {
    "",
    "nan",
    "none",
    "unknown",
    "unavailable",
}


def _validate_required_files(paths):
    """Confirm that all required artifact files exist."""

    missing_files = [
        str(path)
        for path in paths
        if not path.exists()
    ]

    if missing_files:
        raise FileNotFoundError(
            "Required thumbnail-grouping files are missing:\n"
            + "\n".join(missing_files)
        )


def _clean_asin_column(dataframe):
    """Normalize the ASIN column."""

    dataframe = dataframe.copy()

    dataframe["asin"] = (
        dataframe["asin"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return dataframe


def _missing_text_mask(series):
    """Identify empty or invalid text values."""

    return (
        series.isna()
        | series.astype(str)
        .str.strip()
        .str.lower()
        .isin(INVALID_METADATA_VALUES)
    )


def _add_product_metadata(assignments):
    """
    Add missing product metadata to thumbnail assignments.

    The clustering artifact may contain only ASIN and cluster
    information. Product display information is loaded from the
    existing processed product dataset.
    """

    product_data_path = next(
        (
            path
            for path in PRODUCT_DATA_CANDIDATES
            if path.exists()
        ),
        None,
    )

    if product_data_path is None:
        raise FileNotFoundError(
            "Product metadata could not be found. Checked:\n"
            + "\n".join(
                str(path)
                for path in PRODUCT_DATA_CANDIDATES
            )
        )

    products = pd.read_csv(
        product_data_path,
        dtype={"asin": str},
    )

    if "asin" not in products.columns:
        raise ValueError(
            "The product dataset does not contain "
            "an 'asin' column."
        )

    products = _clean_asin_column(
        products
    )

    products = (
        products[
            products["asin"].ne("")
        ]
        .drop_duplicates(
            "asin",
            keep="first",
        )
    )

    metadata_columns = [
        column
        for column in [
            "title",
            "brand",
            "keyword_list",
            "image_url",
            "product_url",
            "price",
            "avg_rating",
        ]
        if column in products.columns
    ]

    if not metadata_columns:
        return assignments

    catalog_metadata = products[
        ["asin", *metadata_columns]
    ].copy()

    catalog_metadata = catalog_metadata.rename(
        columns={
            column: f"catalog_{column}"
            for column in metadata_columns
        }
    )

    assignments = assignments.merge(
        catalog_metadata,
        on="asin",
        how="left",
        validate="one_to_one",
    )

    for column in metadata_columns:
        catalog_column = f"catalog_{column}"

        if column not in assignments.columns:
            assignments[column] = assignments[
                catalog_column
            ]
        else:
            missing_values = _missing_text_mask(
                assignments[column]
            )

            assignments.loc[
                missing_values,
                column,
            ] = assignments.loc[
                missing_values,
                catalog_column,
            ]

        assignments = assignments.drop(
            columns=catalog_column
        )

    return assignments


@lru_cache(maxsize=1)
def load_thumbnail_data():
    """
    Load and validate precomputed thumbnail-grouping artifacts.

    DINOv2 is not loaded here because the existing catalogue
    already has embeddings and cluster assignments.
    """

    required_files = [
        ASSIGNMENTS_PATH,
        INTERPRETATION_PATH,
        EMBEDDINGS_PATH,
        CENTROIDS_PATH,
        METADATA_PATH,
    ]

    _validate_required_files(
        required_files
    )

    assignments = pd.read_csv(
        ASSIGNMENTS_PATH,
        dtype={
            "asin": str,
            "canonical_asin": str,
        },
    )

    interpretations = pd.read_csv(
        INTERPRETATION_PATH,
    )

    embeddings = np.load(
        EMBEDDINGS_PATH,
        allow_pickle=False,
    ).astype(np.float32)

    centroids = np.load(
        CENTROIDS_PATH,
        allow_pickle=False,
    ).astype(np.float32)

    with open(
        METADATA_PATH,
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    required_assignment_columns = {
        "asin",
        "canonical_asin",
        "cluster_id",
        "cluster_name",
    }

    missing_assignment_columns = (
        required_assignment_columns
        - set(assignments.columns)
    )

    if missing_assignment_columns:
        raise ValueError(
            "Missing assignment columns: "
            + ", ".join(
                sorted(
                    missing_assignment_columns
                )
            )
        )

    required_interpretation_columns = {
        "cluster_id",
        "cluster_name",
    }

    missing_interpretation_columns = (
        required_interpretation_columns
        - set(interpretations.columns)
    )

    if missing_interpretation_columns:
        raise ValueError(
            "Missing interpretation columns: "
            + ", ".join(
                sorted(
                    missing_interpretation_columns
                )
            )
        )

    assignments = _clean_asin_column(
        assignments
    )

    assignments["canonical_asin"] = (
        assignments["canonical_asin"]
        .fillna(assignments["asin"])
        .astype(str)
        .str.strip()
        .str.upper()
    )

    assignments["cluster_id"] = (
        pd.to_numeric(
            assignments["cluster_id"],
            errors="raise",
        )
        .astype(int)
    )

    interpretations["cluster_id"] = (
        pd.to_numeric(
            interpretations["cluster_id"],
            errors="raise",
        )
        .astype(int)
    )

    # Add titles, brands, keywords and display URLs.
    assignments = _add_product_metadata(
        assignments
    )

    assignments = assignments.reset_index(
        drop=True
    )

    interpretations = interpretations.reset_index(
        drop=True
    )

    if len(assignments) != len(embeddings):
        raise ValueError(
            "Assignment and embedding row counts do not match. "
            f"Assignments: {len(assignments)}, "
            f"embeddings: {len(embeddings)}."
        )

    if embeddings.ndim != 2:
        raise ValueError(
            "Thumbnail embeddings must be a "
            "two-dimensional matrix."
        )

    if centroids.ndim != 2:
        raise ValueError(
            "Cluster centroids must be a "
            "two-dimensional matrix."
        )

    if embeddings.shape[1] != centroids.shape[1]:
        raise ValueError(
            "Embedding and centroid dimensions do not match. "
            f"Embeddings: {embeddings.shape[1]}, "
            f"centroids: {centroids.shape[1]}."
        )

    embedding_norms = np.linalg.norm(
        embeddings,
        axis=1,
        keepdims=True,
    )

    if np.any(embedding_norms == 0):
        raise ValueError(
            "Thumbnail embeddings contain zero vectors."
        )

    embeddings = (
        embeddings
        / embedding_norms
    ).astype(np.float32)

    centroid_norms = np.linalg.norm(
        centroids,
        axis=1,
        keepdims=True,
    )

    if np.any(centroid_norms == 0):
        raise ValueError(
            "Cluster centroids contain zero vectors."
        )

    centroids = (
        centroids
        / centroid_norms
    ).astype(np.float32)

    expected_clusters = int(
        metadata.get(
            "selected_k",
            len(centroids),
        )
    )

    if len(centroids) != expected_clusters:
        raise ValueError(
            "The centroid count does not match the metadata. "
            f"Centroids: {len(centroids)}, "
            f"metadata selected_k: {expected_clusters}."
        )

    actual_clusters = assignments[
        "cluster_id"
    ].nunique()

    if actual_clusters != expected_clusters:
        raise ValueError(
            "The assignment cluster count does not match "
            "the metadata. "
            f"Assignments: {actual_clusters}, "
            f"metadata selected_k: {expected_clusters}."
        )

    return (
        assignments,
        interpretations,
        embeddings,
        centroids,
        metadata,
    )


@lru_cache(maxsize=1)
def load_thumbnail_models():
    """
    Load PCA and KMeans only when explicitly required.

    Normal catalogue exploration uses the precomputed
    embeddings and assignments, so these models do not
    need to load when the page initially opens.
    """

    _validate_required_files(
        [
            PCA_MODEL_PATH,
            KMEANS_MODEL_PATH,
        ]
    )

    pca_model = joblib.load(
        PCA_MODEL_PATH
    )

    kmeans_model = joblib.load(
        KMEANS_MODEL_PATH
    )

    return pca_model, kmeans_model


@lru_cache(maxsize=1)
def load_local_thumbnail_index():
    """
    Create an ASIN-to-local-image-path lookup.

    The application prefers downloaded images and falls
    back to image URLs when a local image is unavailable.
    """

    image_lookup = {}

    for image_directory in LOCAL_IMAGE_DIRECTORIES:
        if not image_directory.exists():
            continue

        for image_path in image_directory.rglob("*"):
            if not image_path.is_file():
                continue

            if (
                image_path.suffix.lower()
                not in SUPPORTED_IMAGE_EXTENSIONS
            ):
                continue

            match = ASIN_PATTERN.search(
                image_path.stem.upper()
            )

            if not match:
                continue

            asin = match.group(1).upper()

            image_lookup.setdefault(
                asin,
                image_path,
            )

    return image_lookup