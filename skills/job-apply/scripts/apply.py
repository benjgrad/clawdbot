#!/usr/bin/env python3
"""
Job application automation script.

Takes a job posting URL, navigates to it, fills the application form,
uploads resume, solves CAPTCHAs, and saves all artifacts.

Usage:
    python apply.py <job_url> [--company <slug>] [--cover-letter <path>] [--dry-run]

Output: JSON with results, paths to saved artifacts, and status.
"""

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Add tools directory to path
TOOLS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from dotenv import load_dotenv

load_dotenv(TOOLS_DIR / ".env")

from pydantic import BaseModel
from browser_use import Agent, BrowserProfile, Controller, ActionResult

# Paths
WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
CAPTURES = WORKSPACE / "captures"
APPLICATIONS = CAPTURES / "applications"
RESUME_PATH = CAPTURES / "resume" / "Benjamin Grady - Senior Software Engineer.pdf"
TRACKER_PATH = APPLICATIONS / "tracker.md"

# Candidate info
CANDIDATE = {
    "name": "Benjamin Grady",
    "email": "bengrady4@gmail.com",
    "phone": "+1 (613) 217-7549",
    "location": "Toronto, Ontario, Canada",
    "title": "Senior Software Engineer",
}


def slugify(text: str) -> str:
    """Convert text to a directory-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:60].strip("-")


def guess_company_from_url(url: str) -> str:
    """Extract a company name guess from the URL domain."""
    domain = urlparse(url).netloc
    # Strip www. and common TLDs
    domain = re.sub(r"^www\.", "", domain)
    domain = re.sub(r"\.(com|org|net|io|co|careers|jobs|greenhouse\.io|lever\.co|workday\.com|myworkdayjobs\.com|smartrecruiters\.com|ashbyhq\.com|bamboohr\.com|icims\.com)$", "", domain)
    # Take the first meaningful part
    parts = domain.split(".")
    return slugify(parts[0]) if parts else "unknown"


def get_browser_profile(headless: bool = True, storage_state_path: str | None = None) -> BrowserProfile:
    return BrowserProfile(
        headless=headless,
        storage_state=storage_state_path,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
        disable_security=False,
    )


def get_llm():
    from browser_use import ChatAnthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return ChatAnthropic(model="claude-sonnet-4-20250514", api_key=api_key)


class _EmailCheckParams(BaseModel):
    sender_keyword: str = ""
    max_wait_seconds: int = 60


async def _check_email_for_code(sender_keyword: str = "", max_wait_seconds: int = 60) -> ActionResult:
    """Connect to Gmail via IMAP, find the most recent verification code email."""
    import email
    import email.utils
    import imaplib

    gmail_user = CANDIDATE["email"]
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD") or os.environ.get("EMAIL_PASSWORD")

    if not gmail_pass:
        return ActionResult(
            error="GMAIL_APP_PASSWORD not set. Cannot check email for verification codes.",
            success=False,
        )

    # Poll for the email (it may not arrive instantly)
    poll_interval = 5
    elapsed = 0
    code = None

    while elapsed < max_wait_seconds:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(gmail_user, gmail_pass)
            mail.select("INBOX")

            # Search for recent emails (last 10 minutes)
            search_criteria = "(UNSEEN)"
            if sender_keyword:
                search_criteria = f'(UNSEEN FROM "{sender_keyword}")'

            status, msg_ids = mail.search(None, search_criteria)
            if status != "OK" or not msg_ids[0]:
                mail.logout()
                if elapsed + poll_interval < max_wait_seconds:
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval
                    continue
                return ActionResult(
                    error=f"No verification emails found after {max_wait_seconds}s.",
                    success=False,
                )

            # Get the most recent matching email
            latest_id = msg_ids[0].split()[-1]
            status, msg_data = mail.fetch(latest_id, "(RFC822)")
            mail.logout()

            if status != "OK":
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            subject = str(msg.get("Subject", ""))

            # Extract body text
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode("utf-8", errors="replace")
                    elif ct == "text/html" and not body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode("utf-8", errors="replace")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")

            combined = f"{subject}\n{body}"

            # Try to extract verification code with common patterns
            # 4-8 digit numeric codes
            code = _extract_code(combined)
            if code:
                return ActionResult(
                    extracted_content=f"Verification code: {code} (from email: {subject})",
                    success=True,
                )

            # No code found in this email, keep the content for the agent
            return ActionResult(
                extracted_content=f"Email found but no obvious code extracted. Subject: {subject}\nBody excerpt: {body[:500]}",
                success=True,
            )

        except imaplib.IMAP4.error as e:
            return ActionResult(error=f"IMAP login failed: {e}. Check GMAIL_APP_PASSWORD.", success=False)
        except Exception as e:
            if elapsed + poll_interval < max_wait_seconds:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                continue
            return ActionResult(error=f"Email check failed: {e}", success=False)

    return ActionResult(error=f"No verification email found after {max_wait_seconds}s.", success=False)


def _extract_code(text: str) -> str | None:
    """Extract a verification code from email text using common patterns."""
    # Pattern 1: "code is 123456" / "code: 123456" / "verification code 123456"
    m = re.search(r"(?:verification|confirm|security|auth)\s*(?:code|number|pin)[:\s]+(\d{4,8})", text, re.IGNORECASE)
    if m:
        return m.group(1)

    # Pattern 2: "Your code is: 123456" / "Enter 123456"
    m = re.search(r"(?:your|the|enter)\s+(?:code|pin|otp)[:\s]+(\d{4,8})", text, re.IGNORECASE)
    if m:
        return m.group(1)

    # Pattern 3: "123456 is your verification code"
    m = re.search(r"(\d{4,8})\s+is\s+your\s+(?:verification|confirm|security)", text, re.IGNORECASE)
    if m:
        return m.group(1)

    # Pattern 4: Standalone prominent code (often in its own line or bold)
    m = re.search(r"(?:^|\n)\s*(\d{4,8})\s*(?:\n|$)", text)
    if m:
        return m.group(1)

    # Pattern 5: Alphanumeric codes like "AB12CD" (some systems use these)
    m = re.search(r"(?:code|pin|otp)[:\s]+([A-Z0-9]{4,10})", text, re.IGNORECASE)
    if m:
        return m.group(1)

    return None


def get_controller() -> Controller:
    """Controller with CAPTCHA solving and email verification."""
    controller = Controller()

    @controller.action(
        "Check email for a verification code. Use when the application sends a verification/confirmation code to email. "
        "Optionally provide a sender keyword to filter (e.g. 'greenhouse', 'workday'). "
        "Returns the code found in the most recent matching email.",
        param_model=_EmailCheckParams,
    )
    async def check_email_for_verification_code(params: _EmailCheckParams):
        return await _check_email_for_code(params.sender_keyword, params.max_wait_seconds)

    @controller.action("Solve a CAPTCHA on the current page using a paid solving service")
    async def solve_captcha_paid(browser_session):
        import time
        import requests

        capsolver_key = os.environ.get("CAPSOLVER_API_KEY")
        twocaptcha_key = os.environ.get("TWOCAPTCHA_API_KEY")

        if not capsolver_key and not twocaptcha_key:
            return ActionResult(
                error="No CAPTCHA solving API keys configured.",
                success=False,
            )

        page = await browser_session.get_current_page()
        current_url = page.url if page else "unknown"

        try:
            from cdp_use.cdp.runtime.commands import EvaluateParameters

            target = browser_session.session_manager.get_active_page_target()
            result = await target.cdp_client.send(
                EvaluateParameters(
                    expression="""
                    (function() {
                        var el = document.querySelector('.g-recaptcha');
                        if (el) return JSON.stringify({type: 'recaptcha_v2', sitekey: el.getAttribute('data-sitekey')});
                        var el2 = document.querySelector('[data-sitekey]');
                        if (el2) return JSON.stringify({type: 'recaptcha_v2', sitekey: el2.getAttribute('data-sitekey')});
                        var hc = document.querySelector('.h-captcha');
                        if (hc) return JSON.stringify({type: 'hcaptcha', sitekey: hc.getAttribute('data-sitekey')});
                        var cf = document.querySelector('.cf-turnstile');
                        if (cf) return JSON.stringify({type: 'turnstile', sitekey: cf.getAttribute('data-sitekey')});
                        return JSON.stringify({type: 'unknown', sitekey: null});
                    })()
                    """
                )
            )
            captcha_info = json.loads(result.result.value)
        except Exception as e:
            return ActionResult(error=f"Failed to detect CAPTCHA: {e}", success=False)

        if not captcha_info.get("sitekey"):
            return ActionResult(
                error="No CAPTCHA site key found. May need visual solving.",
                success=False,
            )

        captcha_type = captcha_info["type"]
        site_key = captcha_info["sitekey"]

        if capsolver_key:
            try:
                token = await _solve_with_capsolver(capsolver_key, captcha_type, site_key, current_url)
                if token:
                    await _inject_captcha_token(browser_session, captcha_type, token)
                    return ActionResult(
                        extracted_content=f"CAPTCHA solved via CapSolver ({captcha_type})",
                        success=True,
                    )
            except Exception as e:
                if not twocaptcha_key:
                    return ActionResult(error=f"CapSolver failed: {e}", success=False)

        if twocaptcha_key:
            try:
                from twocaptcha import TwoCaptcha
                solver = TwoCaptcha(twocaptcha_key)
                loop = asyncio.get_event_loop()
                if captcha_type == "recaptcha_v2":
                    result = await loop.run_in_executor(None, lambda: solver.recaptcha(sitekey=site_key, url=current_url))
                elif captcha_type == "hcaptcha":
                    result = await loop.run_in_executor(None, lambda: solver.hcaptcha(sitekey=site_key, url=current_url))
                elif captcha_type == "turnstile":
                    result = await loop.run_in_executor(None, lambda: solver.turnstile(sitekey=site_key, url=current_url))
                else:
                    return ActionResult(error=f"Unsupported type: {captcha_type}", success=False)
                token = result.get("code")
                if token:
                    await _inject_captcha_token(browser_session, captcha_type, token)
                    return ActionResult(
                        extracted_content=f"CAPTCHA solved via 2Captcha ({captcha_type})",
                        success=True,
                    )
            except Exception as e:
                return ActionResult(error=f"2Captcha failed: {e}", success=False)

        return ActionResult(error="All CAPTCHA methods failed", success=False)

    return controller


async def _solve_with_capsolver(api_key, captcha_type, site_key, page_url):
    import requests

    task_type_map = {
        "recaptcha_v2": "NoCaptchaTaskProxyless",
        "hcaptcha": "HCaptchaTaskProxyless",
        "turnstile": "AntiTurnstileTaskProxyless",
    }
    task_type = task_type_map.get(captcha_type)
    if not task_type:
        return None

    resp = requests.post(
        "https://api.capsolver.com/createTask",
        json={"clientKey": api_key, "task": {"type": task_type, "websiteURL": page_url, "websiteKey": site_key}},
        timeout=30,
    )
    data = resp.json()
    if data.get("errorId", 0) != 0:
        raise Exception(f"CapSolver error: {data.get('errorDescription')}")

    task_id = data["taskId"]
    for _ in range(60):
        await asyncio.sleep(3)
        result = requests.post(
            "https://api.capsolver.com/getTaskResult",
            json={"clientKey": api_key, "taskId": task_id},
            timeout=30,
        )
        rd = result.json()
        if rd.get("status") == "ready":
            solution = rd.get("solution", {})
            return solution.get("gRecaptchaResponse") or solution.get("token")
        if rd.get("errorId", 0) != 0:
            raise Exception(f"CapSolver error: {rd.get('errorDescription')}")
    raise Exception("CapSolver timeout")


async def _inject_captcha_token(browser_session, captcha_type, token):
    from cdp_use.cdp.runtime.commands import EvaluateParameters

    target = browser_session.session_manager.get_active_page_target()
    if captcha_type in ("recaptcha_v2",):
        js = f"""(function() {{
            var ta = document.getElementById('g-recaptcha-response');
            if (ta) {{ ta.style.display=''; ta.value='{token}'; }}
            if (typeof ___grecaptcha_cfg !== 'undefined') {{
                var c = ___grecaptcha_cfg.clients;
                if (c) for (var k in c) {{
                    var cl = c[k];
                    if (cl && cl.$ && cl.$.$ && typeof cl.$.$.callback === 'function') cl.$.$.callback('{token}');
                }}
            }}
        }})()"""
    elif captcha_type == "hcaptcha":
        js = f"""(function() {{
            var ta = document.querySelector('[name="h-captcha-response"]');
            if (ta) ta.value = '{token}';
        }})()"""
    elif captcha_type == "turnstile":
        js = f"""(function() {{
            var inp = document.querySelector('[name="cf-turnstile-response"]');
            if (inp) inp.value = '{token}';
        }})()"""
    else:
        return
    await target.cdp_client.send(EvaluateParameters(expression=js))


def build_task_prompt(url: str, cover_letter_path: str | None = None, dry_run: bool = False) -> str:
    """Build a detailed task prompt for the browser agent."""
    resume_note = f"Resume PDF to upload: {RESUME_PATH}" if RESUME_PATH.exists() else "No resume file found."

    cover_letter_note = ""
    if cover_letter_path and Path(cover_letter_path).exists():
        cover_letter_note = f"\nCover letter to upload if there is a field for it: {cover_letter_path}"

    submit_instruction = (
        "Do NOT submit the form. Stop just before the final submit button and report what you see."
        if dry_run
        else "Submit the application. If there is a final confirmation page, report what it says."
    )

    return f"""Apply for the job at: {url}

