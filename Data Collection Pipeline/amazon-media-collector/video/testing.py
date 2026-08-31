from __future__ import annotations

import asyncio
import csv
import html
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from playwright.async_api import BrowserContext, Page, async_playwright
except ModuleNotFoundError:  # Allows a clear installation message below.
    BrowserContext = Any
    Page = Any
    async_playwright = None


INPUT_FILE = "amazon_products.csv"
COOKIES_FILE = "cookies.json"
OUTPUT_FILE = "supplier_video_results.csv"
LOG_FILE = "supplier_video_log.csv"
DEBUG_FOLDER = "supplier_video_debug"

PAGE_TIMEOUT_MS = 45_000
VIDEO_WAIT_SECONDS = 12
MIN_DELAY_SECONDS = 2
MAX_DELAY_SECONDS = 4

OUTPUT_COLUMNS = ["asin", "keyword", "product_url", "supplier_video_url"]
LOG_COLUMNS = ["timestamp", "asin", "status", "details"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def normalize_video_url(url: str) -> str | None:
    """Accept only reusable Amazon MP4/HLS URLs; reject blob and VDP URLs."""
    url = html.unescape(clean(url)).replace("\\/", "/")
    if not url.startswith("https://") or url.startswith("blob:"):
        return None

    host = (urlparse(url).hostname or "").lower()
    if not (
        host == "m.media-amazon.com"
        or host.endswith(".media-amazon.com")
        or host.endswith(".ssl-images-amazon.com")
    ):
        return None

    path = urlparse(url).path.lower()
    if path.endswith(".mp4") or path.endswith(".m3u8"):
        return url

    # Amazon may request an HLS .ts segment before exposing the playlist.
    if path.endswith(".ts") and re.search(r"\.hls\d+_\d+\.ts$", path):
        return re.sub(r"\.hls\d+_\d+\.ts(?=\?|$)", ".hls.m3u8", url)

    return None


def find_urls(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            found.extend(find_urls(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(find_urls(child))
    elif isinstance(value, str):
        candidate = normalize_video_url(value)
        if candidate:
            found.append(candidate)
    return list(dict.fromkeys(found))


def supplier_urls_from_gallery_html(page_html: str) -> tuple[bool, list[str]]:
    """Read only the top image-block JSON, never the lower Product Videos widget."""
    gallery_has_video = False
    urls: list[str] = []

    pattern = r"jQuery\.parseJSON\('(\{.*?\})'\)"
    for raw_json in re.findall(pattern, page_html, flags=re.DOTALL):
        if '"colorImages"' not in raw_json or '"videos"' not in raw_json:
            continue
        try:
            config = json.loads(raw_json.replace("\\'", "'"))
        except json.JSONDecodeError:
            continue

        videos = config.get("videos") or []
        if videos:
            gallery_has_video = True
            urls.extend(find_urls(videos))

    return gallery_has_video, list(dict.fromkeys(urls))


def load_cookies(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8-sig"))
    cookies = data.get("cookies", []) if isinstance(data, dict) else data
    if not isinstance(cookies, list):
        raise ValueError("cookies.json must contain a cookie list or Playwright storage state")

    accepted: list[dict[str, Any]] = []
    same_site = {
        "strict": "Strict",
        "lax": "Lax",
        "none": "None",
        "no_restriction": "None",
    }
    for source in cookies:
        if not isinstance(source, dict) or not source.get("name"):
            continue
        cookie = {
            key: source[key]
            for key in ("name", "value", "domain", "path", "expires", "httpOnly", "secure")
            if key in source and source[key] is not None
        }
        if "expires" not in cookie and "expirationDate" in source:
            cookie["expires"] = source["expirationDate"]
        if source.get("sameSite"):
            mapped = same_site.get(str(source["sameSite"]).lower())
            if mapped:
                cookie["sameSite"] = mapped
        if "domain" not in cookie and source.get("url"):
            cookie["url"] = source["url"]
        if "domain" in cookie:
            cookie.setdefault("path", "/")
        accepted.append(cookie)
    return accepted


def append_row(path: Path, columns: list[str], row: dict[str, Any]) -> None:
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


async def challenge_present(page: Page) -> bool:
    title = (await page.title()).lower()
    body = (await page.locator("body").inner_text(timeout=5_000)).lower()
    captcha_signs = (
        "robot check",
        "enter the characters you see below",
        "type the characters you see in this image",
        "sorry, we just need to make sure you're not a robot",
    )
    if any(sign in title or sign in body for sign in captcha_signs):
        return True
    return "amazon sign-in" in title or await page.locator("#ap_email, form[name='signIn']").count() > 0


async def gallery_video_button(page: Page):
    """Return a clickable video thumbnail from #altImages/#imageBlock only."""
    actions = page.locator("#altImages [data-thumb-action]")
    for index in range(await actions.count()):
        item = actions.nth(index)
        raw = await item.get_attribute("data-thumb-action") or ""
        try:
            metadata = json.loads(raw)
        except json.JSONDecodeError:
            metadata = {}
        if clean(metadata.get("type")).lower() == "video":
            return item

    selectors = (
        "#altImages li.videoThumbnail",
        "#altImages [class*='videoThumbnail']",
        "#imageBlock #videoBlockIngress",
        "#imageBlock [data-action*='video']",
    )
    for selector in selectors:
        item = page.locator(selector).first
        if await item.count() and await item.is_visible():
            return item
    return None


async def first_gallery_dom_url(page: Page) -> str | None:
    selectors = (
        "#imageBlock video[src]",
        "#imageBlock video source[src]",
        "#imageBlock [data-video-url]",
        "#ivVideosTab video[src]",
        "#ivVideosTab video source[src]",
    )
    for selector in selectors:
        elements = page.locator(selector)
        for index in range(await elements.count()):
            element = elements.nth(index)
            value = (
                await element.get_attribute("src")
                or await element.get_attribute("data-video-url")
                or ""
            )
            candidate = normalize_video_url(value)
            if candidate:
                return candidate
    return None


async def save_debug(page: Page, folder: Path, asin: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{asin}.html").write_text(await page.content(), encoding="utf-8")
    await page.screenshot(path=str(folder / f"{asin}.png"), full_page=False)


async def collect_supplier_video(page: Page, product_url: str, asin: str, debug: Path):
    captured: asyncio.Future[str] = asyncio.get_running_loop().create_future()
    capture_enabled = False

    def observe_response(response) -> None:
        if not capture_enabled or captured.done():
            return
        candidate = normalize_video_url(response.url)
        if candidate:
            captured.set_result(candidate)

    page.on("response", observe_response)
    await page.goto(product_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    await asyncio.sleep(random.SystemRandom().uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))

    if await challenge_present(page):
        return "N/A", "BLOCKED", "CAPTCHA or sign-in page detected"

    page_html = await page.content()
    gallery_has_video, embedded_urls = supplier_urls_from_gallery_html(page_html)
    if embedded_urls:
        return embedded_urls[0], "FOUND", "Supplier URL found in top-gallery metadata"

    dom_url = await first_gallery_dom_url(page)
    if dom_url:
        return dom_url, "FOUND", "Supplier URL found in top-gallery DOM"

    button = await gallery_video_button(page)
    if not gallery_has_video and button is None:
        return "N/A", "MISSING", "No supplier video exists in the top gallery"

    if button is None:
        await save_debug(page, debug, asin)
        return "N/A", "FAILED", "Gallery metadata reports a video, but its button was not found"

    capture_enabled = True
    await button.click(force=True)

    try:
        video_url = await asyncio.wait_for(captured, timeout=VIDEO_WAIT_SECONDS)
        return video_url, "FOUND", "Supplier stream captured after gallery click"
    except asyncio.TimeoutError:
        dom_url = await first_gallery_dom_url(page)
        if dom_url:
            return dom_url, "FOUND", "Supplier URL found in the opened gallery player"
        await save_debug(page, debug, asin)
        return "N/A", "FAILED", "Supplier gallery video opened, but no reusable URL appeared"


async def run() -> None:
    root = Path(__file__).resolve().parent
    input_path = root / INPUT_FILE
    cookie_path = root / COOKIES_FILE
    output_path = root / OUTPUT_FILE
    log_path = root / LOG_FILE
    debug_path = root / DEBUG_FOLDER

    if not input_path.exists():
        print(f"[ERROR] Input CSV not found: {input_path}")
        return
    if async_playwright is None:
        print("[ERROR] Playwright is not installed. Run: python -m pip install -r requirements.txt")
        return

    with input_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        fields = {clean(field).lower() for field in (reader.fieldnames or [])}
        missing = {"asin", "keyword", "product_url"} - fields
        if missing:
            print(f"[ERROR] Missing CSV column(s): {', '.join(sorted(missing))}")
            return
        rows = list(reader)

    output_path.unlink(missing_ok=True)
    log_path.unlink(missing_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        cookies = load_cookies(cookie_path)
        if cookies:
            await context.add_cookies(cookies)
            print(f"[COOKIES] Loaded {len(cookies)} session cookies")
        else:
            print("[COOKIES] cookies.json not found or empty; continuing without it")

        try:
            for number, original in enumerate(rows, start=1):
                row = {clean(key).lower(): clean(value) for key, value in original.items()}
                asin = row["asin"].upper()
                keyword = row["keyword"]
                product_url = row["product_url"]
                page = await context.new_page()

                try:
                    video_url, status, details = await collect_supplier_video(
                        page, product_url, asin, debug_path
                    )
                except Exception as error:
                    video_url, status, details = "N/A", "FAILED", str(error)
                finally:
                    await page.close()

                append_row(
                    output_path,
                    OUTPUT_COLUMNS,
                    {
                        "asin": asin,
                        "keyword": keyword,
                        "product_url": product_url,
                        "supplier_video_url": video_url,
                    },
                )
                append_row(
                    log_path,
                    LOG_COLUMNS,
                    {
                        "timestamp": utc_now(),
                        "asin": asin,
                        "status": status,
                        "details": details,
                    },
                )
                print(f"[{number}/{len(rows)}] {asin}: {status} -> {video_url}")

                if status == "BLOCKED":
                    print("[STOPPED] Refresh cookies or complete sign-in manually, then run again.")
                    break
        finally:
            await context.close()
            await browser.close()

    print(f"[COMPLETED] Results: {output_path}")
    print(f"[COMPLETED] Log: {log_path}")


if __name__ == "__main__":
    asyncio.run(run())
