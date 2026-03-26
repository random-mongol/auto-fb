import subprocess
import time
import os
import sys
import random
from datetime import datetime, timedelta
import typing
from accounts import load_accounts

# --- CONFIGURATION (All times in JST) ---
LIKER_TIMES = ["12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]
MARKETING_TIME = ["13:00", "15:00", "17:00", "19:00", "21:00", "23:00"]
MESSENGER_TIME = ["11:00", "19:30"]
POSTER_TIME = ["05:00"]  # 10:00 AM HST is 05:00 AM JST: paused for now
KHANBANK_TIME = []  # ["09:00", "15:00", "21:00"]
JITTER_MIN_MINUTES = 2
JITTER_MAX_MINUTES = 8
CHECK_INTERVAL_SECONDS = 60  # Check every minute

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIKER_SCRIPT = os.path.join(BASE_DIR, "fb_liker.py")
MARKETING_SCRIPT = os.path.join(BASE_DIR, "fb_marketing_agent.py")
POSTER_SCRIPT = os.path.join(BASE_DIR, "fb_poster.py")
MESSENGER_SCRIPT = os.path.join(BASE_DIR, "fb_messenger.py")
KHANBANK_SCRIPT = os.path.join(BASE_DIR, "khanbank_login.py")


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [Orchestrator] {message}")
    sys.stdout.flush()


def run_script(cmd):
    log(f"Executing: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        if result.returncode == 0:
            log(f"Successfully finished: {' '.join(cmd[-3:])}")
            return True
        else:
            log(f"Script failed with return code {result.returncode}: {' '.join(cmd[-3:])}")
            return False
    except Exception as e:
        log(f"Error running script: {e}")
        return False


def run_for_all_accounts(script_path, extra_args=None):
    """Run a script sequentially for every configured account."""
    accounts = load_accounts()
    for account in accounts:
        cmd = ["uv", "run", "python", script_path, "--account", account.id]
        if extra_args:
            cmd.extend(extra_args)
        run_script(cmd)


def get_target_time(time_str, date_str):
    """Returns a datetime object for the given HH:MM and YYYY-MM-DD."""
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def main():
    log("Facebook Marketing Orchestrator started.")

    accounts = load_accounts()
    log(f"Loaded {len(accounts)} account(s): {[a.id for a in accounts]}")

    # Track which specific slots have been run today to avoid double-runs
    # Format: "YYYY-MM-DD_Script_Time"
    completed_runs: typing.Set[str] = set()

    # Pre-populate with anything that passed today already
    now_startup = datetime.now()
    current_date_startup = now_startup.strftime("%Y-%m-%d")

    for t in LIKER_TIMES:
        if now_startup >= get_target_time(t, current_date_startup):
            completed_runs.add(f"{current_date_startup}_liker_{t}")
    for t in MARKETING_TIME:
        if now_startup >= get_target_time(t, current_date_startup):
            completed_runs.add(f"{current_date_startup}_marketing_{t}")
    for t in MESSENGER_TIME:
        if now_startup >= get_target_time(t, current_date_startup):
            completed_runs.add(f"{current_date_startup}_messenger_{t}")
    # for t in POSTER_TIME:
    #     if now_startup >= get_target_time(t, current_date_startup):
    #         completed_runs.add(f"{current_date_startup}_poster_{t}")
    for t in KHANBANK_TIME:
        if now_startup >= get_target_time(t, current_date_startup):
            completed_runs.add(f"{current_date_startup}_khanbank_{t}")

    if completed_runs:
        log(f"Skipping {len(completed_runs)} already-passed tasks for today.")

    while True:
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_hm = now.strftime("%H:%M")

        # 1. Check Liker Schedule
        for t in LIKER_TIMES:
            run_id = f"{current_date}_liker_{t}"
            if run_id not in completed_runs:
                target_dt = get_target_time(t, current_date)
                if now >= target_dt:
                    delay = random.randint(JITTER_MIN_MINUTES, JITTER_MAX_MINUTES)
                    if now >= target_dt + timedelta(minutes=delay):
                        log(f"Due for Liker run (scheduled {t}, {delay}m jitter) — running for all accounts.")
                        run_for_all_accounts(LIKER_SCRIPT, extra_args=["--once"])
                        completed_runs.add(run_id)

        # 2. Check Marketing Schedule
        for t in MARKETING_TIME:
            run_id = f"{current_date}_marketing_{t}"
            if run_id not in completed_runs:
                target_dt = get_target_time(t, current_date)
                if now >= target_dt:
                    delay = random.randint(JITTER_MIN_MINUTES, JITTER_MAX_MINUTES)
                    if now >= target_dt + timedelta(minutes=delay):
                        log(f"Due for Marketing run (scheduled {t}, {delay}m jitter) — running for all accounts.")
                        run_for_all_accounts(MARKETING_SCRIPT)
                        completed_runs.add(run_id)

        # 3. Check Poster Schedule (Paused for now)
        # for t in POSTER_TIME:
        #     run_id = f"{current_date}_poster_{t}"
        #     if run_id not in completed_runs:
        #         target_dt = get_target_time(t, current_date)
        #         if now >= target_dt:
        #             delay = random.randint(JITTER_MIN_MINUTES, JITTER_MAX_MINUTES)
        #             if now >= target_dt + timedelta(minutes=delay):
        #                 log(f"Due for Poster run (scheduled {t}, {delay}m jitter) — running for all accounts.")
        #                 run_for_all_accounts(POSTER_SCRIPT)
        #                 completed_runs.add(run_id)

        # 4. Check Messenger Schedule
        for t in MESSENGER_TIME:
            run_id = f"{current_date}_messenger_{t}"
            if run_id not in completed_runs:
                target_dt = get_target_time(t, current_date)
                if now >= target_dt:
                    delay = random.randint(JITTER_MIN_MINUTES, JITTER_MAX_MINUTES)
                    if now >= target_dt + timedelta(minutes=delay):
                        log(f"Due for Messenger run (scheduled {t}, {delay}m jitter) — running for all accounts.")
                        run_for_all_accounts(MESSENGER_SCRIPT)
                        completed_runs.add(run_id)

        # 5. Check Khan Bank Schedule
        for t in KHANBANK_TIME:
            run_id = f"{current_date}_khanbank_{t}"
            if run_id not in completed_runs:
                target_dt = get_target_time(t, current_date)
                if now >= target_dt:
                    delay = random.randint(JITTER_MIN_MINUTES, JITTER_MAX_MINUTES)
                    if now >= target_dt + timedelta(minutes=delay):
                        log(f"Due for Khan Bank run (scheduled {t}, {delay}m jitter).")
                        run_script(["uv", "run", "python", KHANBANK_SCRIPT])
                        completed_runs.add(run_id)

        # Cleanup old runs from set at midnight
        if current_hm == "00:00":
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            completed_runs = {r for r in completed_runs if not r.startswith(yesterday)}

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Orchestrator stopped by user.")
        sys.exit(0)
    except Exception as e:
        log(f"CRITICAL ERROR in Orchestrator: {e}")
        sys.exit(1)
