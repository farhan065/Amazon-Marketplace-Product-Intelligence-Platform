from pathlib import Path


# ============================================================
# Project directories
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "thumbnail_grouping"
)

DATA_DIR = (
    PROJECT_ROOT
    / "data"
)

PROCESSED_DATA_DIR = (
    DATA_DIR
    / "processed"
)


# ============================================================
# Product dataset locations
# ============================================================

PRODUCT_DATA_CANDIDATES = [
    PROCESSED_DATA_DIR
    / "products_recommendation_clean.csv",

    DATA_DIR
    / "raw"
    / "amazon_products.csv",

    DATA_DIR
    / "amazon_products.csv",
]


# ============================================================
# Thumbnail assignment and interpretation artifacts
# ============================================================

ASSIGNMENTS_PATH = (
    PROCESSED_DATA_DIR
    / "thumbnail_group_assignments.csv"
)

INTERPRETATION_PATH = (
    PROCESSED_DATA_DIR
    / "thumbnail_cluster_interpretation.csv"
)

REPRESENTATIVES_PATH = (
    PROCESSED_DATA_DIR
    / "thumbnail_cluster_representatives.csv"
)


# ============================================================
# Trained model artifacts
# ============================================================

EMBEDDINGS_PATH = (
    MODEL_DIR
    / "thumbnail_embeddings.npy"
)

CENTROIDS_PATH = (
    MODEL_DIR
    / "thumbnail_cluster_centroids.npy"
)

PCA_MODEL_PATH = (
    MODEL_DIR
    / "thumbnail_feature_pca.joblib"
)

KMEANS_MODEL_PATH = (
    MODEL_DIR
    / "thumbnail_kmeans.joblib"
)

METADATA_PATH = (
    MODEL_DIR
    / "thumbnail_model_metadata.json"
)


# ============================================================
# Downloaded thumbnail locations
# ============================================================

LOCAL_IMAGE_DIRECTORIES = [
    DATA_DIR
    / "images"
    / "thumbnail_images",

    DATA_DIR
    / "images",

    PROCESSED_DATA_DIR
    / "thumbnail_clean_images",
]

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}