import asyncio
import random
import os
import time
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from python_ghost_cursor.playwright_async import create_cursor
import dotenv
from sqlalchemy import func, and_
from sqlalchemy.orm import aliased
from database import SessionLocal
from models import FBGroup, FBGroupActivity
from datetime import datetime
from accounts import Account

dotenv.load_dotenv()

# Isolate Playwright browsers within the project folder
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.getcwd(), ".playwright-browsers")

TARGET_LIKES = 5
DELAY_BETWEEN_LIKES = 5  # seconds
INTERVAL_HOURS = 4


class Confuser:
    """Utility to add noise and human-like delays to interactions."""
    @staticmethod
    async def random_delay(min_ms=2000, max_ms=5000):
        """Adds a random delay based on ms range. Default 2-5s as per AGENTS.md."""
        delay = random.uniform(min_ms, max_ms) / 1000.0
        await asyncio.sleep(delay)


async def perform_group_likes(account: Account):
    profile_dir = account.resolved_profile_path
    account_id = account.id

    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)

    db = SessionLocal()
    target_url = None
    group_record = None

    try:
        # Select the group least recently liked by this account
        activity = aliased(FBGroupActivity)
        group_record = (
            db.query(FBGroup)
            .outerjoin(activity, and_(activity.group_id == FBGroup.id, activity.account_id == account_id))
            .order_by(activity.last_liked_date.asc().nullslast(), func.random())
            .first()
        )

        if group_record:
            target_url = group_record.facebook
            print(f"[{account_id}] Selected group: {group_record.name or target_url}")
    except Exception as e:
        print(f"[{account_id}] Error fetching from DB: {e}")
    finally:
        db.close()

    if not target_url:
        print(f"[{account_id}] No group URLs found in the database. Please import groups first.")
        return

    print(f"\n--- [{account_id}] Starting run at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    print(f"Target Group: {target_url}")

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

        async def human_click(element):
            try:
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(0.5, 1.5))
                await cursor.click(element)
                return True
            except Exception as e:
                print(f"Ghost-cursor click failed: {e}. Falling back to standard click.")
                try:
                    await element.click()
                    return True
                except:
                    return False

        try:
            print(f"Navigating to group...")
            max_nav_retries = 3
            for attempt in range(max_nav_retries):
                try:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                    try:
                        await page.wait_for_selector('div[role="main"]', timeout=15000)
                    except:
                        pass
                    break
                except Exception as e:
                    error_msg = str(e)
                    print(f"Navigation attempt {attempt+1} failed: {error_msg}")
                    if "Target page, context or browser has been closed" in error_msg:
                        print("Browser closed during navigation. Exiting.")
                        return
                    if attempt == max_nav_retries - 1:
                        print("Could not load page after retries. Exiting.")
                        return
                    await asyncio.sleep(5)

            await asyncio.sleep(8)

            if "login" in page.url or "checkpoint" in page.url:
                print(f"[{account_id}] Action Required: Please handle login or checkpoint.")
                try:
                    while any(x in page.url for x in ["login", "checkpoint", "facebook.com/login"]):
                        await asyncio.sleep(5)
                except Exception as e:
                    if "Target page, context or browser has been closed" in str(e):
                        print("Browser closed during login check. Stopping.")
                        return
                    raise e
                print("Proceeding after login...")
                if target_url not in page.url:
                    await page.goto(target_url, wait_until="domcontentloaded")
                    await asyncio.sleep(5)

            likes_done = 0
            like_selector = 'div[role="article"] div[aria-label="Like"]'

            print(f"Starting to scroll and like {TARGET_LIKES} posts...")

            max_scroll_attempts = 50
            for scroll in range(max_scroll_attempts):
                if likes_done >= TARGET_LIKES:
                    break

                try:
                    await page.wait_for_selector('div[role="main"]', timeout=5000)
                    buttons = await page.query_selector_all(like_selector)

                    if not buttons and scroll > 5:
                        buttons = await page.query_selector_all('div[aria-label="Like"]')
                except Exception as e:
                    error_msg = str(e)
                    if "context was destroyed" in error_msg:
                        print("Execution context destroyed. Retrying in next scroll...")
                        await asyncio.sleep(3)
                        await page.evaluate("window.scrollBy(0, 500)")
                        continue
                    if "Target page, context or browser has been closed" in error_msg:
                        print("Browser closed. Stopping.")
                        break

                    print(f"Error querying buttons: {error_msg}")
                    await asyncio.sleep(2)
                    continue

                for btn in buttons:
                    try:
                        if likes_done >= TARGET_LIKES:
                            break

                        label = await btn.get_attribute("aria-label")
                        if label != "Like":
                            continue

                        if not await btn.is_visible():
                            continue

                        span = await btn.query_selector('span:text-is("Like")')
                        if not span:
                            span = await btn.query_selector('span:has-text("Like")')

                        if not span:
                            continue

                        print(f"[{account_id}] Liking post {likes_done + 1}/{TARGET_LIKES}...")
                        success = await human_click(btn)
                        if success:
                            likes_done += 1
                            print(f"Success! Waiting for human jitter...")
                            await asyncio.sleep(DELAY_BETWEEN_LIKES)
                            await Confuser.random_delay(2000, 5000)
                        else:
                            print("Click reported failure.")

                    except Exception as e:
                        if "context was destroyed" in str(e):
                            print("Execution context destroyed during button check. Breaking button loop.")
                            break
                        print(f"Error processing button: {e}")

                print(f"Scrolling down... (Current likes: {likes_done}/{TARGET_LIKES})")
                await page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(3)

            print(f"[{account_id}] Run complete. Total likes: {likes_done}")

            if likes_done > 0 and group_record:
                db = SessionLocal()
                try:
                    activity_record = db.query(FBGroupActivity).filter(
                        FBGroupActivity.account_id == account_id,
                        FBGroupActivity.group_id == group_record.id
                    ).first()
                    if not activity_record:
                        activity_record = FBGroupActivity(account_id=account_id, group_id=group_record.id)
                        db.add(activity_record)
                    activity_record.last_liked_date = datetime.now()
                    db.commit()
                    print(f"[{account_id}] Updated last_liked_date for group {group_record.name}")
                except Exception as e:
                    print(f"[{account_id}] Error updating DB: {e}")
                finally:
                    db.close()

        except Exception as e:
            print(f"An error occurred during execution: {e}")
        finally:
            await context.close()


async def main_loop(account: Account):
    print(f"FB Liker [{account.id}] started. Will run every {INTERVAL_HOURS} hours.")
    while True:
        try:
            await perform_group_likes(account)
        except Exception as e:
            print(f"Error in main loop: {e}")

        print(f"\nWaiting {INTERVAL_HOURS} hours for next run...")
        await asyncio.sleep(INTERVAL_HOURS * 3600)


if __name__ == "__main__":
    import argparse
    from accounts import get_account, load_accounts

    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--account", type=str, default=None, help="Account ID from accounts.json")
    args = parser.parse_args()

    if args.account:
        account = get_account(args.account)
    else:
        account = load_accounts()[0]

    try:
        if args.once:
            asyncio.run(perform_group_likes(account))
        else:
            asyncio.run(main_loop(account))
    except KeyboardInterrupt:
        print("\nFB Liker stopped.")
