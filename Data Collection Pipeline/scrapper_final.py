import asyncio
import csv
import hashlib
import html
import json
import os
import random
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
from openpyxl import load_workbook
from playwright.async_api import async_playwright

# Configuration
KEYWORDS_FILE = "Search keyword Lists.xlsx"
KEYWORD_COLUMN = "Search Keywords"
OUTPUT_FILE = "amazon_products.csv"
LOG_FILE = "scraping_log.csv"
COOKIES_FILE = "cookies.json"
MAX_REVIEW_PAGES = 2
PAGE_TIMEOUT = 45_000
CHALLENGE_TIMEOUT = 180_000

COLUMNS = [
    "asin", "keyword", "product_url", "title", "price", "brand",
    "description", "image_url", "avg_rating", "rating_count", "reviews",
]


def clean(value):
    if not value:
        return "N/A"
    value = html.unescape(str(value))
    try:
        if any(x in value for x in ("â€", "Ã", "Â", "ðŸ")):
            value = value.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    value = unicodedata.normalize("NFKC", value).replace("\u00a0", " ").replace("\ufeff", "")
    value = "".join(c for c in value if c in "\n\t" or not unicodedata.category(c).startswith("C"))
    return re.sub(r"\s+", " ", value).strip() or "N/A"


def text(soup, *selectors):
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            value = clean(element.get_text(" ", strip=True))
            if value != "N/A":
                return value
    return "N/A"


def log(url, status, code=200):
    try:
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([datetime.now(timezone.utc).isoformat(), url, status, code])
    except Exception as exc:
        print(f"[WARNING] Log failed: {exc}")


def load_keywords():
    if not os.path.exists(KEYWORDS_FILE):
        raise FileNotFoundError(f"'{KEYWORDS_FILE}' not found.")

    wb = load_workbook(KEYWORDS_FILE, read_only=True, data_only=True)
    try:
        ws = wb.active
        headers = {clean(c.value).casefold(): c.column for c in ws[1] if c.value is not None}
        column = headers.get(KEYWORD_COLUMN.casefold())
        if not column:
            raise ValueError(f"Column '{KEYWORD_COLUMN}' not found.")

        keywords, seen = [], set()
        for (value,) in ws.iter_rows(min_row=2, min_col=column, max_col=column, values_only=True):
            keyword = clean(value)
            key = keyword.casefold()
            if keyword != "N/A" and key not in seen:
                seen.add(key)
                keywords.append(keyword)
        if not keywords:
            raise ValueError("No search keywords found.")
        return keywords
    finally:
        wb.close()


def blocked(soup):
    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    if "captcha" in title or "robot check" in title or soup.select_one("#captchacharacters"):
        return "CAPTCHA"
    if "amazon sign-in" in title or soup.select_one("form#signIn, #ap_email"):
        return "SIGN_IN"
    return None


async def pause():
    await asyncio.sleep(random.uniform(2, 5))


async def scroll(page):
    for _ in range(random.randint(2, 3)):
        await page.mouse.wheel(0, random.randint(350, 700))
        await asyncio.sleep(random.uniform(.5, 1))


async def wait_for_access(page):
    deadline = asyncio.get_running_loop().time() + CHALLENGE_TIMEOUT / 1000
    announced = False
    while asyncio.get_running_loop().time() < deadline:
        soup = BeautifulSoup(await page.content(), "html.parser")
        state = blocked(soup)
        if not state:
            return soup
        if not announced:
            print(f"[ACTION REQUIRED] Solve Amazon {state} in the browser.")
            announced = True
        await page.wait_for_timeout(2000)
    return None


async def open_page(page, url, referer=None):
    try:
        response = await page.goto(
            url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT, referer=referer
        )
        await scroll(page)
        await pause()
        soup = await wait_for_access(page)
        if soup is None:
            log(url, "BLOCKED", response.status if response else 503)
        return soup, response
    except Exception as exc:
        print(f"[ERROR] Failed to load {url}: {exc}")
        log(url, "ERROR", 500)
        return None, None


def parse_search(soup, keyword):
    products, seen = [], set()
    for item in soup.select("div[data-asin]"):
        asin = item.get("data-asin", "").strip()
        if len(asin) == 10 and asin not in seen:
            seen.add(asin)
            products.append({
                "asin": asin,
                "keyword": keyword,
                "product_url": f"https://www.amazon.com/dp/{asin}",
            })
    return products


def parse_product(soup):
    image = soup.select_one("#landingImage, #imgBlkFront, #main-image")
    image_url = "N/A" if not image else image.get("data-old-hires") or image.get("src") or "N/A"

    return {
        "title": text(soup, "#productTitle", "#titleSpan", "#title"),
        "price": text(soup, ".a-price .a-offscreen", "#priceblock_ourprice", "#priceblock_dealprice"),
        "brand": text(soup, "#bylineInfo", "tr.po-brand td.a-span9 span", ".po-brand .a-span9"),
        "description": text(soup, "#feature-bullets ul", "#productDescription", "#productFactsDesktopExpander"),
        "image_url": image_url,
        "avg_rating": text(soup, "#acrPopover span.a-size-base", "span[data-hook='rating-out-of-text']", "i.a-icon-star span.a-icon-alt"),
        "rating_count": text(soup, "#acrCustomerReviewText", "#acrCustomerReviewLink span"),
    }


