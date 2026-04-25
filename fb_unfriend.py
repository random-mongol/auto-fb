"""
fb_unfriend.py

Unfriends existing Facebook friends by harvesting profile URLs from the
friends list page, then visiting each profile and clicking the
"Friends" -> "Unfriend" flow with human-like delays.

Usage:
    ./.venv/bin/python fb_unfriend.py [--account <id>] [--limit <n>] [--all]

    --account  Account ID from accounts.json (defaults to first account)
    --limit    Max friends to unfriend per run (default: 20)
    --all      Ignore the per-run limit and continue until no more friends are found
"""

import asyncio
import os
import random
from urllib.parse import urlparse

import dotenv
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from python_ghost_cursor.playwright_async import create_cursor

from accounts import Account

dotenv.load_dotenv()

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.getcwd(), ".playwright-browsers")

FRIENDS_LIST_URL = "https://www.facebook.com/friends/list"
BASE_DELAY = 5
MAX_GATHER_SCROLLS = 60
MAX_GATHER_IDLE_SCROLLS = 6

INVALID_PROFILE_SEGMENTS = {
    "",
    "ads",
    "business",
    "checkpoint",
    "events",
    "friends",
    "gaming",
    "groups",
    "help",
    "login",
    "marketplace",
    "messages",
    "notifications",
    "pages",
    "permalink.php",
    "photos",
    "photo.php",
    "profile.php",
    "reel",
    "reels",
    "search",
    "settings",
    "share",
    "story.php",
    "stories",
    "watch",
    "watchlive",
}


def normalize_profile_url(href: str | None) -> str | None:
    if not href:
        return None

    parsed = urlparse(href)
    if parsed.netloc and "facebook.com" not in parsed.netloc:
        return None

    path = parsed.path.rstrip("/")
    if not path.startswith("/"):
        return None

    segments = [segment for segment in path.split("/") if segment]
    if len(segments) != 1:
        return None

    first_segment = segments[0].lower()
    if first_segment in INVALID_PROFILE_SEGMENTS:
        return None

    return f"https://www.facebook.com/{segments[0]}"


async def human_click(page, cursor, selector_or_element, timeout=10000):
    try:
        if isinstance(selector_or_element, str):
            element = await page.wait_for_selector(selector_or_element, timeout=timeout)
        else:
            element = selector_or_element

        if element:
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await cursor.click(element)
            return True
    except Exception as e:
        print(f"Click failed for {selector_or_element}: {e}")
    return False


async def ensure_logged_in(page, target_url: str, account_id: str):
    if "login" not in page.url and "checkpoint" not in page.url:
        return

    print(f"[{account_id}] Action Required: Please handle login/checkpoint.")
    while any(x in page.url for x in ["login", "checkpoint", "facebook.com/login"]):
        await asyncio.sleep(5)

    if target_url not in page.url:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)


