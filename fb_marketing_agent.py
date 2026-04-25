import asyncio
import random
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from python_ghost_cursor.playwright_async import create_cursor
import dotenv
from accounts import Account

dotenv.load_dotenv()

# Isolate Playwright browsers within the project folder
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.getcwd(), ".playwright-browsers")

FRIEND_LIMIT_DAILY = 5
BASE_DELAY = 5  # seconds
FRIENDS_PAGE_URL = "https://www.facebook.com/friends"
MAX_EMPTY_SCROLLS = 5


class Confuser:
    """Utility to add noise to interactions."""

    @staticmethod
    async def random_delay(min_ms=500, max_ms=2000):
        delay = random.uniform(min_ms, max_ms) / 1000.0
        await asyncio.sleep(delay)

    @staticmethod
    async def type_with_noise(page, selector, text):
        """Types text with randomized speed and occasional mistakes/corrections."""
        await page.focus(selector)
        for char in text:
            await page.type(selector, char, delay=random.randint(50, 250))
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.1, 0.5))


async def run_fb_automation(account: Account):
    profile_dir = account.resolved_profile_path
    account_id = account.id

    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
    target_url = FRIENDS_PAGE_URL
    print(f"[{account_id}] Targeting friend suggestions from: {target_url}")

    async with async_playwright() as p:
        print(f"[{account_id}] Launching browser with profile: {profile_dir}")

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

        async def human_click(selector_or_element):
            if isinstance(selector_or_element, str):
                try:
                    element = await page.wait_for_selector(selector_or_element, timeout=5000)
                except:
                    return False
            else:
                element = selector_or_element

            if element:
                try:
                    await element.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    await cursor.click(element)
                    return True
                except Exception as e:
                    print(f"Ghost-cursor click failed: {e}")
                    try:
                        await element.click()
                        return True
                    except:
                        return False
            return False

        print(f"Navigating to: {target_url}")

        max_nav_retries = 3
        for attempt in range(max_nav_retries):
            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                try:
                    await page.wait_for_selector('div[role="main"]', timeout=10000)
                except:
                    await asyncio.sleep(5)
                break
            except Exception as e:
                error_msg = str(e)
                print(f"Navigation attempt {attempt+1} failed: {error_msg}")
                if "Target page, context or browser has been closed" in error_msg or "Browser closed" in error_msg:
                    print("Browser closed during navigation. Exiting.")
                    return
                if attempt == max_nav_retries - 1:
                    print("Could not load page. Exiting.")
                    await context.close()
                    return
                await asyncio.sleep(5)

        if "login" in page.url or "checkpoint" in page.url:
            print(f"[{account_id}] Action Required: Please handle login or checkpoint.")
            print("The agent will proceed automatically once it detects you are on the target page.")
            try:
                while any(x in page.url for x in ["login", "checkpoint", "facebook.com/login"]):
                    await asyncio.sleep(5)
            except Exception as e:
                if "Target page, context or browser has been closed" in str(e) or "Browser closed" in str(e):
                    print("Browser or page closed during login check. Stopping.")
                    await context.close()
                    return
                raise e
            print("Detected target page or bypass. Proceeding...")
            if target_url not in page.url:
                await page.goto(target_url, wait_until="domcontentloaded")
                await page.wait_for_selector('div[role="main"]', timeout=10000)

        friends_added_today = 0
        empty_scrolls = 0
        print(f"[{account_id}] Starting to add friends (Target: {FRIEND_LIMIT_DAILY})")

        while friends_added_today < FRIEND_LIMIT_DAILY:
            try:
                await page.wait_for_selector('div[role="main"]', timeout=30000)
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.5)")
                await Confuser.random_delay(2000, 4000)
                sent_request_this_pass = False

                try:
                    potential_buttons = await page.query_selector_all('div[role="button"] span:text-is("Add friend")')
                    if not potential_buttons:
                        potential_buttons = await page.query_selector_all('div[role="button"] span:text("Add friend")')
                    if not potential_buttons:
                        potential_buttons = await page.query_selector_all('span:text-is("Add Friend")')
                    if not potential_buttons:
                        potential_buttons = await page.query_selector_all('span:text("Add Friend")')
                except Exception as e:
                    if "context was destroyed" in str(e):
                        print("Execution context destroyed. Retrying in next loop...")
                        await asyncio.sleep(2)
                        continue
                    raise e

                print(f"Visible 'Add friend' buttons found: {len(potential_buttons)}")

                for btn in potential_buttons:
                    if friends_added_today >= FRIEND_LIMIT_DAILY:
                        break

                    if not await btn.is_visible():
                        continue

                    try:
                        success = await human_click(btn)
                        if success:
                            friends_added_today += 1
                            sent_request_this_pass = True
                            empty_scrolls = 0
                            jittered_delay = BASE_DELAY + random.uniform(-1.5, 3.5)
                            print(f"[{account_id}] [{friends_added_today}/{FRIEND_LIMIT_DAILY}] Friend request sent!")
                            print(f"Cooling down for {jittered_delay:.2f}s...")
                            await asyncio.sleep(jittered_delay)
                    except Exception as e:
                        print(f"Error clicking button: {e}")

                if friends_added_today >= FRIEND_LIMIT_DAILY:
                    break

                if not potential_buttons:
                    empty_scrolls += 1
                    print(f"[{account_id}] No add-friend buttons found on this pass ({empty_scrolls}/{MAX_EMPTY_SCROLLS}).")
                elif not sent_request_this_pass:
                    empty_scrolls += 1
                    print(f"[{account_id}] Add-friend buttons were visible, but no request was sent on this pass ({empty_scrolls}/{MAX_EMPTY_SCROLLS}).")

                if empty_scrolls >= MAX_EMPTY_SCROLLS:
                    print(f"[{account_id}] No new friend-request targets after repeated scrolling. Stopping safely.")
                    break

                print("Scrolling for more friend suggestions...")
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await Confuser.random_delay(3000, 5000)

            except Exception as e:
                error_msg = str(e)
                print(f"Error in main loop: {error_msg}")
                if "Target page, context or browser has been closed" in error_msg or "Browser closed" in error_msg:
                    print("Browser or page closed. Stopping agent.")
                    break
                await asyncio.sleep(5)

        print(f"[{account_id}] Successfully sent {friends_added_today} friend requests.")
        await asyncio.sleep(5)
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

    try:
        asyncio.run(run_fb_automation(account))
    except KeyboardInterrupt:
        print("\nStopping agent...")
