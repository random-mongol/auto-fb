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
from accounts import Account

dotenv.load_dotenv()

# Isolate Playwright browsers within the project folder
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.getcwd(), ".playwright-browsers")

SITEMAP_URL = "https://huuli.tech/sitemap.xml"
ARTICLE_PREFIX = "https://huuli.tech/articles"


class Confuser:
    """Utility to add noise and human-like delays to interactions."""
    @staticmethod
    async def random_delay(min_ms=2000, max_ms=5000):
        delay = random.uniform(min_ms, max_ms) / 1000.0
        await asyncio.sleep(delay)


def get_articles_from_sitemap():
    """Fetches and parses the sitemap to find target articles."""
    try:
        print(f"Fetching sitemap: {SITEMAP_URL}")
        response = requests.get(SITEMAP_URL, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)
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


def get_unposted_article(urls, account_id: str):
    """Filters out articles already posted by this account."""
    db = SessionLocal()
    try:
        posted_urls = {
            a.url for a in db.query(PostedArticle).filter(PostedArticle.account_id == account_id).all()
        }
        unposted = [u for u in urls if u not in posted_urls]
        if not unposted:
            return None
        return random.choice(unposted)
    finally:
        db.close()


def mark_as_posted(url, account_id: str):
    """Records the successful post in the database."""
    db = SessionLocal()
    try:
        posted = PostedArticle(account_id=account_id, url=url)
        db.add(posted)
        db.commit()
        print(f"[{account_id}] Successfully recorded in DB: {url}")
    except Exception as e:
        print(f"[{account_id}] Error marking as posted in DB: {e}")
    finally:
        db.close()


async def human_click(page, cursor, selector, timeout=15000):
    """Generic helper for clicking elements with ghost-cursor."""
    try:
        element = await page.wait_for_selector(selector, timeout=timeout)
        if element:
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await cursor.click(element)
            return True
    except Exception as e:
        print(f"Wait/Click failed for '{selector}': {e}")
    return False


async def switch_profile(page, cursor, target_name):
    """Utility to switch the active Facebook profile to a target name/page."""
    print(f"Attempting to switch profile to '{target_name}'...")

    profile_icon_selector = '[aria-label="Your profile"]'
    if not await human_click(page, cursor, profile_icon_selector):
        print("Could not find profile switcher icon. Refreshing and retrying...")
        await page.reload()
        await asyncio.sleep(5)
        if not await human_click(page, cursor, profile_icon_selector):
            print("Failed to click profile icon after retry.")
            return False

    await asyncio.sleep(3)

    target_selector = f'span:has-text("{target_name}")'

    if not await human_click(page, cursor, target_selector, timeout=5000):
        print(f"Target '{target_name}' not immediately visible. Checking 'See all profiles'...")
        if await human_click(page, cursor, 'span:has-text("See all profiles")', timeout=5000):
            await asyncio.sleep(3)
            if not await human_click(page, cursor, target_selector):
                print(f"Still could not find '{target_name}'.")
                return False
        else:
            print(f"Could not click '{target_name}'. You might already be on this profile.")

    print(f"Switch to '{target_name}' initiated. Waiting for transition...")
    await asyncio.sleep(12)
    return True


