# 🤖 Agent Instructions & Repository Guide

Welcome, Agent. This file serves as the primary technical documentation and operational guide for any AI agent working on the `auto-fb` repository. 

## 🎯 Repository Goal
The goal of this project is to build a high-stealth, human-mimicking Facebook marketing automation suite. It focuses on the following:
- **Friend Request Automation**: Targetting specific group contributors and members.
- **Engagement Automation**: Automatically liking posts in target groups to maintain presence.
- **Stealth & Safety**: Prioritizing account longevity by using residential proxies, realistic mouse movements (Ghost-Cursor), and strictly controlled interaction limits.

---

## 🏗 Repository Structure

- `fb_orchestrator.py`: The master scheduler that triggers the scripts at the correct intervals and handles execution.
- `fb_marketing_agent.py`: The core agent for sending friend requests. Uses Playwright + Ghost-Cursor.
- `fb_liker.py`: Engagement script. Supports both looping and single runs (`--once`).
- `fb_poster.py`: Automatic article posting script. Fetches articles from `huuli.tech` and posts them to a specific profile.
- `pyproject.toml` & `uv.lock`: Dependency management via `uv`. Always use `uv sync` to set up the environment.

- `.env`: Contains configuration for `PROXY_SERVER`, `FB_PROFILE_PATH`, `DATABASE_URL`, and target group URLs.
- `database.py` & `models.py`: SQLAlchemy database configuration and models.
- `alembic/`: Database migration scripts.
- `import_groups.py`: Utility to import groups from a local HTML file.

---

## 🛠 Operational Advice for Agents

### 1. Environment & Execution
- **Use `uv`**: Always execute scripts via `uv run python <script>.py`.
- **Headed Mode**: All scripts are configured to run in **headed mode** (`headless=False`). This is intentional to bypass bot detection and allow the user to intervene if a CAPTCHA or "Checkpoint" appears.
- **Stealth First**: Do not skip the `create_cursor` step from `ghost-cursor`. All interactions (`click`, `move`, `scroll`) should go through the cursor, not direct Playwright selectors.

### 2. Working with the Facebook Profile
- If you need to debug a login issue, check if the `fb_profile` directory exists and has content.
- When adding new features that require a new URL, ensure you check if the session is still valid by looking for a specific element (like the search bar or profile icon) before proceeding.

### 3. Rate Limits & Jitter
- **Friend Requests**: Capped at 20 per day.
- **Liking**: Capped at 5 likes per run (every 4 hours).
- **Delays**: Always implement "Human Jitter." Never use fixed sleep times. Use a baseline (e.g., 5s) plus a random variance (2s - 5s).

### 4. Code Style
- **Error Handling**: Use broad `try...except` blocks to prevent crashes from network blips.
- **Logging**: Log actions to `stdout`. When using the orchestrator, these logs are captured in terminal output or redirected to logs.

### 5. Automation & Scheduling (Orchestrator)
The project uses `fb_orchestrator.py` instead of OS-specific schedulers (like `plist` or `cron`).
- **Liker**: Runs 6 times a day (12, 2, 4, 6, 8, 10 PM JST).
- **Marketing (Friend Requests)**: Runs daily at 01:00 JST.
- **Poster**: Runs daily at 05:00 JST (matched to 10:00 AM HST).
- **Stealth Scheduling**: All tasks have a random jitter delay (2-8 minutes) added to their scheduled time to avoid predictable patterns.
- **All times/schedules are defined in JST.**
- **Safety**: The orchestrator ensures that only one script runs at a time to prevent `fb_profile` lock collisions.

### 6. Database & Migrations
The project uses PostgreSQL with SQLAlchemy.
- **Migrations**: Always use Alembic for schema changes.
- **Dynamic URLs**: Scripts no longer rely on hardcoded lists in the code. They fetch URLs from the `fbgroups` table.
- **Liker Logic**: Prioritizes the "most previously liked" group (the one with the oldest `last_liked_date`) to ensure rotation.
- **Marketing Logic**: Prioritizes groups that haven't been visited recently (`last_marketed_date`).
- **Profile Path**: Both scripts now respect the `FB_PROFILE_PATH` defined in `.env` for consistent session management.
- **Tracking**: `last_liked_date` and `last_marketed_date` are updated automatically by the scripts.

---

## 🚀 Common Commands

| Task | Command |
| :--- | :--- |
| Install/Update | `uv sync` |
| Install Browsers | `uv run playwright install chromium` |
| **Start Orchestrator** | `uv run python fb_orchestrator.py` |
| Test Marketing Agent | `uv run python fb_marketing_agent.py` |
| Test Liker (Once) | `uv run python fb_liker.py --once` |
| **Test Messenger** | `uv run python fb_messenger.py` |
| **Run Migrations** | `uv run alembic upgrade head` |
| **Import Groups** | `uv run python import_groups.py` |
| **Test Poster** | `uv run python fb_poster.py` |
| **Generate Reel** | `uv run python fb_reel_generator.py` |

