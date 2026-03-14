import subprocess
import time
import os
import sys
import random
from datetime import datetime, timedelta
import typing

# --- CONFIGURATION (All times in JST) ---
LIKER_TIMES = ["12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]
MARKETING_TIME = ["13:00", "15:00", "17:00", "19:00", "21:00", "23:00"]
MESSENGER_TIME = ["11:00"]
POSTER_TIME = ["05:00"]  # 10:00 AM HST is 05:00 AM JST: paused for now
JITTER_MIN_MINUTES = 2
JITTER_MAX_MINUTES = 8
CHECK_INTERVAL_SECONDS = 60  # Check every minute

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIKER_SCRIPT = os.path.join(BASE_DIR, "fb_liker.py")
MARKETING_SCRIPT = os.path.join(BASE_DIR, "fb_marketing_agent.py")
POSTER_SCRIPT = os.path.join(BASE_DIR, "fb_poster.py")
MESSENGER_SCRIPT = os.path.join(BASE_DIR, "fb_messenger.py")


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [Orchestrator] {message}")
    sys.stdout.flush()

def run_script(cmd):
    log(f"Executing: {' '.join(cmd)}")
    try:
        # Use subprocess.run to wait for completion
        # This prevents profile lock collisions
        result = subprocess.run(cmd, capture_output=False, text=True)
        if result.returncode == 0:
            log(f"Successfully finished: {cmd[-1]}")
            return True
        else:
            log(f"Script failed with return code {result.returncode}: {cmd[-1]}")
            return False
    except Exception as e:
        log(f"Error running script {cmd[-1]}: {e}")
        return False

def get_target_time(time_str, date_str):
    """Returns a datetime object for the given HH:MM and YYYY-MM-DD."""
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

def main():
    log("Facebook Marketing Orchestrator started.")
    
    # Track which specific slots have been run today to avoid double-runs
    # Format: "YYYY-MM-DD_Script_Time"
    completed_runs: typing.Set[str] = set()

    # Pre-populate with anything that passed today already to avoid triggering 
    # old tasks immediately on script startup.
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
                    # Add jitter: wait a few minutes if we just hit the time
                    delay = random.randint(JITTER_MIN_MINUTES, JITTER_MAX_MINUTES)
                    if now >= target_dt + timedelta(minutes=delay):
                        log(f"Due for Liker run (scheduled for {t}, with {delay}m jitter).")
                        success = run_script(["uv", "run", "python", LIKER_SCRIPT, "--once"])
                        completed_runs.add(run_id)
                    elif now >= target_dt:
                        # We are in the jitter window, just wait
                        pass

        # 2. Check Marketing Schedule
        for t in MARKETING_TIME:
            run_id = f"{current_date}_marketing_{t}"
            if run_id not in completed_runs:
                target_dt = get_target_time(t, current_date)
                if now >= target_dt:
                    delay = random.randint(JITTER_MIN_MINUTES, JITTER_MAX_MINUTES)
                    if now >= target_dt + timedelta(minutes=delay):
                        log(f"Due for Marketing run (scheduled for {t}, with {delay}m jitter).")
                        success = run_script(["uv", "run", "python", MARKETING_SCRIPT])
                        completed_runs.add(run_id)

        # 3. Check Poster Schedule (Paused for now)
        # for t in POSTER_TIME:
        #     run_id = f"{current_date}_poster_{t}"
        #     if run_id not in completed_runs:
        #         target_dt = get_target_time(t, current_date)
        #         if now >= target_dt:
        #             delay = random.randint(JITTER_MIN_MINUTES, JITTER_MAX_MINUTES)
        #             if now >= target_dt + timedelta(minutes=delay):
        #                 log(f"Due for Poster run (scheduled for {t}, with {delay}m jitter).")
        #                 success = run_script(["uv", "run", "python", POSTER_SCRIPT])
        #                 completed_runs.add(run_id)

        # 4. Check Messenger Schedule
        for t in MESSENGER_TIME:
            run_id = f"{current_date}_messenger_{t}"
            if run_id not in completed_runs:
                target_dt = get_target_time(t, current_date)
                if now >= target_dt:
                    delay = random.randint(JITTER_MIN_MINUTES, JITTER_MAX_MINUTES)
                    if now >= target_dt + timedelta(minutes=delay):
                        log(f"Due for Messenger run (scheduled for {t}, with {delay}m jitter).")
                        success = run_script(["uv", "run", "python", MESSENGER_SCRIPT])
                        completed_runs.add(run_id)

        # Cleanup old runs from set periodically (e.g., at midnight)
        if current_hm == "00:00":
            # Keep only today's runs in the set to prevent it from growing infinitely
            # (Though it would take years to be a problem, it's good practice)
            # Actually, let's just clear runs from yesterday
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            completed_runs = {r for r in completed_runs if not r.startswith(yesterday)}

        # Sleep until next check
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
