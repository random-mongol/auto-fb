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
from urllib.parse import urlparse

dotenv.load_dotenv()

# Isolate Playwright browsers within the project folder
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.getcwd(), ".playwright-browsers")

FRIENDS_LIST_URL = "https://www.facebook.com/friends/list"
TARGET_MESSAGES_PER_RUN = 3
BASE_DELAY = 5  # seconds

# Mongolian Cyrillic message as requested
MESSAGES = [
    "Сайн байна уу? Найз болсонд баярлалаа. Зав гарвал https://huuli.tech-ийг сонирхоод үзээрэй. Хууль, эрх зүйн мэдээлэл хайхад цаг хэмнэхэд их хэрэг болдог юм.",
    "Сайн байна уу, найзаа. Холбогдсонд баярлалаа. Би хууль, эрх зүйн судалгааг арай хялбар болгох https://huuli.tech дээр ажиллаж байгаа. Сонирхоод үзээд санал бодлоо хэлбэл их баярлана.",
    "Мэнд байна уу? Найзын хүсэлтийг зөвшөөрсөнд баярлалаа. Бидний хийсэн https://huuli.tech нь хууль зүйн судалгаа, хайлтаа илүү хурдан хийхэд тусалдаг. Туршаад үзвэл сэтгэгдлээ хуваалцаарай."
]

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

CHAT_HISTORY_MARKERS = [
    "huuli.tech",
    "you sent",
    "sent by you",
]

CHAT_SYSTEM_MARKERS = [
    "you're friends on facebook",
]

CHAT_UI_NOISE_CONTAINS = [
    "active now",
    "search in conversation",
    "open sticker picker",
    "open gif picker",
    "open emoji picker",
    "open image editor",
    "choose a file",
    "view profile",
    "privacy and support",
    "customize chat",
    "close chat",
    "press enter to send",
]

CHAT_UI_NOISE_PREFIXES = [
    "write to ",
    "say hi to ",
]


class Confuser:
    @staticmethod
    async def random_delay(min_ms=2000, max_ms=5000):
        delay = random.uniform(min_ms, max_ms) / 1000.0
        await asyncio.sleep(delay)


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


def profile_url_to_thread_url(profile_url: str | None) -> str | None:
    normalized_url = normalize_profile_url(profile_url)
    if not normalized_url:
        return None

    thread_id = normalized_url.rstrip("/").rsplit("/", 1)[-1]
    if not thread_id:
        return None

    return f"https://www.facebook.com/messages/t/{thread_id}"


def looks_like_notification_label(name: str | None) -> bool:
    if not name:
        return True

    lowered = " ".join(name.split()).lower()
    return any(
        token in lowered
        for token in [
            "mark as read",
            "posted in",
            "posted 2 new reels",
            "posted a reel",
            "posted a photo",
            "unread",
        ]
    )


def purge_invalid_friend_rows(db, account_id: str) -> int:
    removed = 0
    invalid_rows = (
        db.query(FBFriend)
        .filter(FBFriend.account_id == account_id, FBFriend.last_messaged_at == None)
        .all()
    )
    for friend in invalid_rows:
        normalized_url = normalize_profile_url(friend.profile_url)
        if not normalized_url or looks_like_notification_label(friend.name):
            db.delete(friend)
            removed += 1
            continue

        if normalized_url != friend.profile_url:
            friend.profile_url = normalized_url

    if removed:
        print(f"[{account_id}] Removed {removed} invalid friend rows from DB before sending.")
    db.commit()
    return removed


