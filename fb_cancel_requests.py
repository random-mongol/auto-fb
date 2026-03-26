"""
fb_cancel_requests.py

Cancels pending outgoing (sent) Facebook friend requests.
Navigates to the Sent Requests page, finds "Cancel request" buttons,
and clicks them with human-like delays.

Usage:
    uv run python fb_cancel_requests.py [--account <id>] [--limit <n>]

    --account  Account ID from accounts.json (defaults to first account)
    --limit    Max requests to cancel per run (default: 20)
"""

import asyncio
import random
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from python_ghost_cursor.playwright_async import create_cursor
import dotenv
from accounts import Account

dotenv.load_dotenv()

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.getcwd(), ".playwright-browsers")

SENT_REQUESTS_URL = "https://www.facebook.com/friends/requests/?sent"
BASE_DELAY = 4  # seconds between cancellations


async def cancel_friend_requests(account: Account, limit: int = 20):
    profile_dir = account.resolved_profile_path
    account_id = account.id

    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)

    print(f"[{account_id}] Starting cancel-requests run. Limit: {limit}")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            no_viewport=False,
        )

        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        cursor = create_cursor(page)

        async def human_click(element_or_selector, timeout=10000):
            try:
                if isinstance(element_or_selector, str):
                    el = await page.wait_for_selector(element_or_selector, timeout=timeout)
                else:
                    el = element_or_selector
                if el:
                    await el.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.4, 1.2))
                    await cursor.click(el)
                    return True
            except Exception as e:
                print(f"Click failed: {e}")
            return False

        try:
            print(f"[{account_id}] Navigating to sent requests page...")
            await page.goto(SENT_REQUESTS_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            # Handle login/checkpoint
            if "login" in page.url or "checkpoint" in page.url:
                print(f"[{account_id}] Action Required: Please handle login/checkpoint.")
                while any(x in page.url for x in ["login", "checkpoint", "facebook.com/login"]):
                    await asyncio.sleep(5)
                await page.goto(SENT_REQUESTS_URL, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(5)

            # Click "View sent requests" to reveal the sent requests list
            print(f"[{account_id}] Looking for 'View sent requests' button...")
            view_sent = await page.query_selector('span:text-is("View sent requests")')
            if not view_sent:
                view_sent = await page.query_selector('span:has-text("View sent requests")')
            if view_sent:
                await human_click(view_sent)
                print(f"[{account_id}] Clicked 'View sent requests'. Waiting for list to load...")
                await asyncio.sleep(4)
            else:
                print(f"[{account_id}] 'View sent requests' button not found — proceeding anyway.")

            cancelled = 0
            max_scrolls = 60

            for scroll_attempt in range(max_scrolls):
                if cancelled >= limit:
                    break

                # Look for "Cancel request" buttons — FB uses aria-label or span text
                cancel_buttons = []
                try:
                    # Primary selector: div with aria-label="Cancel request"
                    cancel_buttons = await page.query_selector_all('div[aria-label="Cancel request"]')

                    # Fallback: span containing the text
                    if not cancel_buttons:
                        cancel_buttons = await page.query_selector_all('span:text-is("Cancel request")')

                    # Second fallback
                    if not cancel_buttons:
                        cancel_buttons = await page.query_selector_all('span:has-text("Cancel request")')
                except Exception as e:
                    if "context was destroyed" in str(e):
                        await asyncio.sleep(2)
                        continue
                    print(f"Error querying buttons: {e}")
                    await asyncio.sleep(2)
                    continue

                if not cancel_buttons:
                    print(f"[{account_id}] No 'Cancel request' buttons found on this scroll. Scrolling more...")
                    await page.evaluate("window.scrollBy(0, 800)")
                    await asyncio.sleep(3)
                    continue

                print(f"[{account_id}] Found {len(cancel_buttons)} cancel button(s).")

                for btn in cancel_buttons:
                    if cancelled >= limit:
                        break

                    try:
                        if not await btn.is_visible():
                            continue

                        success = await human_click(btn)
                        if success:
                            cancelled += 1
                            print(f"[{account_id}] Cancelled request {cancelled}/{limit}")

                            # After clicking "Cancel request", FB may show a confirmation dialog
                            # Look for a "Confirm" button and click it
                            try:
                                confirm_btn = await page.wait_for_selector(
                                    'div[aria-label="Confirm"] , span:text-is("Confirm")',
                                    timeout=3000
                                )
                                if confirm_btn:
                                    await asyncio.sleep(random.uniform(0.5, 1.0))
                                    await human_click(confirm_btn)
                                    print(f"[{account_id}] Confirmed cancellation.")
                            except:
                                pass  # No confirmation dialog needed

                            jitter = BASE_DELAY + random.uniform(-1.0, 2.0)
                            print(f"Cooling down {jitter:.1f}s...")
                            await asyncio.sleep(jitter)

                    except Exception as e:
                        if "context was destroyed" in str(e):
                            break
                        print(f"Error cancelling request: {e}")

                # Scroll down to load more sent requests
                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(3)

            print(f"[{account_id}] Done. Cancelled {cancelled} friend request(s).")

        except Exception as e:
            print(f"[{account_id}] Error: {e}")
        finally:
            await context.close()


if __name__ == "__main__":
    import argparse
    from accounts import get_account, load_accounts

    parser = argparse.ArgumentParser(description="Cancel pending Facebook friend requests")
    parser.add_argument("--account", type=str, default=None, help="Account ID from accounts.json")
    parser.add_argument("--limit", type=int, default=20, help="Max requests to cancel (default: 20)")
    args = parser.parse_args()

    if args.account:
        account = get_account(args.account)
    else:
        account = load_accounts()[0]

    asyncio.run(cancel_friend_requests(account, limit=args.limit))
