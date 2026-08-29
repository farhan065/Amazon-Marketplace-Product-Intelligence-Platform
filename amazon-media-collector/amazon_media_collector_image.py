from __future__ import annotations

import csv
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


INPUT_FILE = "amazon_products.csv"
OUTPUT_FILE = "image_download_results.csv"
LOG_FILE = "image_download_log.csv"
IMAGE_ROOT = "downloaded_images"

REQUIRED_COLUMNS = {"asin", "keyword", "product_url", "image_url"}
OUTPUT_COLUMNS = [
    "asin", "keyword", "product_url", "image_url", "local_image_path", "status"
]
LOG_COLUMNS = ["timestamp", "asin", "image_url", "status", "details"]


def safe_name(value: str, fallback: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]', "_", (value or "").strip())
    value = re.sub(r"\s+", " ", value).strip(" ._")
    return (value or fallback)[:100]


def marketplace_name(product_url: str) -> str:
    host = (urlparse(product_url).hostname or "").lower().removeprefix("www.")
    names = {
        "amazon.com": "amazon_us",
        "amazon.co.uk": "amazon_uk",
        "amazon.ca": "amazon_ca",
        "amazon.in": "amazon_in",
        "amazon.com.au": "amazon_au",
        "amazon.de": "amazon_de",
        "amazon.fr": "amazon_fr",
        "amazon.it": "amazon_it",
        "amazon.es": "amazon_es",
        "amazon.co.jp": "amazon_jp",
    }
    return names.get(host, safe_name(host, "amazon_unknown"))


def image_extension(image_url: str, content_type: str) -> str:
    url_extension = Path(urlparse(image_url).path).suffix.lower()
    if url_extension in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}:
        return ".jpg" if url_extension == ".jpeg" else url_extension
    extension = mimetypes.guess_extension(content_type.split(";", 1)[0].strip()) or ".jpg"
    return ".jpg" if extension in {".jpeg", ".jpe"} else extension


def write_log(log_path: Path, row: dict[str, str]) -> None:
    new_file = not log_path.exists()
    with log_path.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=LOG_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def download_image(image_url: str, image_root: Path, filename: str) -> Path:
    request = Request(
        image_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=30) as response:
        content_type = response.headers.get("Content-Type", "")
        if not content_type.lower().startswith("image/"):
            raise ValueError(f"URL returned '{content_type}', not an image")
        image_data = response.read()

    image_root.mkdir(parents=True, exist_ok=True)
    image_path = image_root / f"{filename}{image_extension(image_url, content_type)}"
    image_path.write_bytes(image_data)
    return image_path.resolve()


def main() -> None:
    project_folder = Path(__file__).resolve().parent
    input_path = project_folder / INPUT_FILE
    output_path = project_folder / OUTPUT_FILE
    log_path = project_folder / LOG_FILE
    image_root = project_folder / IMAGE_ROOT

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        return

    with input_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        columns = {column.strip().lower() for column in (reader.fieldnames or [])}
        missing = REQUIRED_COLUMNS - columns
        if missing:
            print(f"[ERROR] Missing CSV column(s): {', '.join(sorted(missing))}")
            return
        rows = list(reader)

    results: list[dict[str, str]] = []
    for number, row in enumerate(rows, start=1):
        normalized = {
            str(key).strip().lower(): (value or "").strip() for key, value in row.items()
        }
        asin = normalized["asin"].upper()
        keyword = normalized["keyword"]
        product_url = normalized["product_url"]
        image_url = normalized["image_url"]
        local_path, status, details = "N/A", "FAILED", ""

        try:
            if not asin or not image_url or image_url.upper() == "N/A":
                raise ValueError("ASIN or image_url is missing")
            image_name = "_".join(
                (
                    safe_name(keyword, "no_keyword"),
                    safe_name(asin, "no_asin"),
                    marketplace_name(product_url),
                )
            )
            local_path = str(download_image(image_url, image_root, image_name))
            status, details = "DOWNLOADED", "Image downloaded successfully"
            print(f"[{number}/{len(rows)}] {asin}: downloaded")
        except Exception as error:
            details = str(error)
            print(f"[{number}/{len(rows)}] {asin or 'unknown'}: failed - {error}")

        results.append(
            {
                "asin": asin,
                "keyword": keyword,
                "product_url": product_url,
                "image_url": image_url,
                "local_image_path": local_path,
                "status": status,
            }
        )
        write_log(
            log_path,
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "asin": asin,
                "image_url": image_url,
                "status": status,
                "details": details,
            },
        )

    with output_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    print(f"[COMPLETED] Results: {output_path}")
    print(f"[COMPLETED] Log: {log_path}")
    print(f"[COMPLETED] Images: {image_root}")


if __name__ == "__main__":
    main()