async def get_chat_container_text(page):
    composer = await page.query_selector('div[aria-label="Thread composer"] div[aria-placeholder="Aa"]')
    if composer:
        container_handle = await composer.evaluate_handle(
            """node => {
                let current = node;
                while (current) {
                    if (current.getAttribute && current.getAttribute("role") === "dialog") {
                        return current;
                    }
                    if (
                        current.querySelector &&
                        current.querySelector('[aria-placeholder="Aa"]') &&
                        current.querySelector('[aria-label="Thread composer"]')
                    ) {
                        return current;
                    }
                    current = current.parentElement;
                }
                return null;
            }"""
        )
        container = container_handle.as_element() if container_handle else None
        if container:
            try:
                return await container.inner_text()
            except Exception:
                pass

    for selector in ['div[role="dialog"]', 'div[aria-label="Chat"]', 'div[aria-label="Conversation"]']:
        container = await page.query_selector(selector)
        if container:
            try:
                return await container.inner_text()
            except Exception:
                continue

    return None


def normalize_text_lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.splitlines() if " ".join(line.split())]


def meaningful_chat_lines(lines: list[str], friend_name: str | None) -> list[str]:
    ignored_exact = {
        "aa",
        "message",
        "messages",
        "messenger",
        "write a reply...",
        "type a message...",
        "new message",
        "reply",
    }
    if friend_name:
        ignored_exact.add(friend_name.strip().lower())

    filtered = []
    for line in lines:
        lowered = line.lower()
        if lowered in ignored_exact:
            continue
        if any(lowered.startswith(prefix) for prefix in CHAT_UI_NOISE_PREFIXES):
            continue
        if any(marker in lowered for marker in CHAT_UI_NOISE_CONTAINS):
            continue
        filtered.append(line)
    return filtered


async def detect_existing_conversation(page, friend_name: str | None):
    chat_text = await get_chat_container_text(page)
    if not chat_text:
        return "unknown", []

    lines = normalize_text_lines(chat_text)
    filtered_lines = meaningful_chat_lines(lines, friend_name)
    lowered_lines = [line.lower() for line in filtered_lines]

    if any(marker in line for marker in CHAT_HISTORY_MARKERS for line in lowered_lines):
        return "existing", filtered_lines[:5]

    system_only_lines = [
        line for line in lowered_lines
        if any(marker in line for marker in CHAT_SYSTEM_MARKERS)
    ]
    non_system_lines = [
        line for line in lowered_lines
        if not any(marker in line for marker in CHAT_SYSTEM_MARKERS)
    ]

    if non_system_lines:
        return "existing", filtered_lines[:5]

    if system_only_lines:
        return "new", filtered_lines[:5]

    return "unknown", filtered_lines[:5]


async def close_open_chat_windows(page, cursor):
    close_buttons = await page.query_selector_all('[aria-label="Close chat"]')
    for button in close_buttons:
        try:
            if await button.is_visible():
                await human_click(page, cursor, button, timeout=3000)
                await asyncio.sleep(random.uniform(0.5, 1.0))
        except Exception:
            continue


async def find_visible_element(page, selectors: list[str], timeout_ms=10000):
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    return element
            except Exception:
                continue
        await asyncio.sleep(0.5)
    return None


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


