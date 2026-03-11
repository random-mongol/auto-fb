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

# Facebook Page profile URL
FB_PROFILE_URL = "https://www.facebook.com/profile.php?id=61579195435310"
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

async def human_click(page, cursor, selector, timeout=15000):
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

async def switch_profile(page, cursor, target_name):
    """Utility to switch the active Facebook profile to a target name/page."""
    print(f"Attempting to switch profile to '{target_name}'...")
    
    # 1. Click on <svg aria-label="Your profile"> or [aria-label="Your profile"]
    profile_icon_selector = '[aria-label="Your profile"]'
    if not await human_click(page, cursor, profile_icon_selector):
        print("Could not find profile switcher icon. Refreshing and retrying...")
        await page.reload()
        await asyncio.sleep(5)
        if not await human_click(page, cursor, profile_icon_selector):
            print("Failed to click profile icon after retry.")
            return False
    
    await asyncio.sleep(3)
    
    # 2. Then click on <span> with the target text
    target_selector = f'span:has-text("{target_name}")'
    
    if not await human_click(page, cursor, target_selector, timeout=5000):
        print(f"Target '{target_name}' not immediately visible. Checking 'See all profiles'...")
        # Check if "See all profiles" is needed
        if await human_click(page, cursor, 'span:has-text("See all profiles")', timeout=5000):
            await asyncio.sleep(3)
            if not await human_click(page, cursor, target_selector):
                print(f"Still could not find '{target_name}'.")
                return False
        else:
            print(f"Could not click '{target_name}'. You might already be on this profile.")
            # We don't return False here because we might already be on the profile
    
    print(f"Switch to '{target_name}' initiated. Waiting for transition...")
    await asyncio.sleep(12)
    return True

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

        try:
            print("Navigating to Facebook Home...")
            await page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # Handle Login/Checkpoint if needed
            if "login" in page.url or "checkpoint" in page.url:
                print("Action Required: Please handle login or checkpoint in the browser window.")
                while any(x in page.url for x in ["login", "checkpoint", "facebook.com/login"]):
                    await asyncio.sleep(5)
                print("Proceeding after login...")

            # Switch to the page profile
            target_page_name = "huuli.tech - Хуульчийн ухаалаг туслах"
            if not await switch_profile(page, cursor, target_page_name):
                print("Profile switch might have failed. Attempting to proceed anyway.")

            print(f"Navigating to Page Profile: {FB_PROFILE_URL}...")
            await page.goto(FB_PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(8) 

            # Step 1: Click on span with "What's on your mind?"
            # We look for a span that contains the text. FB often localizes, 
            # but the user provided specific English text.
            print("Opening 'What's on your mind?' modal...")
            # Selector for the initial button on the profile page
            post_trigger_selector = 'span:has-text("What\'s on your mind?")'
            if not await human_click(page, cursor, post_trigger_selector):
                # Try fallback for "What's on your mind, [Name]?"
                if not await human_click(page, cursor, 'span:has-text("What\'s on your mind")'):
                    print("Failed to find 'What's on your mind?' span.")
                    return

            await asyncio.sleep(3)
            await Confuser.random_delay()

            # Step 2: Paste URL inside span with "What's on your mind?" text (in the modal)
            print(f"Entering URL: {target_url}")
            # In the modal, there is usually a div with role="textbox" that contains the span.
            # We can click the span or the textbox.
            modal_span_selector = 'div[role="dialog"] span:has-text("What\'s on your mind?")'
            if not await human_click(page, cursor, modal_span_selector, timeout=5000):
                # If the span isn't found in the dialog, try the fallback
                if not await human_click(page, cursor, 'div[role="dialog"] span:has-text("What\'s on your mind")', timeout=5000):
                    # If span is gone (clicked), the focused element might already be the textbox
                    pass
            
            # Type the URL with human jitter
            await page.keyboard.type(target_url, delay=random.randint(40, 120))
            
            print("Waiting for URL preview to generate...")
            await asyncio.sleep(8) # Wait for FB to fetch the link preview
            await Confuser.random_delay()

            # Step 2.5: Click 'Next' if present (Required for Page posting)
            next_btn_selector = 'div[role="dialog"] div[aria-label="Next"]'
            print("Checking for 'Next' button...")
            if await human_click(page, cursor, next_btn_selector, timeout=5000):
                print("'Next' clicked. Waiting for Post button...")
                await asyncio.sleep(3)

            # Step 3: Click on Post button
            print("Clicking 'Post'...")
            # Post button usually has inner span with text "Post"
            # It's inside the dialog. 
            post_btn_selector = 'div[role="dialog"] div[aria-label="Post"]'
            # First try the aria-label which is very stable
            if not await human_click(page, cursor, post_btn_selector, timeout=5000):
                # Fallback to the span text as requested
                if not await human_click(page, cursor, 'div[role="dialog"] span:text-is("Post")', timeout=5000):
                    if not await human_click(page, cursor, 'div[role="dialog"] span:has-text("Post")', timeout=5000):
                        print("Failed to find 'Post' button.")
                        return

            print("Post button clicked. Waiting for confirmation...")
            await asyncio.sleep(20) # Wait for upload
            
            # Success check: If the dialog is gone, we assume it's queued/posted
            posted_successfully = False
            try:
                dialog = await page.query_selector('div[role="dialog"]')
                if not dialog:
                    posted_successfully = True
                    mark_as_posted(target_url)
                    print("Post completed successfully as Page.")
                else:
                    print("Dialog still visible. Attempting to clear it and proceed to engagement...")
                    # Try to hit Escape to close the dialog if it's stuck
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(2)
                    posted_successfully = True # Assume it posted but dialog stayed
                    mark_as_posted(target_url) 
            except:
                posted_successfully = True
                mark_as_posted(target_url)

            if posted_successfully:
                # --- NEW STEP: LIKE AND SHARE AS PERSONAL PROFILE ---
                print("\n--- Phase 2: Engagement as Personal profile ---")
                
                # 1. Switch back to personal profile
                personal_profile_name = "Хуульч Сэцэн"
                if await switch_profile(page, cursor, personal_profile_name):
                    
                    # 2. Navigate back to the Page Profile
                    print(f"Navigating back to {FB_PROFILE_URL} as {personal_profile_name}...")
                    await page.goto(FB_PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(10)
                    await Confuser.random_delay()

                    # 3. Like the first post
                    print("Attempting to Like the first post...")
                    like_selector = 'div[aria-label="Like"]'
                    if await human_click(page, cursor, like_selector):
                        print("Liked successfully.")
                    else:
                        print("Failed to find Like button.")

                    await asyncio.sleep(3)

                    # 4. Share the first post to personal feed
                    print("Attempting to Share the first post...")
                    # Selector provided: <div aria-label="Send this to friends or post it on your profile.">
                    share_btn_selector = 'div[aria-label="Send this to friends or post it on your profile."]'
                    if await human_click(page, cursor, share_btn_selector):
                        await asyncio.sleep(3)
                        
                        print("Selecting 'Share to Feed'...")
                        if await human_click(page, cursor, 'span:has-text("Share to Feed")'):
                            await asyncio.sleep(5)
                            
                            print("Clicking 'Next'...")
                            if await human_click(page, cursor, 'div[aria-label="Next"]'):
                                await asyncio.sleep(5) # Wait for processing
                                
                                print("Clicking 'Share'...")
                                if await human_click(page, cursor, 'div[aria-label="Share"]'):
                                    print("Product shared to personal feed successfully.")
                                else:
                                    print("Failed to find final 'Share' button.")
                            else:
                                print("Failed to find 'Next' button.")
                        else:
                            print("Failed to find 'Share to Feed' option.")
                    else:
                        print("Failed to find Share button.")

                else:
                    print("Failed to switch back to personal profile for engagement.")

        except Exception as e:
            print(f"An error occurred during execution: {e}")
        finally:
            await context.close()

if __name__ == "__main__":
    asyncio.run(post_to_facebook())