You are applying on behalf of Benjamin Grady, a Senior Software Engineer based in Toronto, Canada.

CANDIDATE INFORMATION:
- Full Name: Benjamin Grady
- Email: bengrady4@gmail.com
- Phone: +1 (613) 217-7549
- Location: Toronto, Ontario, Canada
- Current Title: Senior Software Engineer
- Experience: Fullstack development - React, .NET/C#, Golang, Python, Java
- Work Authorization: Canadian Citizen

INSTRUCTIONS:
1. Navigate to the job posting URL
2. Find and click the "Apply" button (or equivalent)
3. Fill in ALL required fields using the candidate information above
4. {resume_note}
5. Upload the resume when the form has a file upload field{cover_letter_note}
6. If there is a CAPTCHA, solve it using the solve_captcha_paid action
7. If the site sends a verification code to email, use the check_email_for_verification_code action to retrieve it, then enter the code
8. {submit_instruction}

IMPORTANT:
- If the application is through an external ATS (Greenhouse, Lever, Workday, etc.), follow the redirect
- If asked to create an account, do so with the email above
- If the site requires email verification, use the check_email_for_verification_code action. You can pass a sender_keyword like "greenhouse" or "workday" to filter. The action polls for up to 60 seconds.
- For any field you're unsure about, use reasonable defaults for a senior software engineer
- If a field requires information not provided, leave it blank or skip it
- Take note of any confirmation number or reference ID after submission