async def open_message_composer(page, cursor, friend, account_id: str):
    composer_selectors = [
        'div[aria-label="Thread composer"] div[aria-placeholder="Aa"]',
        'div[aria-label="Thread composer"] [contenteditable="true"]',
        'div[role="textbox"][contenteditable="true"]',
        'div[contenteditable="true"][aria-placeholder="Aa"]',
    ]

    thread_url = profile_url_to_thread_url(friend.profile_url)
    if thread_url:
        print(f"[{account_id}] Opening direct thread for {friend.name}: {thread_url}")
        try:
            await page.goto(thread_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(random.uniform(3.0, 5.0))
            composer = await find_visible_element(page, composer_selectors, timeout_ms=10000)
            if composer:
                return composer
            print(f"[{account_id}] Direct thread did not expose a composer for {friend.name}. Falling back.")
        except Exception as e:
            print(f"[{account_id}] Direct thread navigation failed for {friend.name}: {e}")

    print(f"[{account_id}] Falling back to profile messaging flow for {friend.name}: {friend.profile_url}")
    await page.goto(friend.profile_url, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(5)

    message_btn_selector = 'div[aria-label="Message"] span:text-is("Message")'
    if not await human_click(page, cursor, message_btn_selector, timeout=10000):
        if not await human_click(page, cursor, 'div[aria-label="Message"]', timeout=5000):
            print(f"[{account_id}] Could not find Message button for {friend.name}.")
            return None

    await asyncio.sleep(4)
    return await find_visible_element(page, composer_selectors, timeout_ms=10000)


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
                normalized_href = normalize_profile_url(href)
                if not normalized_href:
                    continue

                if normalized_href in scanned_urls:
                    continue

                name = await link.inner_text()
                name = name.split('\n')[0].strip() if name else "Unknown"
                if looks_like_notification_label(name):
                    continue
                scanned_urls.add(normalized_href)

                exists = db.query(FBFriend).filter(
                    FBFriend.account_id == account_id,
                    FBFriend.profile_url == normalized_href
                ).first()
                if not exists:
                    new_friend = FBFriend(account_id=account_id, name=name, profile_url=normalized_href)
                    db.add(new_friend)
                    db.commit()
                    new_friends_count += 1
                    print(f"[{account_id}] Saved new friend: {name} ({normalized_href})")
        finally:
            db.close()

        await page.evaluate("window.scrollBy(0, 1000)")
        await asyncio.sleep(3)

    print(f"[{account_id}] Gathered {new_friends_count} new friends.")


async def send_messages(page, cursor, account_id: str):
    print(f"[{account_id}] --- Step 2: Sending Messages ---")
    db = SessionLocal()
    try:
        purge_invalid_friend_rows(db, account_id)

        candidate_friends = (
            db.query(FBFriend)
            .filter(FBFriend.account_id == account_id, FBFriend.last_messaged_at == None)
            .order_by(FBFriend.created_at.asc(), FBFriend.id.asc())
            .limit(TARGET_MESSAGES_PER_RUN * 10)
            .all()
        )

        target_friends = []
        for friend in candidate_friends:
            normalized_url = normalize_profile_url(friend.profile_url)
            if not normalized_url:
                continue
            if normalized_url != friend.profile_url:
                friend.profile_url = normalized_url
            target_friends.append(friend)
        db.commit()

        if not target_friends:
            print(f"[{account_id}] No unmessaged friends found in DB.")
            return

        messages_sent = 0
        for friend in target_friends:
            if messages_sent >= TARGET_MESSAGES_PER_RUN:
                break

            await close_open_chat_windows(page, cursor)
            composer = await open_message_composer(page, cursor, friend, account_id)
            if composer:
                conversation_state, evidence = await detect_existing_conversation(page, friend.name)
                if conversation_state == "existing":
                    print(
                        f"[{account_id}] Existing conversation detected for {friend.name}. "
                        f"Skipping. Evidence: {evidence[:3]}"
                    )
                    friend.last_messaged_at = datetime.now()
                    db.commit()
                    await close_open_chat_windows(page, cursor)
                    continue

                if conversation_state == "unknown":
                    # Fallback: scan the full page for any trace of our message URL
                    page_text = await page.evaluate("() => document.body.innerText")
                    if "huuli.tech" in page_text.lower():
                        print(
                            f"[{account_id}] Found huuli.tech in page for {friend.name}. "
                            "Already messaged — skipping."
                        )
                        friend.last_messaged_at = datetime.now()
                        db.commit()
                        await close_open_chat_windows(page, cursor)
                        continue
                    print(
                        f"[{account_id}] Could not verify chat state for {friend.name}, "
                        "but no prior message found — proceeding."
                    )

                if not await human_click(page, cursor, composer, timeout=3000):
                    print(f"[{account_id}] Could not focus composer for {friend.name}.")
                    continue

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
                await close_open_chat_windows(page, cursor)
                messages_sent += 1

                await Confuser.random_delay(5000, 15000)
            else:
                print(f"[{account_id}] Could not find composer for {friend.name}.")

        print(f"[{account_id}] Messenger run completed with {messages_sent} new messages sent.")

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
