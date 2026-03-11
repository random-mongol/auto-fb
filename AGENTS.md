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
- **Liker**: Runs every 4 hours.
- **Marketing**: Runs once a day at 10:00 JST.
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
| **Run Migrations** | `uv run alembic upgrade head` |
| **Import Groups** | `uv run python import_groups.py` |

---

## ⚠️ Safety Warning
Facebook detects automation patterns aggressively. If you are modifying the interaction logic, ensure you are not creating a predictable sequence of events. Randomize the scroll depth, the time spent "reading" a post, and the path the mouse takes to a button.

## Guides
When you change something, please update or append your changes to the AGENTS.md at the end of your operation.

### Update 2026-03-11: Improved Wait & Retry Logic
- **`fb_liker.py` Improvements**:
    - Added a navigation retry mechanism (up to 3 attempts).
    - Implemented a check for "Execution context was destroyed" errors. Instead of crashing, the script now waits 3 seconds and retries the interaction (after a small scroll).
    - Standardized "Human Jitter" to strictly follow the 2-5s variance rule over a 5s baseline.
    - Updated `TARGET_LIKES` to 5 to match repo standards.
    - Added better handling for browser closure during long operations (Detects "Target page closed" and exits gracefully).