import asyncio
import random
import os
import time
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from python_ghost_cursor.playwright_async import create_cursor
import dotenv
from sqlalchemy import func
from database import SessionLocal
from models import FBGroup
from datetime import datetime

# Removed hardcoded GROUP_URLS as per AGENTS.md rules. URLs are fetched from the database.


TARGET_LIKES = 5
DELAY_BETWEEN_LIKES = 5  # seconds
INTERVAL_HOURS = 4

# Browser profile path configuration
# Use the same profile as the friend request sender, sourced from .env
PROFILE_DIR = os.getenv("FB_PROFILE_PATH", os.path.join(os.getcwd(), "fb_profile"))

# Ensure profile directory exists
if not os.path.exists(PROFILE_DIR):
    os.makedirs(PROFILE_DIR)

class Confuser:
    """Utility to add noise and human-like delays to interactions."""
    @staticmethod
    async def random_delay(min_ms=2000, max_ms=5000):
        """Adds a random delay based on ms range. Default 2-5s as per AGENTS.md."""
        delay = random.uniform(min_ms, max_ms) / 1000.0
        await asyncio.sleep(delay)

async def perform_group_likes():
    # Attempt to get a group from the database
    db = SessionLocal()
    target_url = None
    group_record = None
    
    try:
        # Select the "most previously liked" group (the one whose previous like was furthest in the past)
        # We use nullslast() to prioritize groups that have at least been liked once before,
        # but the general logic in the repo is to rotate through all groups.
        # If the user specifically said "most previously liked", they might mean prioritizing those with a history.
        group_record = db.query(FBGroup).order_by(FBGroup.last_liked_date.asc().nullslast(), func.random()).first()
        
        if group_record:
            target_url = group_record.facebook
            print(f"Selected group from DB: {group_record.name or target_url} (Last liked: {group_record.last_liked_date})")
    except Exception as e:
        print(f"Error fetching from DB: {e}")
    finally:
        db.close()

    if not target_url:
        print("No group URLs found in the database. Please import groups first.")
        return
        
    print(f"\n--- Starting run at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    print(f"Target Group: {target_url}")

    async with async_playwright() as p:
        # Launch persistent context to use the same logged-in environment
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False, # Keep False to see it working and handle any login/checkpoints
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
                # Ensure element is in view before ghost-cursor tries to move to it
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(0.5, 1.5))
                # Use ghost-cursor for realistic movement
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
                    # Use domcontentloaded for FB because it never stops making network requests
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                    # Wait for a key element or main role to ensure page is somewhat ready
                    try:
                        await page.wait_for_selector('div[role="main"]', timeout=15000)
                    except:
                        pass # Continue anyway, main role might have changed labels
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
            
            # Additional settle delay
            await asyncio.sleep(8)

            # Check for login
            if "login" in page.url or "checkpoint" in page.url:
                print("Action Required: Please handle login or checkpoint in the browser window.")
                # Wait for user to bypass
                try:
                    while any(x in page.url for x in ["login", "checkpoint", "facebook.com/login"]):
                        await asyncio.sleep(5)
                except Exception as e:
                    if "Target page, context or browser has been closed" in str(e):
                        print("Browser closed during login check. Stopping.")
                        return
                    raise e
                print("Proceeding after login...")
                # Re-navigate to the target URL if we were redirected away and stayed there
                if target_url not in page.url:
                    print(f"Re-navigating to target: {target_url}")
                    await page.goto(target_url, wait_until="domcontentloaded")
                    await asyncio.sleep(5)

            likes_done = 0
            # Target likes specifically within articles (posts) to avoid sidebar/group buttons
            like_selector = 'div[role="article"] div[aria-label="Like"]'
            
            print(f"Starting to scroll and like {TARGET_LIKES} posts...")
            
            max_scroll_attempts = 50
            for scroll in range(max_scroll_attempts):
                if likes_done >= TARGET_LIKES:
                    break

                # Find all visible like buttons
                try:
                    # Wait for the main container
                    await page.wait_for_selector('div[role="main"]', timeout=5000)
                    # Query buttons within articles to be safe
                    buttons = await page.query_selector_all(like_selector)
                    
                    # If no buttons found with article scoping, fallback to generic as a last resort
                    # but only if we haven't found anything for a few scrolls.
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
                        
                        # Check if it is already "Liked" or if it is the wrong button
                        label = await btn.get_attribute("aria-label")
                        if label != "Like":
                            # FB changes label to "Remove Like" or "Unlike"
                            continue
                        
                        # Ensure it's visible
                        if not await btn.is_visible():
                            continue
                        
                        # Further validation: ensure there is a "Like" text inside
                        # This avoids clicking icons that might have the same label but are not the main button
                        span = await btn.query_selector('span:text-is("Like")')
                        if not span:
                            span = await btn.query_selector('span:has-text("Like")')
                        
                        if not span:
                            continue

                        # Try to click the button
                        print(f"Liking post {likes_done + 1}/{TARGET_LIKES}...")
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

                # Scroll down to find more posts
                print(f"Scrolling down... (Current likes: {likes_done}/{TARGET_LIKES})")
                await page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(3) # Wait for content to load

            print(f"Run complete. Total likes today: {likes_done}")

            # Update DB timestamp if we liked anything
            if likes_done > 0 and group_record:
                db = SessionLocal()
                try:
                    # reload to avoid detached session issues
                    g = db.query(FBGroup).filter(FBGroup.id == group_record.id).first()
                    if g:
                        g.last_liked_date = datetime.now()
                        db.commit()
                        print(f"Updated last_liked_date for {g.name}")
                except Exception as e:
                    print(f"Error updating DB: {e}")
                finally:
                    db.close()

        except Exception as e:
            print(f"An error occurred during execution: {e}")
        finally:
            await context.close()

async def main_loop():
    print(f"FB Liker started. Will run every {INTERVAL_HOURS} hours.")
    while True:
        try:
            await perform_group_likes()
        except Exception as e:
            print(f"Error in main loop: {e}")
        
        print(f"\nWaiting {INTERVAL_HOURS} hours for next run...")
        # Countdown for visual feedback (optional)
        # For simplicity, just sleep
        await asyncio.sleep(INTERVAL_HOURS * 3600)

if __name__ == "__main__":
    try:
        # Check if we should run once or on loop
        import sys
        if "--once" in sys.argv:
            asyncio.run(perform_group_likes())
        else:
            asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nFB Liker stopped.")