Report back:
- Company name and job title
- Whether the application was submitted successfully
- Any confirmation number or reference
- Any fields that couldn't be filled
- Any errors encountered"""


def build_resume_task_prompt(
    url: str,
    cover_letter_path: str | None = None,
    dry_run: bool = False,
    app_dir: Path | None = None,
) -> str:
    """Build a task prompt for resuming a previously started application."""
    previous_context = ""
    result_file = app_dir / "result.json" if app_dir else None
    if result_file and result_file.exists():
        try:
            prev = json.loads(result_file.read_text())
            agent_result = prev.get("agent_result", "")
            errors = [e for e in prev.get("errors", []) if e]
            status = prev.get("status", "unknown")
            previous_context = f"""
PREVIOUS ATTEMPT CONTEXT:
- Previous status: {status}
- Previous result: {agent_result[:500] if agent_result else 'No result recorded'}
- Errors from previous attempt: {'; '.join(errors) if errors else 'None'}
"""
        except Exception:
            pass

    resume_note = f"Resume PDF to upload: {RESUME_PATH}" if RESUME_PATH.exists() else "No resume file found."

    cover_letter_note = ""
    if cover_letter_path and Path(cover_letter_path).exists():
        cover_letter_note = f"\nCover letter to upload if there is a field for it: {cover_letter_path}"

    submit_instruction = (
        "Do NOT submit the form. Stop just before the final submit button and report what you see."
        if dry_run
        else "Submit the application. If there is a final confirmation page, report what it says."
    )

    return f"""RESUME a previously started job application at: {url}

