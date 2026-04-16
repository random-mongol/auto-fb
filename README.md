Automatic
[x] Facebook friend request sender
[x] Facebook group content liker
[x] Facebook poster from web content, and share 
[x] Reel generator pipeline
[x] Friend Request Follow-Up Messenger
   [ ] Reply follow up message
[ ] Find and discover new facebook groups
- Store in the database 
- Ask to join and store 
[ ] Post to other groups
[ ] Write comments

- Friend Request Follow-Up Messenger
- Reel generator 

Requires AI
- Facebook group content commenter
- Scrape -> Like/comment on best one
- AI Post Generator (Nvidea AI)

Integrate postgres

- SEO post writer. 


Page automation.

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

## Automated Group Liking (`fb_liker.py`)

A specialized script to maintain group activity by liking posts.

### Features
- **Every 4 Hours**: Automatically runs on a loop (4-hour interval).
- **Target Groups**: Randomly picks a group from a configurable list.
- **Human-Like Activity**: Scrolls down and likes 10 visible posts per run.
- **Jittered Timing**: 5-second baseline delay between likes plus random noise.
- **Shared Session**: Uses the `fb_profile` folder to share login state with the marketing agent.

## Automation & Scheduling

The project uses a unified orchestrator to manage multiple tasks and handle timing. It ensures that only one script runs at a time to avoid conflicts with the browser profile.

### Start the Orchestrator
```bash
uv run python fb_orchestrator.py
```

### Schedule
- **Facebook Liker**: Runs every 4 hours (lking 10 posts).
- **Marketing Agent**: Runs once daily at 10:00 JST (sending up to 20 friend requests).

### Individual Script Testing
If you want to run scripts manually for testing:
- **Test Liker**: `uv run python fb_liker.py --once`
- **Test Marketing**: `uv run python fb_marketing_agent.py`


# Manual operations by human 

## 
1. Go to https://www.facebook.com/groups/joins/?nav_source=tab
2. Copy element inside <div role="list"/> inside <div role="main"/>
3. Copy element into data/joined-group-list.html


Task	Command
Run Migrations	`uv run alembic upgrade head`
Import Groups from HTML	`uv run python import_groups.py`
Test Liker (Single Run)	`uv run python fb_liker.py --once`
Test Marketing Agent	`uv run python fb_marketing_agent.py`
Generate Reel Pipeline	`uv run python fb_reel_generator.py`
