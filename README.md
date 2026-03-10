# Facebook Marketing Agent (AI-Powered)

This project automates Facebook friend requests using Playwright with stealth, residential proxy support, and human-like interactions (Ghost-Cursor).

## Features
- **Ghost-Cursor**: Realistic, curved mouse movements.
- **Stealth**: Bypasses bot detection using `playwright-stealth`.
- **Persistent Profile**: Saves cookies and session data to avoid repeated logins.
- **Confuser Utility**: Adds noise to interactions (random typing speed, delays).
- **Residential Proxy Support**: Easily configured via `.env`.
- **Daily Limits**: Automatically stops after sending 20 requests.

## Setup

1. **Install Dependencies**:
   ```bash
   uv sync
   uv run playwright install chromium
   ```

2. **Configure Environment**:
   - Copy `.env.example` to `.env`.
   - Fill in your residential proxy details (if using).
   - Customize `FB_PROFILE_PATH` if needed.

3. **Run the Agent**:
   ```bash
   uv run python fb_marketing_agent.py
   ```

## Usage Notes
- **First Run**: On the first run, the browser will open and you may need to log in manually. The persistent profile will save your session, so you won't need to log in again.
- **Headed Mode**: The agent always runs in headed mode as requested to look more human and allow manual intervention if needed (e.g., solving a captcha).
- **Target Page**: The agent is configured to visit: `https://www.facebook.com/groups/LegalWindowMGL/members/contributors`.

## Automated Logic
- Navigates to the contributors page.
- Scrolls automatically to load more members.
- Identifies "Add friend" buttons.
- Moves the mouse realistically to each button using Ghost-Cursor.
- Clicks and waits 5 seconds (plus random noise) between requests.
- Stops after 20 successful requests.