IMPORTANT: You are RESUMING an application that was previously started but did not complete.
Your browser session has been restored with saved cookies and login state from the previous attempt.
You should already be logged into the ATS (Greenhouse, Lever, Workday, etc.) if an account was created.
{previous_context}
INSTRUCTIONS FOR RESUME:
1. Navigate to the job posting URL: {url}
2. Check if you are already logged in or if the application is partially filled
3. If the application form is already partially completed, continue from where it left off
4. If you need to re-enter the application, find and click the "Apply" button
5. Do NOT create a duplicate account -- check if you are already logged in first
6. If an email verification is pending, use check_email_for_verification_code to get the code
7. Fill in any remaining required fields using the candidate information below
8. {resume_note}
9. Upload the resume when the form has a file upload field{cover_letter_note}
10. If there is a CAPTCHA, solve it using the solve_captcha_paid action
11. {submit_instruction}

You are applying on behalf of Benjamin Grady, a Senior Software Engineer based in Toronto, Canada.

CANDIDATE INFORMATION:
- Full Name: Benjamin Grady
- Email: bengrady4@gmail.com
- Phone: +1 (613) 217-7549
- Location: Toronto, Ontario, Canada
- Current Title: Senior Software Engineer
- Experience: Fullstack development - React, .NET/C#, Golang, Python, Java
- Work Authorization: Canadian Citizen

