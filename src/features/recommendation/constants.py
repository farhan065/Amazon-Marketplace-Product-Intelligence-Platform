from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "recommendation"
)

VECTORIZER_PATH = (
    MODEL_DIR
    / "final_tfidf_vectorizer.joblib"
)

TFIDF_MATRIX_PATH = (
    MODEL_DIR
    / "final_tfidf_matrix.npz"
)

PRODUCT_INDEX_PATH = (
    MODEL_DIR
    / "final_recommendation_product_index.csv"
)

METADATA_PATH = (
    MODEL_DIR
    / "final_recommendation_metadata.json"
)

DEFAULT_TOP_K = 5