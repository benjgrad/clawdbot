#!/usr/bin/env python3
"""
Persistent browser session daemon with file-based IPC.

Keeps a browser alive across multiple tasks. Clawdbot writes follow-up
instructions to ``next_task.json``; this daemon picks them up, runs a new
Agent on the same BrowserSession, and outputs results.

Usage:
    python browse_session.py --task "Go to github.com" [--session-id abc] [--timeout 600] [--max-lifetime 1800]

Stdout protocol (line-buffered, read by clawdbot):
    SESSION_ID:<id>
    SCREENSHOT:<path>
    RESULT:{"output":"...","error":null}
    WAITING
    MAX_LIFETIME_REACHED
"""

import argparse
import asyncio
import atexit
import json
import logging
import os
import signal
import sys
import time
import uuid
from pathlib import Path

# Suppress verbose browser-use and httpx INFO logs (they leak to stderr
# and can bloat clawdbot session context if captured).
logging.getLogger("browser_use").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Add tools directory to path
TOOLS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from dotenv import load_dotenv

load_dotenv(TOOLS_DIR / ".env")

from browser_use import Agent, BrowserSession, Controller
from browser_utils import (
    get_llm,
    get_browser_profile,
    register_captcha_actions,
    register_email_verify_action,
)

WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
SESSIONS_DIR = WORKSPACE / "captures" / "browser-sessions"


# ---------------------------------------------------------------------------
# Session safety helpers
# ---------------------------------------------------------------------------

def _pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is alive."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _reap_stale_sessions(base_dir: Path):
    """Mark sessions with dead PIDs as closed."""
    if not base_dir.exists():
        return
    for status_file in base_dir.glob("*/status.json"):
        try:
            status = json.loads(status_file.read_text())
        except Exception:
            continue
        if status.get("state") in ("running", "idle"):
            pid = status.get("pid")
            if pid and not _pid_alive(pid):
                status["state"] = "closed"
                status["closed_at"] = time.time()
                status["close_reason"] = "stale_reaper"
                status_file.write_text(json.dumps(status, indent=2))


def _cap_screenshots(screenshots_dir: Path, max_count: int = 20):
    """Keep only the most recent *max_count* screenshots."""
    if not screenshots_dir.exists():
        return
    files = sorted(screenshots_dir.glob("*.png"), key=lambda f: f.stat().st_mtime)
    while len(files) > max_count:
        files.pop(0).unlink()


async def _browser_is_alive(session: BrowserSession) -> bool:
    """Ping the browser via CDP to check if it's still responsive."""
    try:
        page = await session.get_current_page()
        if page:
            await page.evaluate("() => 1 + 1")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main daemon
# ---------------------------------------------------------------------------

