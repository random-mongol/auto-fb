import json
import os
import random
import subprocess
import sys
import time
import typing
from datetime import datetime, timedelta

from accounts import load_accounts

# --- CONFIGURATION (All times in JST) ---
LIKER_TIMES = ["12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]
MARKETING_TIME = ["13:00", "15:00", "17:00", "19:00", "21:00", "23:00"]
MESSENGER_TIME = ["11:00", "15:30", "19:30"]
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
STATE_FILE = os.path.join(BASE_DIR, ".orchestrator_state.json")


TaskConfig = typing.Dict[str, typing.Any]


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [Orchestrator] {message}")
    sys.stdout.flush()


def build_tasks() -> typing.List[TaskConfig]:
    return [
        {
            "name": "liker",
            "label": "Liker",
            "enabled": True,
            "times": LIKER_TIMES,
            "startup": True,
            "runner": lambda: run_for_all_accounts(LIKER_SCRIPT, extra_args=["--once"]),
        },
        {
            "name": "marketing",
            "label": "Marketing",
            "enabled": True,
            "times": MARKETING_TIME,
            "startup": True,
            "runner": lambda: run_for_all_accounts(MARKETING_SCRIPT),
        },
        {
            "name": "poster",
            "label": "Poster",
            "enabled": False,
            "times": POSTER_TIME,
            "startup": False,
            "runner": lambda: run_for_all_accounts(POSTER_SCRIPT),
        },
        {
            "name": "messenger",
            "label": "Messenger",
            "enabled": True,
            "times": MESSENGER_TIME,
            "startup": True,
            "runner": lambda: run_for_all_accounts(MESSENGER_SCRIPT),
        },
        {
            "name": "khanbank",
            "label": "Khan Bank",
            "enabled": bool(KHANBANK_TIME),
            "times": KHANBANK_TIME,
            "startup": False,
            "runner": lambda: run_script(["uv", "run", "python", KHANBANK_SCRIPT]),
        },
    ]


def default_state() -> typing.Dict[str, typing.Any]:
    return {
        "completed_runs": [],
        "slot_jitter_minutes": {},
        "startup_runs": {},
    }


def load_state() -> typing.Dict[str, typing.Any]:
    if not os.path.exists(STATE_FILE):
        return default_state()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        log(f"Could not read orchestrator state file, starting fresh: {e}")
        return default_state()

    return {
        "completed_runs": state.get("completed_runs", []),
        "slot_jitter_minutes": state.get("slot_jitter_minutes", {}),
        "startup_runs": state.get("startup_runs", {}),
    }


def save_state(state: typing.Dict[str, typing.Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def prune_state(state: typing.Dict[str, typing.Any], current_date: str) -> typing.Dict[str, typing.Any]:
    state["completed_runs"] = [run_id for run_id in state["completed_runs"] if run_id.startswith(current_date)]
    state["slot_jitter_minutes"] = {
        run_id: minutes
        for run_id, minutes in state["slot_jitter_minutes"].items()
        if run_id.startswith(current_date)
    }
    state["startup_runs"] = {
        date_key: runs for date_key, runs in state["startup_runs"].items() if date_key == current_date
    }
    return state


def run_script(cmd):
    log(f"Executing: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        if result.returncode == 0:
            log(f"Successfully finished: {' '.join(cmd[-3:])}")
            return True

        log(f"Script failed with return code {result.returncode}: {' '.join(cmd[-3:])}")
        return False
    except Exception as e:
        log(f"Error running script: {e}")
        return False


def run_for_all_accounts(script_path, extra_args=None):
    """Run a script sequentially for every configured account."""
    accounts = load_accounts()
    if not accounts:
        log(f"No accounts configured for {os.path.basename(script_path)}.")
        return False

    all_succeeded = True
    for account in accounts:
        log(f"Running {os.path.basename(script_path)} for account '{account.id}'.")
        cmd = ["uv", "run", "python", script_path, "--account", account.id]
        if extra_args:
            cmd.extend(extra_args)
        if not run_script(cmd):
            all_succeeded = False

    return all_succeeded


def get_target_time(time_str, date_str):
    """Returns a datetime object for the given HH:MM and YYYY-MM-DD."""
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def make_run_id(date_str: str, task_name: str, time_str: str) -> str:
    return f"{date_str}_{task_name}_{time_str}"


def get_slot_jitter_minutes(state: typing.Dict[str, typing.Any], run_id: str) -> int:
    jitter = state["slot_jitter_minutes"].get(run_id)
    if jitter is None:
        jitter = random.randint(JITTER_MIN_MINUTES, JITTER_MAX_MINUTES)
        state["slot_jitter_minutes"][run_id] = jitter
        save_state(state)
    return jitter


def get_due_time(state: typing.Dict[str, typing.Any], date_str: str, task_name: str, time_str: str) -> datetime:
    run_id = make_run_id(date_str, task_name, time_str)
    jitter = get_slot_jitter_minutes(state, run_id)
    return get_target_time(time_str, date_str) + timedelta(minutes=jitter)


def mark_completed(
    completed_runs: typing.Set[str],
    state: typing.Dict[str, typing.Any],
    run_id: str,
) -> None:
    if run_id not in completed_runs:
        completed_runs.add(run_id)
        state["completed_runs"] = sorted(completed_runs)
        save_state(state)


def prepopulate_passed_slots(
    now: datetime,
    tasks: typing.List[TaskConfig],
    completed_runs: typing.Set[str],
    state: typing.Dict[str, typing.Any],
) -> int:
    current_date = now.strftime("%Y-%m-%d")
    skipped = 0

    for task in tasks:
        if not task["enabled"]:
            continue
        for time_str in task["times"]:
            run_id = make_run_id(current_date, task["name"], time_str)
            if run_id in completed_runs:
                continue

            due_time = get_due_time(state, current_date, task["name"], time_str)
            if now >= due_time:
                completed_runs.add(run_id)
                skipped += 1

    state["completed_runs"] = sorted(completed_runs)
    save_state(state)
    return skipped


def run_startup_bootstrap(
    current_date: str,
    tasks: typing.List[TaskConfig],
    state: typing.Dict[str, typing.Any],
) -> None:
    already_bootstrapped = set(state["startup_runs"].get(current_date, []))
    startup_tasks = [
        task
        for task in tasks
        if task["enabled"] and task["startup"] and task["times"] and task["name"] not in already_bootstrapped
    ]

    if not startup_tasks:
        log("Startup bootstrap already completed for today.")
        return

    log(
        "Running startup bootstrap so the active Facebook automations do at least one pass "
        f"before waiting for the next schedule: {[task['name'] for task in startup_tasks]}"
    )

    for task in startup_tasks:
        log(f"Startup run: {task['label']}.")
        if task["runner"]():
            already_bootstrapped.add(task["name"])
            state["startup_runs"][current_date] = sorted(already_bootstrapped)
            save_state(state)
        else:
            log(f"Startup run failed for {task['label']}; leaving it eligible for a retry on restart.")


def get_next_due_run(
    now: datetime,
    current_date: str,
    tasks: typing.List[TaskConfig],
    completed_runs: typing.Set[str],
    state: typing.Dict[str, typing.Any],
) -> typing.Optional[typing.Tuple[datetime, TaskConfig, str, int]]:
    next_item = None

    for task in tasks:
        if not task["enabled"]:
            continue
        for time_str in task["times"]:
            run_id = make_run_id(current_date, task["name"], time_str)
            if run_id in completed_runs:
                continue

            jitter = get_slot_jitter_minutes(state, run_id)
            due_time = get_target_time(time_str, current_date) + timedelta(minutes=jitter)
            candidate = (due_time, task, time_str, jitter)

            if next_item is None or candidate[0] < next_item[0]:
                next_item = candidate

    return next_item


def main():
    log("Facebook Marketing Orchestrator started.")

    accounts = load_accounts()
    log(f"Loaded {len(accounts)} account(s): {[a.id for a in accounts]}")

    tasks = build_tasks()
    state = prune_state(load_state(), datetime.now().strftime("%Y-%m-%d"))
    save_state(state)

    completed_runs: typing.Set[str] = set(state["completed_runs"])

    now_startup = datetime.now()
    current_date_startup = now_startup.strftime("%Y-%m-%d")
    skipped = prepopulate_passed_slots(now_startup, tasks, completed_runs, state)
    if skipped:
        log(f"Skipping {skipped} scheduled slot(s) whose due window already passed today.")

    run_startup_bootstrap(current_date_startup, tasks, state)

    state = prune_state(load_state(), current_date_startup)
    completed_runs = set(state["completed_runs"])

    announced_next_run_id = None

    while True:
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")

        state = prune_state(load_state(), current_date)
        completed_runs = set(state["completed_runs"])

        for task in tasks:
            if not task["enabled"]:
                continue
            for time_str in task["times"]:
                run_id = make_run_id(current_date, task["name"], time_str)
                if run_id in completed_runs:
                    continue

                jitter = get_slot_jitter_minutes(state, run_id)
                due_time = get_target_time(time_str, current_date) + timedelta(minutes=jitter)
                if now >= due_time:
                    log(
                        f"Due for {task['label']} run (scheduled {time_str}, {jitter}m jitter, "
                        f"due {due_time.strftime('%H:%M')})"
                    )
                    if task["runner"]():
                        mark_completed(completed_runs, state, run_id)
                        announced_next_run_id = None
                    else:
                        log(f"{task['label']} run failed; leaving slot pending for retry.")

        next_run = get_next_due_run(now, current_date, tasks, completed_runs, state)
        if next_run:
            due_time, task, time_str, jitter = next_run
            next_run_id = make_run_id(current_date, task["name"], time_str)
            if next_run_id != announced_next_run_id:
                log(
                    f"Next scheduled run: {task['label']} at {due_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"JST (slot {time_str}, {jitter}m jitter)."
                )
                announced_next_run_id = next_run_id
        else:
            if announced_next_run_id != "__done__":
                log("No scheduled runs remain for today. Waiting for tomorrow's schedule.")
                announced_next_run_id = "__done__"

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
