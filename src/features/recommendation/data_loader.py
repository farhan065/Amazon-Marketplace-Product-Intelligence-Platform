import json
from functools import lru_cache

import joblib
import pandas as pd
from scipy.sparse import load_npz

from .constants import (
    METADATA_PATH,
    PRODUCT_INDEX_PATH,
    TFIDF_MATRIX_PATH,
    VECTORIZER_PATH,
)


@lru_cache(maxsize=1)
def load_recommendation_assets():
    required_paths = [
        VECTORIZER_PATH,
        TFIDF_MATRIX_PATH,
        PRODUCT_INDEX_PATH,
        METADATA_PATH,
    ]

    missing_paths = [
        path
        for path in required_paths
        if not path.exists()
    ]

    if missing_paths:
        missing_text = "\n".join(
            str(path)
            for path in missing_paths
        )

        raise FileNotFoundError(
            "Missing recommendation artifacts:\n"
            f"{missing_text}"
        )

    vectorizer = joblib.load(
        VECTORIZER_PATH
    )

    tfidf_matrix = load_npz(
        TFIDF_MATRIX_PATH
    ).tocsr()

    products = pd.read_csv(
        PRODUCT_INDEX_PATH,
        dtype={"asin": str},
    )

    products["asin"] = (
        products["asin"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    with open(
        METADATA_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    if len(products) != tfidf_matrix.shape[0]:
        raise ValueError(
            "Product index and TF-IDF matrix "
            "have different row counts."
        )

    if products["asin"].duplicated().any():
        raise ValueError(
            "Duplicate ASINs found in product index."
        )

    asin_to_index = {
        asin: index
        for index, asin
        in enumerate(products["asin"])
    }

    return (
        products,
        vectorizer,
        tfidf_matrix,
        metadata,
        asin_to_index,
    )