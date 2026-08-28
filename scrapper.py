import asyncio
import csv
import hashlib
import html as html_module
import json
import os
import random
import re
import unicodedata
from urllib.parse import quote_plus, urljoin
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Configuration
KEYWORDS = ["wireless mouse"]  # Replace with target keywords
LOG_FILE = "scraping_log.csv"
OUTPUT_FILE = "amazon_products.csv"
COOKIES_FILE = "cookies.json"
DEBUG_DIR = "debug_html"
MAX_REVIEW_PAGES = 2
PAGE_TIMEOUT_MS = 45_000
MANUAL_CHALLENGE_TIMEOUT_MS = 180_000

def log_attempt(target_url, status, response_code=200):
    """Logs request attempts using timezone-aware UTC datetime."""
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now(timezone.utc).isoformat(), target_url, status, response_code])

async def random_delay(min_sec=2.0, max_sec=7.0):
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)

async def human_scroll(page):
    for _ in range(random.randint(2, 4)):
        scroll_amount = random.randint(300, 700)
        await page.mouse.wheel(0, scroll_amount)
        await asyncio.sleep(random.uniform(0.5, 1.2))

def check_blocking(soup):
    """Detects Amazon CAPTCHA or Login redirection prompts."""
    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    if (
        "captcha" in title
        or "robot check" in title
        or soup.select_one("#captchacharacters, form[action*='validateCaptcha']")
    ):
        return "CAPTCHA"
    if (
        "amazon sign-in" in title
        or "sign in" in title
        or soup.select_one("form[name='signIn'], form#signIn, #ap_email")
    ):
        return "SIGN_IN"
    return None

def extract_text_multi(soup, selectors):
    for sel in selectors:
        elem = soup.select_one(sel)
        if elem and elem.get_text(strip=True):
            return clean_text(elem.get_text(" ", strip=True))
    return "N/A"

def clean_text(value):
    """Normalize scraped text and conservatively repair common mojibake."""
    if not value:
        return "N/A"

    text = html_module.unescape(str(value))

    # Repair text such as "Itâ€™s" only when it contains strong mojibake
    # markers and a Windows-1252 -> UTF-8 round trip is valid.
    mojibake_markers = ("â€", "â€™", "â€œ", "â€“", "â€”", "Ã", "Â", "ðŸ")
    if any(marker in text for marker in mojibake_markers):
        try:
            repaired = text.encode("cp1252").decode("utf-8")
            if sum(repaired.count(marker) for marker in mojibake_markers) < sum(
                text.count(marker) for marker in mojibake_markers
            ):
                text = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ").replace("\ufeff", "")
    text = "".join(
        char
        for char in text
        if char in "\n\t" or not unicodedata.category(char).startswith("C")
    )
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return text.strip() or "N/A"

def extract_review_headline(review):
    """Return the title without Amazon's visually hidden star-rating text."""
    element = review.select_one("[data-hook='review-title'], .review-title")
    if not element:
        return "N/A"

    parts = []
    for text_node in element.find_all(string=True):
        text = text_node.strip()
        if not text:
            continue
        parent_classes = text_node.parent.get("class", []) if text_node.parent else []
        if "a-icon-alt" in parent_classes:
            continue
        if re.fullmatch(
            r"\d(?:\.\d)?\s+out of\s+5\s+stars?",
            text,
            flags=re.IGNORECASE,
        ):
            continue
        parts.append(text)

    headline = " ".join(dict.fromkeys(parts)).strip()
    return clean_text(headline)

def extract_video_url(soup, html_text):
    """Extracts public m.media-amazon.com MP4 links instead of session blob URLs."""
    mp4_matches = re.findall(r'https://m\.media-amazon\.com/images/S/[^"\':\s]+\.mp4', html_text)
    if mp4_matches:
        return mp4_matches[0]
        
    scripts = soup.find_all("script", type="text/javascript")
    for s in scripts:
        if s.string and "videoUrl" in s.string:
            match = re.search(r'"videoUrl"\s*:\s*"([^"]+)"', s.string)
            if match:
                url = match.group(1).replace("\\/", "/")
                if not url.startswith("blob:"):
                    return url
    return "N/A"

def parse_search_page(html, keyword):
    soup = BeautifulSoup(html, "html.parser")
    products = []
    
    items = soup.select("div[data-component-type='s-search-result']")
    if not items:
        items = soup.select("div.s-result-item[data-asin]")
    if not items:
        items = soup.select("div[data-asin]")

    for item in items:
        asin = item.get("data-asin", "").strip()
        if not asin or len(asin) != 10:
            continue
            
        product_url = f"https://www.amazon.com/dp/{asin}"
        products.append({
            "asin": asin,
            "keyword": keyword,
            "product_url": product_url
        })
        
    return products

