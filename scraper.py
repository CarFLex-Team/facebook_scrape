import os
import time
import random
import json
import re
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Set, List, Tuple
from playwright.sync_api import sync_playwright

# =====================================================
# CONFIG
# =====================================================

MAX_AGE_MINUTES = 10
MIN_PRICE_RANGE = (1, 50)
SCROLL_PIXELS = 2600
SECURITY_LINK_MAX_HITS = 1
MAX_NO_PROGRESS_ROUNDS = 4

DATA_DIR = os.getenv("DATA_DIR", "/tmp")
os.makedirs(DATA_DIR, exist_ok=True)

JSONL_PATH = os.path.join(DATA_DIR, "cars.jsonl")
SECURITY_SKIP_PATH = os.path.join(DATA_DIR, "security_skip.json")

STORAGE_STATE_PATH = os.getenv("FB_STATE_PATH", "fb_state.json")

marketplace_links = [
    ("montreal", "https://www.facebook.com/marketplace/montreal/vehicles/?sortBy=creation_time_descend&topLevelVehicleType=car_truck&exact=false"),
    ("quebec", "https://www.facebook.com/marketplace/quebec/vehicles/?sortBy=creation_time_descend&topLevelVehicleType=car_truck&exact=false"),
]

SECURITY_PATTERNS = [
    "unusual login",
    "security check",
    "verify your account",
    "checkpoint required",
    "confirm your identity",
]

PRICE_RE = re.compile(
    r"(?:\bCA\$|\bC\$|\bCAD\b|\$)\s*[\d]{1,3}(?:[,\s]\d{3})*(?:\.\d{1,2})?",
    re.IGNORECASE
)

# =====================================================
# UTILS
# =====================================================

def human_delay(a=0.25, b=0.75):
    time.sleep(random.uniform(a, b))


def append_jsonl(path: str, record: dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_seen_links(path: str) -> Set[str]:
    seen = set()
    if not os.path.exists(path):
        return seen
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                if obj.get("Link"):
                    seen.add(obj["Link"])
            except:
                continue
    return seen


def is_checkpoint_text(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in SECURITY_PATTERNS)


def parse_facebook_time(text: str) -> Optional[datetime]:
    now = datetime.now()
    t = (text or "").lower()

    if "just now" in t:
        return now
    if "yesterday" in t:
        return now - timedelta(days=1)

    m = re.search(r"(\d+)\s*(minute|hour|day)", t)
    if m:
        val = int(m.group(1))
        unit = m.group(2)
        if unit == "minute":
            return now - timedelta(minutes=val)
        if unit == "hour":
            return now - timedelta(hours=val)
        if unit == "day":
            return now - timedelta(days=val)
    return None


# =====================================================
# MAIN SCRAPER
# =====================================================

def scrape_city(context, city, url, seen_links):
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded")
    human_delay(1, 2)

    links = page.evaluate("""
        () => Array.from(document.querySelectorAll("a[href*='/marketplace/item/']"))
            .map(a => "https://www.facebook.com" + a.getAttribute("href").split("?")[0])
    """)

    for link in links:
        if link in seen_links:
            continue

        try:
            ad = context.new_page()
            ad.goto(link, wait_until="domcontentloaded")
            human_delay(0.5, 1)

            body = ad.inner_text("body")[:2000]
            if is_checkpoint_text(body):
                ad.close()
                continue

            title = ad.locator("h1").first.text_content() or "N/A"

            price_match = PRICE_RE.search(body)
            price = price_match.group(0) if price_match else "N/A"

            creation_time = None
            spans = ad.query_selector_all("span")
            for sp in spans[:200]:
                txt = sp.inner_text()
                parsed = parse_facebook_time(txt)
                if parsed:
                    creation_time = parsed
                    break

            if not creation_time:
                ad.close()
                continue

            age_min = (datetime.now() - creation_time).total_seconds() / 60
            if age_min > MAX_AGE_MINUTES:
                ad.close()
                continue

            row = {
                "City": city,
                "Title": title.strip(),
                "Price": price,
                "CreationTime": creation_time.strftime("%Y-%m-%d %H:%M"),
                "Link": link,
                "_key": hashlib.md5(link.encode()).hexdigest(),
            }

            append_jsonl(JSONL_PATH, row)
            seen_links.add(link)
            print(f"Saved: {title[:60]}")

            ad.close()

        except Exception as e:
            print("Ad error:", e)
            continue

    page.close()


def run_scraper():
    print("Starting scraper...")

    seen_links = load_seen_links(JSONL_PATH)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            storage_state=STORAGE_STATE_PATH,
            viewport={"width": 1400, "height": 900},
            locale="en-US",
        )

        for city, url in marketplace_links:
            print(f"Scraping {city}")
            scrape_city(context, city, url, seen_links)

        browser.close()

    print("Done.")