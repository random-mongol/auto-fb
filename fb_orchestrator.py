import subprocess
import time
import os
import sys
from datetime import datetime, timedelta

# --- CONFIGURATION ---
LIKER_INTERVAL_HOURS = 4
MARKETING_HOUR_JST = 10  # 10:00 AM JST
CHECK_INTERVAL_SECONDS = 60  # Check every minute

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIKER_SCRIPT = os.path.join(BASE_DIR, "fb_liker.py")
MARKETING_SCRIPT = os.path.join(BASE_DIR, "fb_marketing_agent.py")

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

def main():
    log("Facebook Marketing Orchestrator started.")
    
    last_liker_run = datetime.min
    last_marketing_run_date = ""

    while True:
        now = datetime.now()
        current_date_str = now.strftime("%Y-%m-%d")

        # 1. Check Liker (Every 4 hours)
        if now >= last_liker_run + timedelta(hours=LIKER_INTERVAL_HOURS):
            log("Due for Liker run.")
            success = run_script(["uv", "run", "python", LIKER_SCRIPT, "--once"])
            if success:
                last_liker_run = datetime.now() # Update only on success or attempt? 
                # Better update always to avoid infinite retry loops if it keeps failing
                last_liker_run = datetime.now()
            else:
                # If failed, we might want to retry sooner, but for now let's just stick to the interval
                last_liker_run = datetime.now()

        # 2. Check Marketing Agent (Once a day at/after MARKETING_HOUR_JST)
        if now.hour >= MARKETING_HOUR_JST and last_marketing_run_date != current_date_str:
            log("Due for Marketing run.")
            success = run_script(["uv", "run", "python", MARKETING_SCRIPT])
            if success:
                last_marketing_run_date = current_date_str
            else:
                # If failed, we don't update the date so it can retry in the next 1-minute check
                # But to avoid rapid fire failure, let's wait a bit
                log("Marketing run failed. Will retry in the next check.")
                time.sleep(300) # Wait 5 mins before next check if something is wrong

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
