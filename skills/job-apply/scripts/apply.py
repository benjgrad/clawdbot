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

from browser_use import Agent, Controller
from browser_utils import (
    get_llm,
    get_browser_profile,
    register_captcha_actions,
    register_email_verify_action,
)

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
    domain = re.sub(r"^www\.", "", domain)
    domain = re.sub(
        r"\.(com|org|net|io|co|careers|jobs|greenhouse\.io|lever\.co|workday\.com"
        r"|myworkdayjobs\.com|smartrecruiters\.com|ashbyhq\.com|bamboohr\.com|icims\.com)$",
        "",
        domain,
    )
    parts = domain.split(".")
    return slugify(parts[0]) if parts else "unknown"


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
- If the site requires email verification, use the check_email_for_verification_code action. You can pass a sender_keyword like "greenhouse" or "workday" to filter. The action spawns a background email checker and polls for up to 5 minutes. The user may also provide the code manually.
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
6. If an email verification is pending, use check_email_for_verification_code to get the code. This spawns a background email checker and polls for up to 5 minutes.
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
- If the site requires email verification, use the check_email_for_verification_code action. You can pass a sender_keyword like "greenhouse" or "workday" to filter. The action spawns a background email checker and polls for up to 5 minutes. The user may also provide the code manually.
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
    if not company_slug:
        company_slug = guess_company_from_url(url)

    app_dir = APPLICATIONS / company_slug
    screenshots_dir = app_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

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

    if resume:
        task = build_resume_task_prompt(url, cover_letter_path, dry_run, app_dir)
    else:
        task = build_task_prompt(url, cover_letter_path, dry_run)

    (app_dir / "task_prompt.txt").write_text(task)

    # Build controller with CAPTCHA + email verify actions
    controller = Controller()
    register_captcha_actions(controller)
    register_email_verify_action(controller, app_dir)

    llm = get_llm()
    browser_profile = get_browser_profile(
        headless=True, storage_state_path=storage_state_path
    )

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

        saved_screenshots = []
        for i, path in enumerate(history.screenshot_paths()):
            if path and Path(path).exists():
                dest = screenshots_dir / f"step_{i:03d}.png"
                shutil.copy2(path, dest)
                saved_screenshots.append(str(dest))
        result_data["screenshots"] = saved_screenshots

        history.save_to_file(str(app_dir / "history.json"))

        if history.is_successful():
            result_data["status"] = "submitted" if not dry_run else "dry_run_complete"
        else:
            result_data["status"] = "failed"

    except Exception as e:
        result_data["status"] = "error"
        result_data["errors"].append(str(e))
    finally:
        try:
            if hasattr(agent, "browser_session") and agent.browser_session:
                await agent.browser_session.export_storage_state(storage_state_path)
        except Exception:
            pass

    result_data["is_resumable"] = result_data["status"] in ("failed", "error")

    (app_dir / "result.json").write_text(json.dumps(result_data, indent=2, default=str))
    _update_tracker(result_data, dry_run)

    return result_data


def _update_tracker(result: dict, dry_run: bool):
    """Append to the application tracker."""
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)

    status = "Dry Run" if dry_run else result.get("status", "unknown").title()
    agent_result = result.get("agent_result", "No result")
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

    sys.exit(0 if result["status"] in ("submitted", "dry_run_complete") else 1)


if __name__ == "__main__":
    asyncio.run(main())