IMPORTANT:
- If the previous attempt created an account, you should already be logged in via saved cookies
- If the site requires email verification, use the check_email_for_verification_code action
- For any field you're unsure about, use reasonable defaults for a senior software engineer
- If a field requires information not provided, leave it blank or skip it
- Take note of any confirmation number or reference ID after submission

Report back:
- Company name and job title
- Whether the application was submitted successfully
- Any confirmation number or reference
- Any fields that couldn't be filled
- Any errors encountered"""


async def run_application(
    url: str,
    company_slug: str | None = None,
    cover_letter_path: str | None = None,
    dry_run: bool = False,
    resume: bool = False,
) -> dict:
    """Run the full application flow and return results."""
    # Determine company slug
    if not company_slug:
        company_slug = guess_company_from_url(url)

    # Create output directory
    app_dir = APPLICATIONS / company_slug
    screenshots_dir = app_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Session persistence: always save to per-company storage_state.json
    storage_state_path = str(app_dir / "storage_state.json")

    # Auto-detect resume: if previous attempt failed and session state exists
    if not resume:
        prev_result_file = app_dir / "result.json"
        if prev_result_file.exists():
            try:
                prev = json.loads(prev_result_file.read_text())
                if prev.get("status") in ("failed", "error") and Path(storage_state_path).exists():
                    resume = True
                    print(f"Auto-resuming: previous attempt status was '{prev['status']}'")
            except Exception:
                pass

    timestamp = datetime.now().strftime("%Y-%m-%d")
    result_data = {
        "url": url,
        "company": company_slug,
        "date": timestamp,
        "status": "started",
        "app_dir": str(app_dir),
        "errors": [],
        "confirmation": None,
        "agent_result": None,
        "resumed": resume,
        "storage_state_path": storage_state_path,
    }

    # Build task prompt (resume-aware)
    if resume:
        task = build_resume_task_prompt(url, cover_letter_path, dry_run, app_dir)
    else:
        task = build_task_prompt(url, cover_letter_path, dry_run)

    # Save the task prompt for reference
    (app_dir / "task_prompt.txt").write_text(task)

    # Run the browser agent
    llm = get_llm()
    browser_profile = get_browser_profile(headless=True, storage_state_path=storage_state_path)
    controller = get_controller()

    conversation_path = app_dir / "conversation.json"
    gif_path = str(app_dir / "session.gif")

    agent = Agent(
        task=task,
        llm=llm,
        browser_profile=browser_profile,
        controller=controller,
        available_file_paths=[str(RESUME_PATH)],
        save_conversation_path=str(conversation_path),
        generate_gif=gif_path,
        use_vision=True,
        max_failures=5,
        max_actions_per_step=3,
    )

    try:
        history = await agent.run(max_steps=80)

        result_data["agent_result"] = history.final_result()
        result_data["is_successful"] = history.is_successful()
        result_data["steps"] = history.number_of_steps()
        result_data["errors"] = history.errors()
        result_data["urls_visited"] = history.urls()
        result_data["extracted_content"] = history.extracted_content()

        # Save screenshots
        saved_screenshots = []
        for i, path in enumerate(history.screenshot_paths()):
            if path and Path(path).exists():
                dest = screenshots_dir / f"step_{i:03d}.png"
                shutil.copy2(path, dest)
                saved_screenshots.append(str(dest))
        result_data["screenshots"] = saved_screenshots

        # Save history
        history.save_to_file(str(app_dir / "history.json"))

        if history.is_successful():
            result_data["status"] = "submitted" if not dry_run else "dry_run_complete"
        else:
            result_data["status"] = "failed"

    except Exception as e:
        result_data["status"] = "error"
        result_data["errors"].append(str(e))
    finally:
        # Always export browser state for future resume, regardless of outcome
        try:
            if hasattr(agent, 'browser_session') and agent.browser_session:
                await agent.browser_session.export_storage_state(storage_state_path)
        except Exception:
            pass  # Best-effort; StorageStateWatchdog may have already saved

    result_data["is_resumable"] = result_data["status"] in ("failed", "error")

    # Save result
    (app_dir / "result.json").write_text(json.dumps(result_data, indent=2, default=str))

    # Update tracker
    _update_tracker(result_data, dry_run)

    return result_data


def _update_tracker(result: dict, dry_run: bool):
    """Append to the application tracker."""
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)

    status = "Dry Run" if dry_run else result.get("status", "unknown").title()
    agent_result = result.get("agent_result", "No result")
    # Truncate long results
    if agent_result and len(agent_result) > 300:
        agent_result = agent_result[:300] + "..."

    entry = f"""