---

## ⚠️ Safety Warning
Facebook detects automation patterns aggressively. If you are modifying the interaction logic, ensure you are not creating a predictable sequence of events. Randomize the scroll depth, the time spent "reading" a post, and the path the mouse takes to a button.

## Guides
When you change something, please update or append your changes to the AGENTS.md at the end of your operation.

### Update 2026-03-14 (v2): Messenger Automation for New Friends
- **`fb_messenger.py` Added**:
    - Automates sending greetings to 5 new friends from `https://www.facebook.com/friends/list`.
    - Implements a "New Conversation" check: Only sends a message if no prior history exists (checked by empty chat log or "You're friends on Facebook" indicator).
    - Uses the shared `common_fb_profile` for session consistency.
    - Includes human-mimicking jitter and randomized message templates.
    - Automatically closes chat windows after processing each friend.

### Update 2026-03-11: Improved Wait & Retry Logic
- **`fb_liker.py` Improvements**:
    - Added a navigation retry mechanism (up to 3 attempts).
    - Implemented a check for "Execution context was destroyed" errors. Instead of crashing, the script now waits 3 seconds and retries the interaction (after a small scroll).
    - Standardized "Human Jitter" to strictly follow the 2-5s variance rule over a 5s baseline.
    - Updated `TARGET_LIKES` to 5 to match repo standards.
    - Added better handling for browser closure during long operations (Detects "Target page closed" and exits gracefully).

### Update 2026-03-12: Automated Article Posting
- **`fb_poster.py` Added**:
    - Fetches articles from `https://huuli.tech/sitemap.xml`.
    - Filters out already posted articles using the `posted_articles` table.
    - Automates the posting process on the user's Facebook profile.
    - Integrated into `fb_orchestrator.py` to run daily at 10:05 JST.
- **Database Changes**:
    - Added `posted_articles` table to track URL history.

### Update 2026-03-12 (v2): Schedule & Jitter Unification
- **`fb_orchestrator.py` Updated**:
    - Unified all schedules at the top of the script.
    - Updated Liker to run 6 times a day: 12, 14, 16, 18, 20, 22 (JST).
    - Updated Marketing (Friend Request) to run at 01:00 JST.
    - Updated Poster to run at 05:00 JST (10:00 AM HST).
    - Added a mandatory random jitter (2-8 minutes) to all scheduled runs for increased stealth.
    - Standardized all internal timekeeping to JST.

### Update 2026-03-11 (v2): Orchestrator Startup Logic
- **`fb_orchestrator.py` Updated**:
    - Prevented immediate execution of missed tasks upon script startup.
    - The orchestrator now pre-populates the "completed runs" set with any scheduled tasks that have already passed for the current day, ensuring it waits for the *next* scheduled occurrence.

### Update 2026-03-11 (v3): Switch Posting to Facebook Page & Engagement
- **`fb_poster.py` Updated**:
    - Changed the target from the user's home wall to the Facebook Page "huuli.tech - Хуульчийн ухаалаг туслах."
    - Implemented a generic `switch_profile` function to handle switching between any profile/page.
    - Added a "Phase 2" engagement step: After posting as a page, the script switches back to the personal profile ("Хуульч Сэцэн") to Like and Share the new post to the personal feed.
    - Added mandatory 'Next' button click step when posting as a Page.
    - Standardized `human_click` as a shared utility to handle all interaction logic.
    - Updated `FB_PROFILE_URL` to the page's profile URL: `https://www.facebook.com/profile.php?id=61579195435310`.

### Update 2026-03-12 (v3): Robust Selectors for Posting
- **`fb_poster.py` Selector Fix**:
    - Improved 'What's on your mind?' trigger and modal detection with multiple fallback selectors (Localizations/Different Page UI).
    - Updated 'Post' button selectors to include `div[aria-label="Post"]` and lowercase "post" text as suggested by user logs.
    - Simplified 'Next' button selector for better reliability during Page posting.

### Update 2026-03-14: Reduced Unnecessary Clicks & Improved Reliability
- **Selector Scoping**: 
    - `fb_liker.py`: Updated 'Like' button selector to specifically target elements within `div[role="article"]`. This prevents the script from accidentally clicking the "Like" buttons in sidebars, suggested groups, or header elements.
    - `fb_poster.py`: Updated engagement 'Like' selector to target the first post in the main feed, avoiding the Page-like button on the profile header.
    - `fb_poster.py`: Re-ordered 'Post' button selectors to prioritize dialog-bound elements.