def parse_product_detail_page(html):
    soup = BeautifulSoup(html, "html.parser")
    
    if check_blocking(soup):
        return None, "BLOCKED"

    title = extract_text_multi(soup, ["#productTitle", "#titleSpan", "h1.a-size-large", "#title"])
    price = extract_text_multi(soup, [".a-price .a-offscreen", "#priceblock_ourprice", "#priceblock_dealprice", ".apexPriceToPay span.a-offscreen", "#corePrice_feature_div .a-offscreen"])
    brand = extract_text_multi(soup, ["#bylineInfo", "tr.po-brand td.a-span9 span", "#a-page .po-brand .a-span9", "a#bylineInfo"])
    description = extract_text_multi(soup, ["#feature-bullets ul", "#productDescription", "#technicalSpecifications_feature_div", "#productFactsDesktopExpander"])
    
    image_url = "N/A"
    img_elem = soup.select_one("#landingImage") or soup.select_one("#imgBlkFront") or soup.select_one("#main-image")
    if img_elem:
        image_url = img_elem.get("data-old-hires") or img_elem.get("src", "N/A")
        
    video_url = extract_video_url(soup, html)
    avg_rating = extract_text_multi(soup, ["i.a-icon-star span.a-icon-alt", "#acrPopover span.a-size-base", "span[data-hook='rating-out-of-text']"])
    rating_count = extract_text_multi(soup, ["#acrCustomerReviewText", "#acrCustomerReviewLink span", "#submitContext_glow"])

    product_data = {
        "title": title,
        "price": price,
        "brand": brand,
        "description": description,
        "image_url": image_url,
        "video_url": video_url,
        "avg_rating": avg_rating,
        "rating_count": rating_count
    }
    
    status = "SUCCESS" if title != "N/A" else "EMPTY"
    return product_data, status

def parse_reviews_from_soup(soup):
    """Extracts reviewer names, headlines, ratings, and body texts across desktop and mobile DOM structures."""
    reviews_list = []
    
    review_blocks = soup.select(
        "[data-hook='review'], "
        "[data-hook='review-card'], "
        "div.a-section.review, "
        "div.customer_review, "
        "article.review"
    )

    # Some layouts nest a data-hook='review' inside a review-card. Keep only
    # the innermost block so a review is not emitted twice.
    nested_ids = {
        id(parent)
        for block in review_blocks
        for parent in block.parents
        if parent in review_blocks
    }
    review_blocks = [block for block in review_blocks if id(block) not in nested_ids]
    
    for idx, rev in enumerate(review_blocks):
        id_holder = rev.select_one("[id^='customer_review-'], [data-review-id]")
        rev_id = rev.get("id") or rev.get("data-review-id")
        if not rev_id and id_holder:
            rev_id = id_holder.get("id") or id_holder.get("data-review-id")
        author = extract_text_multi(rev, [
            "[data-hook='review-author'] .a-profile-name",
            ".a-profile-name",
            "span.a-profile-name",
            "div.a-profile-content span"
        ])
        
        headline = extract_review_headline(rev)
        
        body = extract_text_multi(rev, [
            "span[data-hook='review-body'] span",
            "span[data-hook='review-body']",
            "[data-hook='review-body']",
            "div[data-hook='review-collapsed'] span",
            ".review-text-content span",
            ".review-text-content"
        ])
        
        rev_rating = extract_text_multi(rev, [
            "i[data-hook='review-star-rating'] span",
            "i[data-hook='cmps-review-star-rating'] span",
            "[data-hook='review-star-rating'] .a-icon-alt",
            "[data-hook='cmps-review-star-rating'] .a-icon-alt",
            "span.a-icon-alt"
        ])
        
        date_str = extract_text_multi(rev, ["[data-hook='review-date']", ".review-date"])
        
        if headline == "N/A" and body == "N/A":
            continue

        if not rev_id:
            fingerprint = "\x1f".join(
                [author, headline, body, rev_rating, date_str]
            ).encode("utf-8", errors="ignore")
            rev_id = "generated_" + hashlib.sha1(fingerprint).hexdigest()

        reviews_list.append({
            "review_id": rev_id,
            "reviewer_name": author,
            "headline": headline,
            "review_text": body,
            "rating": rev_rating,
            "review_date": date_str
        })
        
    return reviews_list

