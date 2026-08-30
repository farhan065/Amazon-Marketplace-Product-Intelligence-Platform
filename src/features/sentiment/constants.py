from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

PROCESSED_DATA_DIR = (
    PROJECT_ROOT / "data" / "processed"
)

REVIEWS_SENTIMENT_PATH = (
    PROCESSED_DATA_DIR
    / "reviews_sentiment_app.csv"
)

PRODUCT_SENTIMENT_PATH = (
    PROCESSED_DATA_DIR
    / "product_sentiment_summary.csv"
)

KEYWORD_SENTIMENT_PATH = (
    PROCESSED_DATA_DIR
    / "keyword_sentiment_summary.csv"
)

LOCAL_MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "sentiment"
    / "roberta_inference"
)

HUGGINGFACE_MODEL_NAME = (
    "cardiffnlp/"
    "twitter-roberta-base-sentiment-latest"
)

SENTIMENT_LABELS = (
    "negative",
    "neutral",
    "positive",
)

MAX_TOKEN_LENGTH = 512
LOW_CONFIDENCE_THRESHOLD = 0.70