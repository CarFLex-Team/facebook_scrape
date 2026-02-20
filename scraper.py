import time
import random
from datetime import datetime
from playwright.sync_api import sync_playwright

MARKETPLACE_URL = "https://www.facebook.com/marketplace/montreal/vehicles/"

STORAGE_STATE_PATH = "fb_state.json"


def human_delay(a=0.5, b=1.2):
    time.sleep(random.uniform(a, b))


def run_scraper():
    print("🚀 Scraper started", datetime.now())

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

        page = context.new_page()
        page.goto(MARKETPLACE_URL, wait_until="domcontentloaded")
        human_delay(2, 3)

        # Simple login check
        body = page.inner_text("body")[:2000].lower()
        if "log in" in body or "sign up" in body:
            print("❌ NOT LOGGED IN")
            browser.close()
            return

        print("✅ Logged in successfully")

        # Scroll once
        page.mouse.wheel(0, 3000)
        human_delay(2, 3)

        # Collect listing links
        links = page.evaluate("""
            () => Array.from(
                document.querySelectorAll("a[href*='/marketplace/item/']")
            ).map(a => "https://www.facebook.com" + a.getAttribute("href").split("?")[0])
        """)

        links = list(dict.fromkeys(links))[:5]

        print(f"🔍 Found {len(links)} listings")

        for link in links:
            try:
                ad = context.new_page()
                ad.goto(link, wait_until="domcontentloaded", timeout=30000)
                human_delay(1, 2)

                title = ad.locator("h1").first.text_content()
                title = title.strip() if title else "N/A"

                print(f"🟢 {title}")

                ad.close()
            except Exception as e:
                print("⚠️ Ad error:", e)

        browser.close()

    print("✅ Scraper finished", datetime.now())