async def collect_friend_profile_urls(page, account_id: str):
    print(f"[{account_id}] Gathering current friends from {FRIENDS_LIST_URL}")
    await page.goto(FRIENDS_LIST_URL, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(5)
    await ensure_logged_in(page, FRIENDS_LIST_URL, account_id)

    collected_urls = []
    seen_urls = set()
    idle_scrolls = 0

    for scroll_attempt in range(MAX_GATHER_SCROLLS):
        try:
            links = await page.query_selector_all('a[role="link"][href*="facebook.com/"]')
        except Exception as e:
            if "context was destroyed" in str(e):
                await asyncio.sleep(2)
                continue
            raise

        found_this_pass = 0
        for link in links:
            href = await link.get_attribute("href")
            normalized_url = normalize_profile_url(href)
            if not normalized_url or normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            collected_urls.append(normalized_url)
            found_this_pass += 1

        print(
            f"[{account_id}] Gather pass {scroll_attempt + 1}: "
            f"{found_this_pass} new profile(s), {len(collected_urls)} total."
        )

        if found_this_pass == 0:
            idle_scrolls += 1
        else:
            idle_scrolls = 0

        if idle_scrolls >= MAX_GATHER_IDLE_SCROLLS:
            print(f"[{account_id}] Friends list stopped yielding new profiles. Proceeding with {len(collected_urls)} candidate(s).")
            break

        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(random.uniform(2.0, 4.0))

    return collected_urls


async def find_first_visible(page, selectors: list[str], timeout=5000):
    for selector in selectors:
        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            if element and await element.is_visible():
                return element
        except Exception:
            continue
    return None


async def unfriend_profile(page, cursor, profile_url: str, account_id: str):
    await page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(random.uniform(3.5, 6.0))

    friendship_button = await find_first_visible(
        page,
        [
            'div[aria-label="Friends"]',
            'div[role="button"][aria-label="Friends"]',
            'span:text-is("Friends")',
            'span:has-text("Friends")',
        ],
        timeout=8000,
    )
    if not friendship_button:
        print(f"[{account_id}] Could not find Friends button on {profile_url}. Skipping.")
        return False

    if not await human_click(page, cursor, friendship_button, timeout=8000):
        print(f"[{account_id}] Failed to open friendship menu on {profile_url}.")
        return False

    await asyncio.sleep(random.uniform(1.5, 3.0))

    unfriend_button = await find_first_visible(
        page,
        [
            'div[role="menuitem"] span:text-is("Unfriend")',
            'div[role="menuitem"] span:has-text("Unfriend")',
            'span:text-is("Unfriend")',
            'span:has-text("Unfriend")',
        ],
        timeout=5000,
    )
    if not unfriend_button:
        print(f"[{account_id}] Could not find Unfriend option for {profile_url}.")
        return False

    if not await human_click(page, cursor, unfriend_button, timeout=5000):
        print(f"[{account_id}] Failed to click Unfriend for {profile_url}.")
        return False

    await asyncio.sleep(random.uniform(1.5, 3.0))

    confirm_button = await find_first_visible(
        page,
        [
            'div[aria-label="Confirm"]',
            'div[role="button"][aria-label="Confirm"]',
            'span:text-is("Confirm")',
            'span:has-text("Confirm")',
        ],
        timeout=5000,
    )
    if confirm_button:
        if not await human_click(page, cursor, confirm_button, timeout=5000):
            print(f"[{account_id}] Failed to confirm unfriend for {profile_url}.")
            return False
    else:
        print(f"[{account_id}] No confirm dialog appeared for {profile_url}; assuming direct unfriend flow.")

    return True


async def unfriend_friends(account: Account, limit: int | None):
    profile_dir = account.resolved_profile_path
    account_id = account.id

    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)

    requested = "all" if limit is None else str(limit)
    print(f"[{account_id}] Starting unfriend run. Target: {requested}")

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

        try:
            candidate_profiles = await collect_friend_profile_urls(page, account_id)
            if limit is not None:
                candidate_profiles = candidate_profiles[:limit]

            if not candidate_profiles:
                print(f"[{account_id}] No friend profiles found to process.")
                return

            unfriended = 0
            total_targets = len(candidate_profiles)

            for index, profile_url in enumerate(candidate_profiles, start=1):
                print(f"[{account_id}] Processing {index}/{total_targets}: {profile_url}")
                try:
                    success = await unfriend_profile(page, cursor, profile_url, account_id)
                except Exception as e:
                    error_text = str(e)
                    print(f"[{account_id}] Error while unfriending {profile_url}: {error_text}")
                    if "Target page, context or browser has been closed" in error_text or "Browser closed" in error_text:
                        print(f"[{account_id}] Browser was closed during run. Stopping.")
                        break
                    success = False

                if success:
                    unfriended += 1
                    jitter = BASE_DELAY + random.uniform(-1.5, 3.5)
                    print(f"[{account_id}] Unfriended {unfriended}/{total_targets}. Cooling down for {jitter:.2f}s...")
                    await asyncio.sleep(jitter)
                else:
                    await asyncio.sleep(random.uniform(2.0, 4.0))

            print(f"[{account_id}] Finished unfriend run. Successfully unfriended {unfriended} friend(s).")
        finally:
            await context.close()


if __name__ == "__main__":
    import argparse
    from accounts import get_account, load_accounts

    parser = argparse.ArgumentParser(description="Unfriend existing Facebook friends")
    parser.add_argument("--account", type=str, default=None, help="Account ID from accounts.json")
    parser.add_argument("--limit", type=int, default=20, help="Max friends to unfriend (default: 20)")
    parser.add_argument("--all", action="store_true", help="Unfriend all discovered friends")
    args = parser.parse_args()

    if args.account:
        account = get_account(args.account)
    else:
        account = load_accounts()[0]

    run_limit = None if args.all else args.limit
    asyncio.run(unfriend_friends(account, run_limit))