## {result['company']} - {result['date']}
- **URL:** {result['url']}
- **Status:** {status}
- **Steps:** {result.get('steps', 'N/A')}
- **Directory:** `{result['app_dir']}`
- **Result:** {agent_result}
"""

    with open(TRACKER_PATH, "a") as f:
        f.write(entry)


async def main():
    parser = argparse.ArgumentParser(description="Apply for a job automatically")
    parser.add_argument("url", help="Job posting URL")
    parser.add_argument("--company", help="Company slug for directory naming")
    parser.add_argument("--cover-letter", help="Path to cover letter PDF")
    parser.add_argument("--dry-run", action="store_true", help="Stop before submitting")
    parser.add_argument("--resume", action="store_true", help="Resume a previously started application using saved browser state")
    args = parser.parse_args()

    company = args.company or guess_company_from_url(args.url)
    state_file = APPLICATIONS / company / "storage_state.json"

    print(f"Starting application: {args.url}")
    print(f"Company: {company}")
    print(f"Dry run: {args.dry_run}")
    print(f"Resume flag: {args.resume}")
    print(f"Saved session: {'found' if state_file.exists() else 'none'}")
    print(f"Resume PDF: {RESUME_PATH}")
    print(f"CAPSOLVER_API_KEY: {'set' if os.environ.get('CAPSOLVER_API_KEY') else 'NOT SET'}")
    print(f"EMAIL_PASSWORD: {'set' if os.environ.get('GMAIL_APP_PASSWORD') or os.environ.get('EMAIL_PASSWORD') else 'NOT SET'}")
    print("---")

    result = await run_application(
        url=args.url,
        company_slug=args.company,
        cover_letter_path=args.cover_letter,
        dry_run=args.dry_run,
        resume=args.resume,
    )

    print("\n--- RESULT ---")
    print(json.dumps(result, indent=2, default=str))

    # Exit with appropriate code
    sys.exit(0 if result["status"] in ("submitted", "dry_run_complete") else 1)


if __name__ == "__main__":
    asyncio.run(main())