def review_title(review):
    title = text(review, "[data-hook='review-title']", ".review-title")
    return clean(re.sub(r"^\d(?:\.\d)?\s+out of\s+5\s+stars?\s*", "", title, flags=re.I))


def parse_reviews(soup):
    blocks = soup.select("[data-hook='review']") or soup.select("[data-hook='review-card']")
    reviews = []

    for review in blocks:
        author = text(review, "[data-hook='review-author'] .a-profile-name", ".a-profile-name")
        headline = review_title(review)
        body = text(review, "[data-hook='review-body']", ".review-text-content")
        rating = text(
            review,
            "[data-hook='review-star-rating'] .a-icon-alt",
            "[data-hook='cmps-review-star-rating'] .a-icon-alt",
            "span.a-icon-alt",
        )
        date = text(review, "[data-hook='review-date']", ".review-date")
        if headline == "N/A" and body == "N/A":
            continue

        review_id = review.get("id") or review.get("data-review-id")
        if not review_id:
            raw = "|".join((author, headline, body, rating, date)).encode("utf-8")
            review_id = "generated_" + hashlib.sha1(raw).hexdigest()

        reviews.append({
            "review_id": review_id,
            "reviewer_name": author,
            "headline": headline,
            "review_text": body,
            "rating": rating,
            "review_date": date,
        })
    return reviews


async def get_reviews(page, asin, product_soup, product_url):
    reviews = parse_reviews(product_soup)
    seen = {r["review_id"] for r in reviews}

    link = product_soup.select_one(
        "a[data-hook='see-all-reviews-link-foot'][href*='product-reviews'], "
        "#reviews-medley-footer a[href*='product-reviews']"
    )
    next_url = (
        urljoin(product_url, link["href"])
        if link and link.get("href")
        else f"https://www.amazon.com/product-reviews/{asin}/?reviewerType=all_reviews"
    )

    for page_number in range(1, MAX_REVIEW_PAGES + 1):
        soup, response = await open_page(page, next_url, product_url if page_number == 1 else None)
        if soup is None:
            break

        current = parse_reviews(soup)
        if not current:
            log(next_url, "EMPTY", response.status if response else 200)
            break

        for review in current:
            if review["review_id"] not in seen:
                seen.add(review["review_id"])
                reviews.append(review)
        log(next_url, "SUCCESS", response.status if response else 200)

        next_link = soup.select_one(
            "li.a-last:not(.a-disabled) a[href], "
            "a[data-hook='pagination-next'][href], a[aria-label='Next page'][href]"
        )
        if not next_link or not next_link.get("href"):
            break
        next_url = urljoin(page.url, next_link["href"])

    return reviews


def write_product(item, data, reviews):
    row = {**item, **data, "reviews": json.dumps(reviews, ensure_ascii=False)}
    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8-sig") as f:
        csv.DictWriter(f, fieldnames=COLUMNS).writerow(row)


async def load_cookies(context):
    if not os.path.exists(COOKIES_FILE):
        return
    try:
        with open(COOKIES_FILE, encoding="utf-8") as f:
            cookies = json.load(f)
        if isinstance(cookies, dict):
            cookies = cookies.get("cookies", [])
        allowed = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
        cleaned = [{k: v for k, v in c.items() if k in allowed} for c in cookies]
        await context.add_cookies(cleaned)
        print("[INFO] Cookies loaded.")
    except Exception as exc:
        print(f"[WARNING] Cookies not loaded: {exc}")


async def run_pipeline():
    try:
        keywords = load_keywords()
    except Exception as exc:
        print(f"[FATAL] {exc}")
        return

    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp", "target_url", "status", "response_code"])
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        csv.DictWriter(f, fieldnames=COLUMNS).writeheader()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080}, locale="en-US")
        await load_cookies(context)
        page = await context.new_page()

        products = []
        for i, keyword in enumerate(keywords, 1):
            print(f"\n[SEARCH {i}/{len(keywords)}] {keyword}")
            url = f"https://www.amazon.com/s?k={quote_plus(keyword)}"
            soup, response = await open_page(page, url)
            if soup is None:
                continue
            found = parse_search(soup, keyword)
            products.extend(found)
            log(url, "SUCCESS" if found else "EMPTY", response.status if response else 200)
            print(f"[FOUND] {len(found)} product(s)")

        saved = 0
        for i, item in enumerate(products, 1):
            print(f"\n[PRODUCT {i}/{len(products)}] {item['asin']} | {item['keyword']}")
            soup, response = await open_page(page, item["product_url"])
            if soup is None:
                continue

            data = parse_product(soup)
            status = "SUCCESS" if data["title"] != "N/A" else "EMPTY"
            log(item["product_url"], status, response.status if response else 200)
            if status == "EMPTY":
                continue

            reviews = await get_reviews(page, item["asin"], soup, item["product_url"])
            write_product(item, data, reviews)
            saved += 1
            print(f"[SAVED] Reviews: {len(reviews)}")

        try:
            with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                json.dump(await context.cookies(), f, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[WARNING] Cookies not saved: {exc}")

        await browser.close()

    print(f"\n[COMPLETE] Saved {saved}/{len(products)} products to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
