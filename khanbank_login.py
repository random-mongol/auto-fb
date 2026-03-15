import asyncio
import os
import random
import hashlib
import json
import requests
import time

import dotenv
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from python_ghost_cursor.playwright_async import create_cursor

dotenv.load_dotenv()

LOGIN_URL = "https://corp.khanbank.com/auth/login"
USERNAME = os.getenv("BANK_USERNAME")
PASSWORD = os.getenv("BANK_PASSWORD")
DISCORD_WEBHOOK_URL = os.getenv("BANK_DISCORD_WEBHOOK", "https://discord.com/api/webhooks/1472529310794514526/12RubpZwpSsC3PRubQxkweOWNUH1cv5a1emez9n-aUVXYwqtUAti8Sl0v9tXaBEMmmA9")
PROFILE_DIR = os.getenv("FB_PROFILE_PATH", os.path.join(os.getcwd(), "fb_profile"))
STATE_FILE = os.path.join(os.getcwd(), ".last_bank_tx.json")

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.getcwd(), ".playwright-browsers")

if not os.path.exists(PROFILE_DIR):
    os.makedirs(PROFILE_DIR)


class Confuser:
    @staticmethod
    async def random_delay(min_ms=600, max_ms=1800):
        await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000.0)


async def human_click(page, cursor, selector, timeout=15000):
    try:
        element = await page.wait_for_selector(selector, state="visible", timeout=timeout)
        await element.scroll_into_view_if_needed()
        await Confuser.random_delay(500, 1200)
        await cursor.click(element)
        return True
    except Exception as exc:
        print(f"Click failed for {selector}: {exc}")
        return False


async def type_like_human(page, text):
    for char in text:
        await page.keyboard.type(char, delay=random.randint(60, 170))
        if random.random() < 0.08:
            await asyncio.sleep(random.uniform(0.1, 0.35))


async def check_and_send_transactions(page):
    print("Checking for new transactions...")
    try:
        # Wait for the recent transactions container
        # Use a shorter timeout here because it might not exist if user navigates away
        try:
            await page.wait_for_selector(".kb-recent-transaction", timeout=10000)
        except:
            return

        # Wait a bit for transactions to load
        await asyncio.sleep(2)

        items = await page.query_selector_all(".kb-recent-transaction .ant-collapse-item")
        if not items:
            return

        parsed_transactions = []
        current_date = ""

        for item in items:
            date_el = await item.query_selector(".kb-transfer-date")
            if date_el:
                current_date = (await date_el.inner_text()).strip()

            time_el = await item.query_selector(".kb-label-date")
            desc_el = await item.query_selector(".kb-description")
            acc_el = await item.query_selector(".kb-related-account")
            amount_el = await item.query_selector(".balance")
            balance_el = await item.query_selector(".kb-text-bal .balance-grey")

            if not time_el or not desc_el or not amount_el:
                continue

            time_text = (await time_el.inner_text()).strip()
            desc_text = (await desc_el.inner_text()).strip()
            acc_text = (await acc_el.inner_text()).strip() if acc_el else "N/A"
            amount_text = (await amount_el.inner_text()).strip()
            balance_text = (await balance_el.inner_text()).strip() if balance_el else "N/A"

            # Create a unique ID for this transaction to avoid duplicates
            raw_id_str = f"{current_date}|{time_text}|{desc_text}|{amount_text}|{balance_text}"
            tx_id = hashlib.md5(raw_id_str.encode()).hexdigest()

            parsed_transactions.append({
                "id": tx_id,
                "date": current_date,
                "time": time_text,
                "description": desc_text,
                "account": acc_text,
                "amount": amount_text,
                "balance": balance_text
            })

        if not parsed_transactions:
            return

        # Load last sent ID
        last_sent_id = None
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                    last_sent_id = state.get("last_sent_id")
            except:
                pass

        # Identify new transactions
        new_txs = []
        for tx in parsed_transactions:
            if tx["id"] == last_sent_id:
                break
            new_txs.append(tx)

        if new_txs:
            print(f"Detected {len(new_txs)} new transactions. Sending to Discord...")
            # Send oldest first
            for tx in reversed(new_txs):
                content = (
                    f"🔔 **Khan Bank: New Transaction**\n"
                    f"📅 **Date:** {tx['date']} {tx['time']}\n"
                    f"💰 **Amount:** `{tx['amount']}`\n"
                    f"📝 **Description:** {tx['description']}\n"
                    f"🏦 **Counterpart:** {tx['account']}\n"
                    f"📈 **Remaining:** {tx['balance']}"
                )
                try:
                    requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
                    print(f"Transaction sent: {tx['amount']} on {tx['date']} {tx['time']}")
                except Exception as e:
                    print(f"Failed to send to Discord: {e}")

            # Save the newest transaction ID
            with open(STATE_FILE, "w") as f:
                json.dump({"last_sent_id": parsed_transactions[0]["id"]}, f)
        else:
            print("No new transactions found.")

    except Exception as e:
        print(f"Error checking transactions: {e}")


async def run_khanbank_login():
    if not USERNAME or not PASSWORD:
        raise RuntimeError("Missing BANK_USERNAME or BANK_PASSWORD in .env")

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
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
            print(f"Navigating to {LOGIN_URL}")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            await Confuser.random_delay(1500, 3000)

            username_selector = '#username'
            password_selector = '#password'
            submit_selector = 'button[type="submit"]'

            if not await human_click(page, cursor, username_selector):
                raise RuntimeError("Could not find username field.")
            
            # Select all and delete (human way) to ensure field is truly empty
            # Using Meta (Command) for Mac as the environment is Mac
            modifier = "Meta"
            await page.keyboard.down(modifier)
            await page.keyboard.press("a")
            await page.keyboard.up(modifier)
            await page.keyboard.press("Backspace")
            await Confuser.random_delay(300, 600)
            
            await type_like_human(page, USERNAME)
            await Confuser.random_delay(700, 1600)

            if not await human_click(page, cursor, password_selector):
                raise RuntimeError("Could not find password field.")
            
            # Select all and delete
            await page.keyboard.down(modifier)
            await page.keyboard.press("a")
            await page.keyboard.up(modifier)
            await page.keyboard.press("Backspace")
            await Confuser.random_delay(300, 600)
            
            await type_like_human(page, PASSWORD)
            await Confuser.random_delay(900, 1800)

            if not await human_click(page, cursor, submit_selector):
                raise RuntimeError("Could not find submit button.")

            print("Login form submitted.")
            
            # Monitoring loop
            print("Starting transaction monitor. Browser will stay open for 15 minutes. Press Ctrl+C to stop.")
            start_time = time.time()
            timeout_seconds = 15 * 60  # 15 minutes
            
            while not page.is_closed():
                await check_and_send_transactions(page)
                
                current_time = time.time()
                if current_time - start_time > timeout_seconds:
                    print(f"Monitoring session completed after {timeout_seconds/60} minutes.")
                    break
                    
                # Check every 2 minutes while page is open
                for _ in range(24):
                    if page.is_closed():
                        break
                    await asyncio.sleep(5)
                    # Instant check for timeout during Sleep
                    if time.time() - start_time > timeout_seconds:
                        print(f"Monitoring session completed after {timeout_seconds/60} minutes.")
                        return # Exit the function to trigger finally block
        except Exception as exc:
            print(f"Khan Bank login automation failed: {exc}")
        finally:
            # Graceful close to avoid "Connection closed while reading from the driver"
            try:
                if context:
                    await context.close()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(run_khanbank_login())
    except KeyboardInterrupt:
        print("\nStopping Khan Bank login automation...")