def save_debug_html(asin, page_number, html):
    """Save unexpected review HTML so selectors/redirects can be diagnosed."""
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = os.path.join(DEBUG_DIR, f"reviews_{asin}_page_{page_number}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

async def wait_for_review_page(page, asin, page_number):
    """Wait for reviews, or allow the user to manually solve sign-in/CAPTCHA."""
    review_selector = "[data-hook='review'], [data-hook='review-card']"
    deadline = asyncio.get_running_loop().time() + (MANUAL_CHALLENGE_TIMEOUT_MS / 1000)
    challenge_announced = False

    while asyncio.get_running_loop().time() < deadline:
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        state = check_blocking(soup)

        if not state:
            try:
                await page.wait_for_selector(review_selector, timeout=5_000)
                return BeautifulSoup(await page.content(), "html.parser"), None
            except Exception:
                # A valid page can have no reviews, so stop after the normal
                # page timeout instead of waiting the full challenge timeout.
                await page.wait_for_timeout(1_000)
                return BeautifulSoup(await page.content(), "html.parser"), None

        if not challenge_announced:
            print(
                f"  [ACTION REQUIRED] Amazon displayed {state} for {asin}. "
                "Complete it manually in the visible browser; the scraper will resume."
            )
            challenge_announced = True

        await page.wait_for_timeout(2_000)

    html = await page.content()
    path = save_debug_html(asin, page_number, html)
    return BeautifulSoup(html, "html.parser"), f"Challenge not cleared; saved {path}"

async def extract_reviews_for_product(page, asin, product_soup, product_url):
    """Extract embedded reviews, then follow Amazon's own all-reviews link."""
    reviews = parse_reviews_from_soup(product_soup)
    if reviews:
        print(f"  [REVIEWS] Found {len(reviews)} embedded review(s).")

    # Prefer the review URL Amazon rendered for this product. It carries the
    # correct marketplace/ref path and is more reliable than guessing a URL.
    review_link = product_soup.select_one(
        "a[data-hook='see-all-reviews-link-foot'][href*='product-reviews'], "
        "#reviews-medley-footer a[href*='product-reviews']"
    )
    if not review_link:
        review_link = next(
            (
                link
                for link in product_soup.select("a[href*='/product-reviews/']")
                if asin in link.get("href", "")
            ),
            None,
        )
    if review_link and review_link.get("href"):
        next_url = urljoin(product_url, review_link["href"])
    else:
        next_url = (
            f"https://www.amazon.com/product-reviews/{asin}/"
            "ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews"
        )

    seen_review_ids = {r["review_id"] for r in reviews}

    for page_number in range(1, MAX_REVIEW_PAGES + 1):
        print(f"  [REVIEWS] Loading review page {page_number}: {next_url}")
        try:
            navigation_options = {
                "wait_until": "domcontentloaded",
                "timeout": PAGE_TIMEOUT_MS,
            }
            if page_number == 1:
                navigation_options["referer"] = product_url
            response = await page.goto(next_url, **navigation_options)
            await human_scroll(page)
            await random_delay()
            rev_soup, error = await wait_for_review_page(page, asin, page_number)

            if error:
                print(f"  [WARNING] {error}")
                log_attempt(next_url, "BLOCKED", response.status if response else 503)
                break

            page_reviews = parse_reviews_from_soup(rev_soup)
            if not page_reviews:
                html = await page.content()
                debug_path = save_debug_html(asin, page_number, html)
                print(
                    "  [WARNING] The page contained no recognized review cards. "
                    f"Saved the received HTML to {debug_path}."
                )
                log_attempt(next_url, "EMPTY", response.status if response else 200)
                break

            added = 0
            for review in page_reviews:
                if review["review_id"] not in seen_review_ids:
                    reviews.append(review)
                    seen_review_ids.add(review["review_id"])
                    added += 1

            print(f"  [REVIEWS] Added {added} review(s) from page {page_number}.")
            log_attempt(next_url, "SUCCESS", response.status if response else 200)

            next_link = rev_soup.select_one(
                "li.a-last:not(.a-disabled) a[href], "
                "a[data-hook='pagination-next'][href], "
                "a[aria-label='Next page'][href]"
            )
            if not next_link or not next_link.get("href"):
                break
            next_url = urljoin(page.url, next_link["href"])
            await random_delay()
        except Exception as exc:
            html = await page.content()
            debug_path = save_debug_html(asin, page_number, html)
            print(f"  [WARNING] Review page failed: {exc}. Saved {debug_path}")
            log_attempt(next_url, "ERROR", 500)
            break

    return reviews

async def run_pipeline():
    with open(LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "target_url", "status", "response_code"])

    # utf-8-sig adds a BOM so Microsoft Excel reliably recognizes UTF-8.
    with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["asin", "keyword", "product_url", "title", "price", "brand", "description", "image_url", "video_url", "avg_rating", "rating_count", "reviews"])

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US"
        )
        
        # Inject and sanitize cookies
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                cookie_payload = json.load(f)
                cookies = (
                    cookie_payload.get("cookies", [])
                    if isinstance(cookie_payload, dict)
                    else cookie_payload
                )
                
                clean_cookies = []
                for c in cookies:
                    cookie = {
                        "name": str(c["name"]),
                        "value": str(c["value"]),
                        "domain": str(c.get("domain", ".amazon.com")),
                        "path": str(c.get("path", "/"))
                    }
                    if "sameSite" in c and c["sameSite"] in ["Strict", "Lax", "None"]:
                        cookie["sameSite"] = c["sameSite"]
                    if "secure" in c:
                        cookie["secure"] = bool(c["secure"])
                    if "httpOnly" in c:
                        cookie["httpOnly"] = bool(c["httpOnly"])
                    if isinstance(c.get("expires"), (int, float)) and c["expires"] > 0:
                        cookie["expires"] = c["expires"]
                    clean_cookies.append(cookie)
                    
                await context.add_cookies(clean_cookies)
            print("[INFO] Authenticated cookies injected successfully.")
        else:
            print("[WARNING] cookies.json not found. Running in unauthenticated session mode.")

        page = await context.new_page()

        all_discovered_products = []
        for kw in KEYWORDS:
            search_url = f"https://www.amazon.com/s?k={quote_plus(kw)}"
            print(f"[SEARCHING] Keyword: {kw}")
            
            try:
                response = await page.goto(search_url, wait_until="domcontentloaded")
                
                try:
                    await page.wait_for_selector("div[data-asin]", timeout=15000)
                except Exception:
                    print(f"[WARNING] Waiting for elements timed out for keyword: {kw}")

                await human_scroll(page)
                await random_delay()
                
                content = await page.content()
                soup = BeautifulSoup(content, "html.parser")
                
                if check_blocking(soup):
                    log_attempt(search_url, "BLOCKED", response.status if response else 503)
                    print(f"[ALERT] Block/CAPTCHA detected on search page. Solve it in browser window...")
                    await page.wait_for_selector("div[data-asin]", timeout=60000)
                    content = await page.content()

                discovered = parse_search_page(content, kw)
                log_attempt(search_url, "SUCCESS" if discovered else "EMPTY", response.status if response else 200)
                all_discovered_products.extend(discovered)
                
            except Exception as e:
                print(f"[ERROR] Failed search page {kw}: {e}")
                log_attempt(search_url, "BLOCKED", 500)

        print(f"\n[FOUND] Total products discovered: {len(all_discovered_products)}\n")

        for item in all_discovered_products:
            url = item["product_url"]
            asin = item["asin"]
            print(f"[SCRAPING PRODUCT] ASIN: {asin}")
            
            try:
                response = await page.goto(url, wait_until="domcontentloaded")
                review_section = page.locator("#customerReviews, #reviewsMedley").first
                try:
                    await review_section.scroll_into_view_if_needed(timeout=10_000)
                except Exception:
                    await human_scroll(page)
                await random_delay()
                
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                product_data, status = parse_product_detail_page(html)
                
                if status == "BLOCKED":
                    log_attempt(url, "BLOCKED", response.status if response else 503)
                    await asyncio.sleep(5)
                    html = await page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    product_data, status = parse_product_detail_page(html)

                log_attempt(url, status, response.status if response else 200)

                reviews_list = await extract_reviews_for_product(
                    page, asin, soup, url
                )

                # Save product data and extracted reviews immediately to disk
                if product_data and status != "BLOCKED":
                    with open(OUTPUT_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            asin,
                            item["keyword"],
                            url,
                            product_data["title"],
                            product_data["price"],
                            product_data["brand"],
                            product_data["description"],
                            product_data["image_url"],
                            product_data["video_url"],
                            product_data["avg_rating"],
                            product_data["rating_count"],
                            json.dumps(reviews_list, ensure_ascii=False)
                        ])
            except Exception as e:
                print(f"[ERROR] Failed product {asin}: {e}")
                log_attempt(url, "BLOCKED", 500)

        # Persist session cookies so a manually completed sign-in/CAPTCHA does
        # not need to be repeated on every run.
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(await context.cookies(), f, ensure_ascii=False, indent=2)

        await browser.close()
        print("\n[COMPLETE] Data collection finished! Check 'amazon_products.csv' and 'scraping_log.csv'.")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
