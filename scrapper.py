import asyncio
import csv
import json
import random
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Configuration
KEYWORDS = ["wireless mouse", "mechanical keyboard"]  # Replace with assigned keywords
LOG_FILE = "scraping_log.csv"
OUTPUT_FILE = "amazon_products.csv"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def log_attempt(target_url, status, response_code=200):
    """Logs every request attempt to scraping_log.csv"""
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.utcnow().isoformat(), target_url, status, response_code])

async def random_delay(min_sec=2.0, max_sec=7.0):
    """Applies randomized delays to mimic organic human interaction."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)

async def human_scroll(page):
    """Simulates realistic human scrolling behavior on the page."""
    for _ in range(random.randint(2, 4)):
        scroll_amount = random.randint(300, 700)
        await page.mouse.wheel(0, scroll_amount)
        await asyncio.sleep(random.uniform(0.5, 1.5))

def check_blocking(soup):
    """Detects if Amazon served a CAPTCHA or Bot Verification page."""
    title = soup.title.string.lower() if soup.title else ""
    if "captcha" in title or "robot check" in title or soup.find("input", {"id": "captchacharacters"}):
        return True
    return False

def extract_text_multi(soup, selectors):
    """Extracts text by trying multiple CSS selectors as fallbacks."""
    for sel in selectors:
        elem = soup.select_one(sel)
        if elem and elem.get_text(strip=True):
            return elem.get_text(strip=True)
    return "N/A"

def parse_search_page(html, keyword):
    """Extracts unique product links and basic information from page 1 search results using multiple selector fallbacks."""
    soup = BeautifulSoup(html, "html.parser")
    products = []
    
    # Try primary, secondary, and generic selectors for search result containers
    items = soup.select("div[data-component-type='s-search-result']")
    if not items:
        items = soup.select("div.s-result-item[data-asin]")
    if not items:
        items = soup.select("div[data-asin]")

    for item in items:
        asin = item.get("data-asin", "").strip()
        # Ignore empty ASINs or non-product blocks (ASINs are 10 alphanumeric chars)
        if not asin or len(asin) != 10:
            continue
            
        # Try multiple link selectors
        link_elem = (
            item.select_one("h2 a.a-link-normal") or 
            item.select_one("a.a-link-normal.s-no-outline") or 
            item.select_one("a.a-link-normal.s-line-clamp-2") or
            item.select_one("a[href*='/dp/']")
        )
        
        if not link_elem or not link_elem.get("href"):
            continue
            
        href = link_elem["href"]
        # Format direct product URL cleanly
        if "/dp/" in href:
            clean_asin = href.split("/dp/")[1].split("/")[0].split("?")[0]
            product_url = f"https://www.amazon.com/dp/{clean_asin}"
        else:
            product_url = f"https://www.amazon.com{href}" if href.startswith("/") else href
        
        products.append({
            "asin": asin,
            "keyword": keyword,
            "product_url": product_url
        })
        
    return products

def parse_product_detail_page(html):
    """Extracts detailed product specifications and first-page customer reviews."""
    soup = BeautifulSoup(html, "html.parser")
    
    if check_blocking(soup):
        return None, "BLOCKED"

    # 1. Title
    title = extract_text_multi(soup, [
        "#productTitle",
        "#titleSpan",
        "h1.a-size-large",
        "#title"
    ])
    
    # 2. Price
    price = extract_text_multi(soup, [
        ".a-price .a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        ".apexPriceToPay span.a-offscreen",
        "#corePrice_feature_div .a-offscreen"
    ])
    
    # 3. Brand
    brand = extract_text_multi(soup, [
        "#bylineInfo",
        "tr.po-brand td.a-span9 span",
        "#a-page .po-brand .a-span9",
        "a#bylineInfo"
    ])
    
    # 4. Description & Bullet Specs
    description = extract_text_multi(soup, [
        "#feature-bullets ul",
        "#productDescription",
        "#technicalSpecifications_feature_div",
        "#productFactsDesktopExpander"
    ])
    
    # 5. Image URL
    image_url = "N/A"
    img_elem = soup.select_one("#landingImage") or soup.select_one("#imgBlkFront") or soup.select_one("#main-image")
    if img_elem:
        image_url = img_elem.get("data-old-hires") or img_elem.get("src", "N/A")
        
    # 6. Ratings & Review Count
    avg_rating = extract_text_multi(soup, [
        "i.a-icon-star span.a-icon-alt",
        "#acrPopover span.a-size-base",
        "span[data-hook='rating-out-of-text']"
    ])
    
    rating_count = extract_text_multi(soup, [
        "#acrCustomerReviewText",
        "#acrCustomerReviewLink span",
        "#submitContext_glow"
    ])

    # 7. First-Page Reviews Extraction
    reviews_list = []
    review_blocks = soup.select("div[data-hook='review']")
    
    for idx, rev in enumerate(review_blocks):
        rev_id = rev.get("id", f"rev_{idx}")
        author = extract_text_multi(rev, [".a-profile-name"])
        headline = extract_text_multi(rev, ["[data-hook='review-title'] span:not(.a-icon-alt)", "[data-hook='review-title']"])
        body = extract_text_multi(rev, ["[data-hook='review-body'] span", "[data-hook='review-body']"])
        rev_rating = extract_text_multi(rev, ["[data-hook='cmps-review-star-rating'] span", "i[data-hook='review-star-rating'] span"])
        date_str = extract_text_multi(rev, ["[data-hook='review-date']"])
        
        reviews_list.append({
            "review_id": rev_id,
            "reviewer_name": author,
            "headline": headline,
            "review_text": body,
            "rating": rev_rating,
            "review_date": date_str
        })

    product_data = {
        "title": title,
        "price": price,
        "brand": brand,
        "description": description,
        "image_url": image_url,
        "avg_rating": avg_rating,
        "rating_count": rating_count,
        "reviews": json.dumps(reviews_list, ensure_ascii=False)
    }
    
    status = "SUCCESS" if title != "N/A" else "EMPTY"
    return product_data, status

async def run_pipeline():
    with open(LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "target_url", "status", "response_code"])

    with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["asin", "keyword", "product_url", "title", "price", "brand", "description", "image_url", "avg_rating", "rating_count", "reviews"])

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="en-US"
        )
        
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        all_discovered_products = []
        for kw in KEYWORDS:
            search_url = f"https://www.amazon.com/s?k={kw.replace(' ', '+')}"
            print(f"[SEARCHING] Keyword: {kw}")
            
            try:
                response = await page.goto(search_url, wait_until="networkidle")
                
                try:
                    await page.wait_for_selector("div[data-asin]", timeout=10000)
                except Exception:
                    print(f"[WARNING] Waiting for search elements timed out on keyword: {kw}")

                await human_scroll(page)
                await random_delay(2.0, 5.0)
                
                content = await page.content()
                soup = BeautifulSoup(content, "html.parser")
                
                if check_blocking(soup):
                    log_attempt(search_url, "BLOCKED", response.status if response else 503) # cite: 1
                    print(f"[ALERT] CAPTCHA detected on search page for '{kw}'. Solve it in the browser window...")
                    await page.wait_for_selector("div[data-asin]", timeout=60000)
                    content = await page.content()

                discovered = parse_search_page(content, kw)
                log_attempt(search_url, "SUCCESS" if discovered else "EMPTY", response.status if response else 200) # cite: 1
                all_discovered_products.extend(discovered)
                
            except Exception as e:
                print(f"[ERROR] Failed search page {kw}: {e}")
                log_attempt(search_url, "BLOCKED", 500) # cite: 1

        print(f"\n[FOUND] Total products discovered across keywords: {len(all_discovered_products)}\n")

        for item in all_discovered_products:
            url = item["product_url"]
            print(f"[SCRAPING PRODUCT] ASIN: {item['asin']} | {url}")
            
            try:
                response = await page.goto(url, wait_until="domcontentloaded")
                await human_scroll(page)
                await random_delay(3.0, 7.0)
                
                html = await page.content()
                product_data, status = parse_product_detail_page(html)
                
                if status == "BLOCKED":
                    log_attempt(url, "BLOCKED", response.status if response else 503) # cite: 1
                    print(f"[CAPTCHA DETECTED] Pause script to manually solve on: {url}")
                    await asyncio.sleep(15)
                    html = await page.content()
                    product_data, status = parse_product_detail_page(html)

                log_attempt(url, status, response.status if response else 200) # cite: 1

                if product_data and status != "BLOCKED":
                    with open(OUTPUT_FILE, mode="a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            item["asin"],
                            item["keyword"],
                            url,
                            product_data["title"],
                            product_data["price"],
                            product_data["brand"],
                            product_data["description"],
                            product_data["image_url"],
                            product_data["avg_rating"],
                            product_data["rating_count"],
                            product_data["reviews"]
                        ])
            except Exception as e:
                print(f"[ERROR] Failed scraping product {url}: {e}")
                log_attempt(url, "BLOCKED", 500) # cite: 1

        await browser.close()
        print("\n[COMPLETE] Data collection complete! Check 'amazon_products.csv' and 'scraping_log.csv'.")

if __name__ == "__main__":
    asyncio.run(run_pipeline())