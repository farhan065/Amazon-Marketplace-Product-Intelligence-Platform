from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

PROCESSED_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "price_tier"
)

PREDICTIONS_PATH = (
    PROCESSED_DATA_DIR
    / "price_tier_predictions.csv"
)

MODEL_PATH = (
    MODEL_DIR
    / "price_tier_pipeline.joblib"
)

MODEL_DECISION_PATH = (
    MODEL_DIR
    / "price_tier_model_decision.json"
)

MODEL_METADATA_PATH = (
    MODEL_DIR
    / "price_tier_metadata.json"
)

FEATURE_SUMMARY_PATH = (
    MODEL_DIR
    / "price_tier_feature_summary.csv"
)

LABEL_ORDER = [
    "Budget",
    "Mid-range",
    "Premium",
]

MODEL_FEATURES = [
    "combined_text",
    "brand",
    "keyword",
    "marketplace",
    "log_review_count",
    "average_rating",
    "title_length",
    "description_length",
    "title_missing",
    "description_missing",
    "brand_missing",
    "review_count_missing",
    "rating_missing",
]