async def run_session(
    initial_task: str,
    session_id: str | None = None,
    idle_timeout: int = 600,
    max_lifetime: int = 1800,
):
    session_id = session_id or uuid.uuid4().hex[:8]
    session_dir = SESSIONS_DIR / session_id
    screenshots_dir = session_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    status_file = session_dir / "status.json"
    next_task_file = session_dir / "next_task.json"
    result_file = session_dir / "result.json"
    screenshot_file = session_dir / "screenshot.png"
    storage_state_file = session_dir / "storage_state.json"

    session_start = time.time()
    browser_session: BrowserSession | None = None

    def _write_status(state: str, **extra):
        data = {
            "state": state,
            "pid": os.getpid(),
            "session_id": session_id,
            "started_at": session_start,
            "updated_at": time.time(),
            **extra,
        }
        status_file.write_text(json.dumps(data, indent=2))

    def _cleanup():
        """Best-effort cleanup on exit."""
        try:
            if browser_session:
                # Can't await in atexit, but BrowserSession.kill() is sync-safe
                # for the underlying process.
                import asyncio as _aio
                try:
                    loop = _aio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(browser_session.kill())
                    else:
                        loop.run_until_complete(browser_session.kill())
                except Exception:
                    pass
        except Exception:
            pass
        _write_status("closed", close_reason="cleanup")

    atexit.register(_cleanup)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    # Reap stale sessions from previous runs
    _reap_stale_sessions(SESSIONS_DIR)

    # Create browser profile with keep_alive=True so Agent.close() doesn't kill it
    profile = get_browser_profile(headless=True, keep_alive=True)

    # Start a BrowserSession that persists across tasks
    browser_session = BrowserSession(browser_profile=profile)
    await browser_session.start()

    _write_status("running")

    # Print session ID immediately
    print(f"SESSION_ID:{session_id}", flush=True)

    # --- Helper to run a single task on the persistent session ---
    async def _run_task(task_text: str) -> dict:
        _write_status("running")

        controller = Controller()
        register_captcha_actions(controller)
        register_email_verify_action(controller, session_dir)

        agent = Agent(
            task=task_text,
            llm=get_llm(),
            browser_session=browser_session,
            controller=controller,
            use_vision=True,
            max_failures=3,
        )

        history = await agent.run(max_steps=50)

        # Agent.close() with keep_alive=True preserves the browser process
        # but clears CDP session state.  Re-call start() to reconnect.
        await browser_session.start()

        output = history.final_result() or "Task completed (no explicit result)"
        errors = history.errors()

        # Save screenshot
        ss_paths = history.screenshot_paths()
        if ss_paths:
            last_ss = ss_paths[-1]
            if last_ss and Path(last_ss).exists():
                import shutil
                shutil.copy2(last_ss, screenshot_file)
                # Also archive into screenshots/ with timestamp
                ts = int(time.time())
                shutil.copy2(last_ss, screenshots_dir / f"{ts}.png")
                _cap_screenshots(screenshots_dir)

        result = {"output": output, "errors": errors}
        result_file.write_text(json.dumps(result, indent=2))
        return result

    # --- Run initial task ---
    try:
        result = await _run_task(initial_task)
    except Exception as e:
        result = {"output": None, "errors": [str(e)]}
        result_file.write_text(json.dumps(result, indent=2))

    print(f"SCREENSHOT:{screenshot_file}", flush=True)
    print(f"RESULT:{json.dumps(result)}", flush=True)
    print("WAITING", flush=True)

    # --- Poll loop for follow-up tasks ---
    poll_interval = 2
    heartbeat_interval = 5  # check every 5th cycle (~10s)
    poll_count = 0
    last_activity = time.time()

    while True:
        poll_count += 1

        # Max lifetime check
        if time.time() - session_start > max_lifetime:
            print("MAX_LIFETIME_REACHED", flush=True)
            break

        # Idle timeout check
        if time.time() - last_activity > idle_timeout:
            break

        # CDP heartbeat check (every ~10s)
        if poll_count % heartbeat_interval == 0:
            if not await _browser_is_alive(browser_session):
                print("RESULT:{\"output\":null,\"errors\":[\"Browser process died\"]}", flush=True)
                break

        # Check for next task
        if next_task_file.exists():
            try:
                task_data = json.loads(next_task_file.read_text())
                next_task_file.unlink()
            except Exception:
                await asyncio.sleep(poll_interval)
                continue

            instruction = task_data.get("instruction", "")

            if instruction.lower().strip() == "close":
                break

            last_activity = time.time()

            try:
                result = await _run_task(instruction)
            except Exception as e:
                result = {"output": None, "errors": [str(e)]}
                result_file.write_text(json.dumps(result, indent=2))

            print(f"SCREENSHOT:{screenshot_file}", flush=True)
            print(f"RESULT:{json.dumps(result)}", flush=True)
            print("WAITING", flush=True)

        await asyncio.sleep(poll_interval)

    # --- Shutdown ---
    try:
        await browser_session.export_storage_state(str(storage_state_file))
    except Exception:
        pass

    try:
        await browser_session.kill()
    except Exception:
        pass

    # Mark browser_session as None so atexit cleanup doesn't double-kill
    browser_session = None
    _write_status("closed", close_reason="normal")


async def main():
    parser = argparse.ArgumentParser(description="Persistent browser session daemon")
    parser.add_argument("--task", required=True, help="Initial task to run")
    parser.add_argument("--session-id", default=None, help="Session ID (auto-generated if omitted)")
    parser.add_argument("--timeout", type=int, default=600, help="Idle timeout in seconds (default 600)")
    parser.add_argument("--max-lifetime", type=int, default=1800, help="Max session lifetime in seconds (default 1800)")
    args = parser.parse_args()

    await run_session(
        initial_task=args.task,
        session_id=args.session_id,
        idle_timeout=args.timeout,
        max_lifetime=args.max_lifetime,
    )


if __name__ == "__main__":
    asyncio.run(main())