async def post_to_facebook(account: Account):
    """Main function to perform the Facebook posting."""
    account_id = account.id
    profile_dir = account.resolved_profile_path
    fb_profile_url = account.fb_profile_url or "https://www.facebook.com/profile.php?id=61579195435310"

    urls = get_articles_from_sitemap()
    if not urls:
        print(f"[{account_id}] No articles found in sitemap. Exiting.")
        return

    target_url = get_unposted_article(urls, account_id)
    if not target_url:
        print(f"[{account_id}] No unposted articles found. Everything is already on Facebook!")
        return

    print(f"\n--- [{account_id}] Starting FB Post Run at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    print(f"Selected Article: {target_url}")

    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
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

            if "login" in page.url or "checkpoint" in page.url:
                print(f"[{account_id}] Action Required: Please handle login or checkpoint.")
                while any(x in page.url for x in ["login", "checkpoint", "facebook.com/login"]):
                    await asyncio.sleep(5)
                print("Proceeding after login...")

            target_page_name = "huuli.tech - Хуульчийн ухаалаг туслах"
            if not await switch_profile(page, cursor, target_page_name):
                print(f"[{account_id}] Profile switch might have failed. Attempting to proceed anyway.")

            print(f"[{account_id}] Navigating to Page Profile: {fb_profile_url}...")
            await page.goto(fb_profile_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(8)

            print("Opening 'What's on your mind?' modal...")
            trigger_selectors = [
                'span:has-text("What\'s on your mind?")',
                'span:has-text("What\'s on your mind")',
                'div[role="button"] span:has-text("Write something")',
                'div[aria-label^="What\'s on your mind"]',
                'div[aria-label^="Write something"]'
            ]

            trigger_clicked = False
            for selector in trigger_selectors:
                if await human_click(page, cursor, selector, timeout=5000):
                    trigger_clicked = True
                    break

            if not trigger_clicked:
                print(f"[{account_id}] Failed to find 'What's on your mind?' trigger.")

            await asyncio.sleep(3)
            await Confuser.random_delay()

            print(f"[{account_id}] Entering URL: {target_url}")
            modal_selectors = [
                'div[role="dialog"] div[role="textbox"]',
                'div[role="dialog"] span:has-text("What\'s on your mind?")',
                'div[role="dialog"] span:has-text("What\'s on your mind")',
                'div[role="textbox"][aria-label^="What\'s on your mind"]',
                'div[role="textbox"][aria-label^="Write something"]'
            ]

            for selector in modal_selectors:
                if await human_click(page, cursor, selector, timeout=3000):
                    break

            await page.keyboard.type(target_url, delay=random.randint(40, 120))

            print("Waiting for URL preview to generate...")
            await asyncio.sleep(8)
            await Confuser.random_delay()

            next_btn_selector = 'div[aria-label="Next"]'
            print("Checking for 'Next' button...")
            if await human_click(page, cursor, next_btn_selector, timeout=5000):
                print("'Next' clicked. Waiting for Post button...")
                await asyncio.sleep(3)
            elif await human_click(page, cursor, 'div[role="dialog"] div[aria-label="Next"]', timeout=3000):
                print("'Next' (fallback) clicked. Waiting for Post button...")
                await asyncio.sleep(3)

            print("Clicking 'Post'...")
            post_selectors = [
                'div[role="dialog"] div[aria-label="Post"]',
                'div[role="dialog"] div[role="button"] span:text-is("Post")',
                'div[role="dialog"] div[role="button"] span:has-text("Post")',
                'div[role="dialog"] span:text-is("Post")',
                'div[aria-label="Post"]',
                'span:text-is("Post")'
            ]

            post_clicked = False
            for selector in post_selectors:
                if await human_click(page, cursor, selector, timeout=5000):
                    post_clicked = True
                    break

            if not post_clicked:
                print(f"[{account_id}] Failed to find 'Post' button.")
                return

            print("Post button clicked. Waiting for confirmation...")
            await asyncio.sleep(20)

            posted_successfully = False
            try:
                dialog = await page.query_selector('div[role="dialog"]')
                if not dialog:
                    posted_successfully = True
                    mark_as_posted(target_url, account_id)
                    print(f"[{account_id}] Post completed successfully.")
                else:
                    print("Dialog still visible. Assuming post queued...")
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(2)
                    posted_successfully = True
                    mark_as_posted(target_url, account_id)
            except:
                posted_successfully = True
                mark_as_posted(target_url, account_id)

            if posted_successfully:
                print(f"\n[{account_id}] --- Phase 2: Engagement as Personal profile ---")

                personal_profile_name = account.personal_profile_name or "Хуульч Сэцэн"
                if await switch_profile(page, cursor, personal_profile_name):
                    print(f"[{account_id}] Navigating back to {fb_profile_url}...")
                    await page.goto(fb_profile_url, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(10)
                    await Confuser.random_delay()

                    print("Attempting to Like the FIRST POST...")
                    like_selector = 'div[role="main"] div[role="article"] div[aria-label="Like"]'
                    if await human_click(page, cursor, like_selector):
                        print("Liked successfully.")
                    else:
                        if await human_click(page, cursor, 'div[aria-label="Like"]', timeout=5000):
                            print("Liked generic element.")
                        else:
                            print("Failed to find any Like button.")

                    await asyncio.sleep(3)

                    print("Attempting to Share the first post...")
                    share_btn_selector = 'div[aria-label="Send this to friends or post it on your profile."]'
                    if await human_click(page, cursor, share_btn_selector):
                        await asyncio.sleep(3)

                        print("Selecting 'Share to Feed'...")
                        if await human_click(page, cursor, 'span:has-text("Share to Feed")'):
                            await asyncio.sleep(5)

                            print("Clicking 'Next'...")
                            if await human_click(page, cursor, 'div[aria-label="Next"]'):
                                await asyncio.sleep(5)

                                print("Clicking 'Share'...")
                                if await human_click(page, cursor, 'div[aria-label="Share"]'):
                                    print(f"[{account_id}] Product shared to personal feed successfully.")
                                else:
                                    print("Failed to find final 'Share' button.")
                            else:
                                print("Failed to find 'Next' button.")
                        else:
                            print("Failed to find 'Share to Feed' option.")
                    else:
                        print("Failed to find Share button.")
                else:
                    print(f"[{account_id}] Failed to switch back to personal profile for engagement.")

        except Exception as e:
            print(f"An error occurred during execution: {e}")
        finally:
            await context.close()


if __name__ == "__main__":
    import argparse
    from accounts import get_account, load_accounts

    parser = argparse.ArgumentParser()
    parser.add_argument("--account", type=str, default=None, help="Account ID from accounts.json")
    args = parser.parse_args()

    if args.account:
        account = get_account(args.account)
    else:
        account = load_accounts()[0]

    asyncio.run(post_to_facebook(account))
