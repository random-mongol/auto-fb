import asyncio
import random
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from python_ghost_cursor.playwright_async import create_cursor
import dotenv
from sqlalchemy import func
from database import SessionLocal
from models import FBGroup
from datetime import datetime

dotenv.load_dotenv()

# Configuration from environment
PROFILE_DIR = os.getenv("FB_PROFILE_PATH", os.path.join(os.getcwd(), "fb_profile"))
FRIEND_LIMIT_DAILY = 5
BASE_DELAY = 5  # seconds

# Removed hardcoded GROUP_URLS as per AGENTS.md rules. URLs are fetched from the database.

# TARGET_URL logic moved into run_fb_automation

# Isolate Playwright browsers within the project folder
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.getcwd(), ".playwright-browsers")

# Create profile dir if it doesn't exist
if not os.path.exists(PROFILE_DIR):
    os.makedirs(PROFILE_DIR)

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

async def run_fb_automation():
    # Fetch target from database
    db_session = SessionLocal()
    target_url = None
    group_record = None
    
    try:
        # Pick least recently marketed group
        group_record = db_session.query(FBGroup).order_by(FBGroup.last_marketed_date.asc().nullsfirst(), func.random()).first()
        if group_record:
            target_url = group_record.facebook
    except Exception as e:
        print(f"Error fetching from DB: {e}")
    finally:
        db_session.close()

    if not target_url:
        print("No group URLs found in the database. Please import groups first.")
        return
    
    # Ensure it goes to the contributors page
    if not target_url.endswith('/'):
        target_url += '/'
    
    if "members/contributors" not in target_url:
        target_url += "members/contributors"

    print(f"Targeting: {target_url}")

    async with async_playwright() as p:
        print(f"Launching browser with profile: {PROFILE_DIR}")
        
        # Launch persistent context
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            # Removed proxy as requested
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ],
            no_viewport=False,
        )

        page = await context.new_page()
        # Fix: correctly apply stealth using the Stealth class
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
                    # Use ghost-cursor's click which handles movement and clicking
                    await cursor.click(element)
                    return True
                except Exception as e:
                    print(f"Ghost-cursor click failed: {e}")
                    # Fallback to standard click if ghost-cursor fails
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
                # Use domcontentloaded for FB because it never stops making network requests
                await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                # Wait for the page to actually show the contributors section
                try:
                    await page.wait_for_selector('text="Group contributors"', timeout=10000)
                except:
                    # If text not found, check if we at least have the main area
                    await page.wait_for_selector('div[role="main"]', timeout=5000)
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

        # Check for login
        if "login" in page.url or "checkpoint" in page.url:
            print("Action Required: Please handle login or checkpoint in the browser window.")
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
                try:
                    await page.wait_for_selector('text="Group contributors"', timeout=10000)
                except:
                    pass

        friends_added_today = 0
        print(f"Starting to add friends (Target: {FRIEND_LIMIT_DAILY})")
        
        while friends_added_today < FRIEND_LIMIT_DAILY:
            try:
                await page.wait_for_selector('div[role="main"]', timeout=30000)
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.5)")
                await Confuser.random_delay(2000, 4000)
                
                # Find all potential buttons
                # The specific structure mentioned: <span class="...">Add friend</span>
                try:
                    potential_buttons = await page.query_selector_all('span:text-is("Add friend")')
                    if not potential_buttons:
                        potential_buttons = await page.query_selector_all('span:text("Add friend")')
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
                            jittered_delay = BASE_DELAY + random.uniform(-1.5, 3.5)
                            print(f"[{friends_added_today}/{FRIEND_LIMIT_DAILY}] Friend request sent!")
                            print(f"Cooling down for {jittered_delay:.2f}s...")
                            await asyncio.sleep(jittered_delay)
                    except Exception as e:
                        print(f"Error clicking button: {e}")
                
                print("Scrolling for more members...")
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await Confuser.random_delay(3000, 5000)
                
            except Exception as e:
                error_msg = str(e)
                print(f"Error in main loop: {error_msg}")
                if "Target page, context or browser has been closed" in error_msg or "Browser closed" in error_msg:
                    print("Browser or page closed. Stopping agent.")
                    break
                await asyncio.sleep(5)

        print(f"Successfully sent {friends_added_today} friend requests today.")
        await asyncio.sleep(5)
        await context.close()

        # Update last_marketed_date in DB
        if friends_added_today > 0 and group_record:
            db_session = SessionLocal()
            try:
                g = db_session.query(FBGroup).filter(FBGroup.id == group_record.id).first()
                if g:
                    g.last_marketed_date = datetime.now()
                    db_session.commit()
                    print(f"Updated last_marketed_date for {g.name}")
            except Exception as e:
                print(f"Error updating DB: {e}")
            finally:
                db_session.close()

if __name__ == "__main__":
    try:
        asyncio.run(run_fb_automation())
    except KeyboardInterrupt:
        print("\nStopping agent...")
