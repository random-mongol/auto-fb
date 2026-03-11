import asyncio
import random
import os
import time
import requests
from xml.etree import ElementTree as ET
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from python_ghost_cursor.playwright_async import create_cursor
import dotenv
from database import SessionLocal
from models import PostedArticle
from datetime import datetime

dotenv.load_dotenv()

# --- CONFIGURATION ---
# Browser profile path configuration
# Use the same profile as the friend request sender, sourced from .env
PROFILE_DIR = os.getenv("FB_PROFILE_PATH", os.path.join(os.getcwd(), "fb_profile"))

# Facebook profile URL from user request
FB_PROFILE_URL = "https://www.facebook.com/profile.php?id=61585540187688"
SITEMAP_URL = "https://huuli.tech/sitemap.xml"
ARTICLE_PREFIX = "https://huuli.tech/articles"

class Confuser:
    """Utility to add noise and human-like delays to interactions."""
    @staticmethod
    async def random_delay(min_ms=2000, max_ms=5000):
        """Adds a random delay based on ms range. Default 2-5s as per AGENTS.md."""
        delay = random.uniform(min_ms, max_ms) / 1000.0
        await asyncio.sleep(delay)

def get_articles_from_sitemap():
    """Fetches and parses the sitemap to find target articles."""
    try:
        print(f"Fetching sitemap: {SITEMAP_URL}")
        response = requests.get(SITEMAP_URL, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        # Sitemaps use namespaces
        ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = []
        for url in root.findall('ns:url/ns:loc', ns):
            loc = url.text
            if loc and loc.startswith(ARTICLE_PREFIX):
                urls.append(loc)
        print(f"Found {len(urls)} articles in sitemap.")
        return urls
    except Exception as e:
        print(f"Error fetching sitemap: {e}")
        return []

def get_unposted_article(urls):
    """Filters out already posted articles and selects one to post."""
    db = SessionLocal()
    try:
        # Get all posted URLs
        posted_urls = {a.url for a in db.query(PostedArticle).all()}
        unposted = [u for u in urls if u not in posted_urls]
        if not unposted:
            return None
        # Pick the most recent one (if they are ordered in sitemap) or just random
        # Random choice as requested ("any article")
        return random.choice(unposted)
    finally:
        db.close()

def mark_as_posted(url):
    """Records the successful post in the database."""
    db = SessionLocal()
    try:
        posted = PostedArticle(url=url)
        db.add(posted)
        db.commit()
        print(f"Successfully recorded in DB: {url}")
    except Exception as e:
        print(f"Error marking as posted in DB: {e}")
    finally:
        db.close()

async def post_to_facebook():
    """Main function to perform the Facebook posting."""
    urls = get_articles_from_sitemap()
    if not urls:
        print("No articles found in sitemap. Exiting.")
        return

    target_url = get_unposted_article(urls)
    if not target_url:
        print("No unposted articles found. Everything is already on Facebook!")
        return

    print(f"\n--- Starting FB Post Run at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    print(f"Selected Article: {target_url}")

    async with async_playwright() as p:
        # Ensure profile directory exists
        if not os.path.exists(PROFILE_DIR):
            os.makedirs(PROFILE_DIR)

        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ],
            no_viewport=False,
        )

        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        cursor = create_cursor(page)

        async def human_click(selector, timeout=15000):
            """Generic helper for clicking elements with ghost-cursor."""
            try:
                element = await page.wait_for_selector(selector, timeout=timeout)
                if element:
                    # Scroll into view if needed
                    await element.scroll_into_view_if_needed()
                    await asyncio.sleep(1)
                    await cursor.click(element)
                    return True
            except Exception as e:
                print(f"Wait/Click failed for '{selector}': {e}")
            return False

        try:
            print(f"Navigating to {FB_PROFILE_URL}...")
            await page.goto(FB_PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(8) # Allow items to settle

            # Handle Login/Checkpoint if needed
            if "login" in page.url or "checkpoint" in page.url:
                print("Action Required: Please handle login or checkpoint in the browser window.")
                while any(x in page.url for x in ["login", "checkpoint", "facebook.com/login"]):
                    await asyncio.sleep(5)
                # After login, return to profile
                print("Proceeding after login...")
                await page.goto(FB_PROFILE_URL, wait_until="domcontentloaded")
                await asyncio.sleep(8)

            # Step 1: Click on span with "What's on your mind?"
            # We look for a span that contains the text. FB often localizes, 
            # but the user provided specific English text.
            print("Opening 'What's on your mind?' modal...")
            # Selector for the initial button on the profile page
            post_trigger_selector = 'span:has-text("What\'s on your mind?")'
            if not await human_click(post_trigger_selector):
                # Try fallback for "What's on your mind, [Name]?"
                if not await human_click('span:has-text("What\'s on your mind")'):
                    print("Failed to find 'What's on your mind?' span.")
                    return

            await asyncio.sleep(3)
            await Confuser.random_delay()

            # Step 2: Paste URL inside span with "What's on your mind?" text (in the modal)
            print(f"Entering URL: {target_url}")
            # In the modal, there is usually a div with role="textbox" that contains the span.
            # We can click the span or the textbox.
            modal_span_selector = 'div[role="dialog"] span:has-text("What\'s on your mind?")'
            if not await human_click(modal_span_selector, timeout=5000):
                # If the span isn't found in the dialog, try the fallback
                if not await human_click('div[role="dialog"] span:has-text("What\'s on your mind")', timeout=5000):
                    # If span is gone (clicked), the focused element might already be the textbox
                    pass
            
            # Type the URL with human jitter
            await page.keyboard.type(target_url, delay=random.randint(40, 120))
            
            print("Waiting for URL preview to generate...")
            await asyncio.sleep(8) # Wait for FB to fetch the link preview
            await Confuser.random_delay()

            # Step 3: Click on span with text Post in it
            print("Clicking 'Post'...")
            # Post button usually has inner span with text "Post"
            # It's inside the dialog. 
            post_btn_selector = 'div[role="dialog"] div[aria-label="Post"]'
            # First try the aria-label which is very stable
            if not await human_click(post_btn_selector, timeout=5000):
                # Fallback to the span text as requested
                if not await human_click('div[role="dialog"] span:text-is("Post")', timeout=5000):
                    if not await human_click('div[role="dialog"] span:has-text("Post")', timeout=5000):
                        print("Failed to find 'Post' button.")
                        return

            print("Post button clicked. Waiting for confirmation...")
            await asyncio.sleep(10) # Wait for upload
            
            # Success check: If the dialog is gone, we assume it's posted
            try:
                dialog = await page.query_selector('div[role="dialog"]')
                if dialog:
                    print("Dialog still visible. Post might have failed or is taking long.")
                    # Optionally wait more or take a screenshot
                else:
                    mark_as_posted(target_url)
                    print("Run complete. Post confirmed.")
            except:
                # If query fails, it probably means the page changed or dialog is gone
                mark_as_posted(target_url)
                print("Run complete.")

        except Exception as e:
            print(f"An error occurred during execution: {e}")
        finally:
            await context.close()

if __name__ == "__main__":
    asyncio.run(post_to_facebook())