- **`human_click` Enhancements**:
    - Unified `human_click` across all scripts to include mandatory `scroll_into_view_if_needed()`.
    - Added a small random jitter (0.5s - 1.5s) after scrolling and before clicking to allow the UI to settle and mimic human pause.
    - This reduces "random" clicks caused by elements moving during ghost-cursor transit.

### Update 2026-03-14 (v3): Messenger Integration in Orchestrator
- **`fb_orchestrator.py` Updated**:
    - Integrated `fb_messenger.py` into the daily schedule.
    - Set Messenger script to run daily at 11:00 JST.
    - Added Messenger task to the startup completion check and main scheduling loop.
    - Fixed potentially orphaned code in the Poster section of the orchestrator to ensure clean execution.

### Update 2026-03-14 (v4): Resumable Reel Generation Pipeline
- **`fb_reel_generator.py` Added**:
    - Implements a resumable artifact pipeline for `topic -> script -> voice -> visuals -> edit`.
    - Pulls candidate legal topics from `https://huuli.tech/sitemap.xml`, skips already-generated articles via the database, and stores artifacts under `artifacts/reels/<slug>/`.
    - Supports `--step`, `--source-url`, `--reel-id`, and `--force` so runs can resume from any step without redoing completed work.
    - Generates short script artifacts with an OpenAI hook when `OPENAI_API_KEY` and `OPENAI_MODEL` are configured, and falls back to a deterministic local script builder otherwise.
    - Generates ElevenLabs voice plus word timestamps when `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` are configured, and falls back to silent audio plus synthetic timestamps otherwise.
    - Produces animated gradient backgrounds, grouped subtitle timing, and a final vertical reel video using MoviePy/Pillow.
- **Database Changes**:
    - Added `generated_reels` table to track source URLs, artifact directories, step completion timestamps, and error state for resumable generation.
### Update 2026-03-14 (v4): Messenger Message Rotation & Limits
- **`fb_messenger.py` Updated**:
    - Reduced `TARGET_MESSAGES_PER_RUN` to 3 (previously 5).
    - Implemented a rotation/randomization of 3 similar message templates in Mongolian to increase stealth and avoid message spam detection.
    - Updated logging to show a snippet of the message being sent.
### Update 2026-03-15: Khan Bank Login Helper
- **`khanbank_login.py` Added**:
    - Opens `https://corp.khanbank.com/auth/login` in a headed Playwright Chromium session.
    - Loads `BANK_USERNAME` and `BANK_PASSWORD` from `.env`.
    - Targets the username and password inputs by placeholder text (`Нэвтрэх нэр`, `Нууц үг`) and submits via the page's `[type="submit"]` button.
    - Uses `playwright-stealth`, `ghost-cursor`, and randomized typing/click delays to stay consistent with the repo's human-like interaction pattern.
### Update 2026-03-15 (v2): Khan Bank Shared Profile
- **`khanbank_login.py` Updated**:
    - Switched the browser profile to use `FB_PROFILE_PATH` so the Khan Bank helper shares the same persistent Chromium profile as the rest of the automation suite.
### Update 2026-03-15 (v3): Khan Bank Transaction Monitoring
- **`khanbank_login.py` Updated**:
    - Added automated transaction monitoring after login.
    - Scrapes the "Recent Transactions" list on the home page.
    - Sends new transactions to a dedicated Discord webhook.
    - Implemented `.last_bank_tx.json` to track the last sent transaction and avoid duplicates.
    - Includes a background loop that re-checks for transactions every 2 minutes while the browser is open.
    - Added a 15-minute timeout to the script to allow the orchestrator to continue other tasks.
- **`fb_orchestrator.py` Updated**:
    - Integrated Khan Bank monitoring into the daily schedule.
    - Set to run 3 times daily: **09:00, 15:00, and 21:00 JST**.
    - Includes randomized jitter (2-8 minutes) for stealth.

### Update 2026-04-16: Orchestrator Startup Bootstrap & Persistent Schedule State
- **`fb_orchestrator.py` Updated**:
    - Added a startup bootstrap pass for the active Facebook automations (`fb_liker.py`, `fb_marketing_agent.py`, and `fb_messenger.py`) so the orchestrator does useful work immediately after launch instead of appearing idle.
    - Replaced per-loop random jitter generation with a persisted per-slot jitter map stored in `.orchestrator_state.json`, keeping each scheduled run stable across checks and restarts.
    - Changed startup skip logic to only skip slots whose full due window (scheduled time + assigned jitter) has already passed, preventing false skips.
    - Added persistent tracking for completed schedule slots and same-day startup runs so restarts do not repeatedly trigger extra bootstrap passes, and only records a bootstrap/scheduled slot as completed when the underlying task succeeds.
    - Added clearer logging for per-account execution and the next upcoming scheduled run to make waiting behavior visible.
