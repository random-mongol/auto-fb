import asyncio
import random
import os
import time
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from python_ghost_cursor.playwright_async import create_cursor
import dotenv
from database import SessionLocal
from models import FBFriend
from datetime import datetime
from accounts import Account

dotenv.load_dotenv()

# Isolate Playwright browsers within the project folder
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.getcwd(), ".playwright-browsers")

FRIENDS_LIST_URL = "https://www.facebook.com/friends/list"
TARGET_MESSAGES_PER_RUN = 3
BASE_DELAY = 5  # seconds

# Mongolian Cyrillic message as requested
MESSAGES = [
    "Сайн байна уу! Найз болсонд баярлалаа. Та https://huuli.tech -ийг туршиж үзсэн үү? Таны хууль зүйн судалгаанд зарцуулах цагийг хэмнэх хиймэл оюун байгаа юм.",
    "Мэнд хүргэе! Найз болсон танд талархлаа. Хэрэв та хууль зүйн судалгаа хийдэг бол https://huuli.tech -ийг ашиглаад цагаа хэмнээрэй. Манай хиймэл оюун танд туслах болно.",
    "Сайн байна уу? Найзаар нэмсэнд баярлалаа. Бид хуульчдад зориулсан https://huuli.tech гэх хиймэл оюунт туслах хөгжүүлсэн юм. Та заавал нэг сонирхоод үзээрэй, цаг их хэмнэнэ шүү."
]


class Confuser:
    @staticmethod
    async def random_delay(min_ms=2000, max_ms=5000):
        delay = random.uniform(min_ms, max_ms) / 1000.0
        await asyncio.sleep(delay)


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
        print(f"Wait/Click failed for '{selector_or_element}': {e}")
    return False


async def gather_friends(page, cursor, account_id: str):
    print(f"[{account_id}] --- Step 1: Gathering Friends from {FRIENDS_LIST_URL} ---")
    await page.goto(FRIENDS_LIST_URL, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(5)

    if "login" in page.url or "checkpoint" in page.url:
        print(f"[{account_id}] Action Required: Please handle login/checkpoint.")
        while any(x in page.url for x in ["login", "checkpoint", "facebook.com/login"]):
            await asyncio.sleep(5)
        if FRIENDS_LIST_URL not in page.url:
            await page.goto(FRIENDS_LIST_URL, wait_until="domcontentloaded")

    new_friends_count = 0
    scanned_urls = set()

    for _ in range(5):
        links = await page.query_selector_all('a[role="link"][href*="facebook.com/"]')
        db = SessionLocal()
        try:
            for link in links:
                href = await link.get_attribute("href")
                if not href or "friends" in href or "profile.php?id=" in href and "&" in href:
                    continue

                if "?" in href:
                    href = href.split("?")[0]

                if href in scanned_urls:
                    continue
                scanned_urls.add(href)

                exists = db.query(FBFriend).filter(
                    FBFriend.account_id == account_id,
                    FBFriend.profile_url == href
                ).first()
                if not exists:
                    name = await link.inner_text()
                    name = name.split('\n')[0] if name else "Unknown"
                    new_friend = FBFriend(account_id=account_id, name=name, profile_url=href)
                    db.add(new_friend)
                    db.commit()
                    new_friends_count += 1
                    print(f"[{account_id}] Saved new friend: {name} ({href})")
        finally:
            db.close()

        await page.evaluate("window.scrollBy(0, 1000)")
        await asyncio.sleep(3)

    print(f"[{account_id}] Gathered {new_friends_count} new friends.")


async def send_messages(page, cursor, account_id: str):
    print(f"[{account_id}] --- Step 2: Sending Messages ---")
    db = SessionLocal()
    try:
        target_friends = (
            db.query(FBFriend)
            .filter(FBFriend.account_id == account_id, FBFriend.last_messaged_at == None)
            .limit(TARGET_MESSAGES_PER_RUN)
            .all()
        )

        if not target_friends:
            print(f"[{account_id}] No unmessaged friends found in DB.")
            return

        for friend in target_friends:
            print(f"[{account_id}] Navigating to {friend.name}'s profile: {friend.profile_url}")
            await page.goto(friend.profile_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            message_btn_selector = 'div[aria-label="Message"] span:text-is("Message")'
            if not await human_click(page, cursor, message_btn_selector, timeout=10000):
                if not await human_click(page, cursor, 'div[aria-label="Message"]', timeout=5000):
                    print(f"[{account_id}] Could not find Message button for {friend.name}. Skipping.")
                    continue

            await asyncio.sleep(4)

            composer_selector = 'div[aria-label="Thread composer"] div[aria-placeholder="Aa"]'
            if await human_click(page, cursor, composer_selector, timeout=10000):
                message = random.choice(MESSAGES)
                print(f"[{account_id}] Typing message to {friend.name}: {message[:50]}...")
                await page.keyboard.type(message, delay=random.randint(50, 150))
                await asyncio.sleep(1)

                send_btn_selector = 'div[aria-label="Press enter to send"]'
                send_btn = await page.query_selector(send_btn_selector)
                if send_btn:
                    await human_click(page, cursor, send_btn)
                else:
                    await page.keyboard.press("Enter")

                print(f"[{account_id}] Message sent to {friend.name}!")

                friend.last_messaged_at = datetime.now()
                db.commit()

                await Confuser.random_delay(5000, 15000)
            else:
                print(f"[{account_id}] Could not find composer for {friend.name}.")

    finally:
        db.close()


async def run_messenger_automation(account: Account):
    profile_dir = account.resolved_profile_path
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            no_viewport=False,
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        cursor = create_cursor(page)

        try:
            await gather_friends(page, cursor, account.id)
            await send_messages(page, cursor, account.id)
        except Exception as e:
            print(f"An error occurred: {e}")
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

    asyncio.run(run_messenger_automation(account))
