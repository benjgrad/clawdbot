#!/usr/bin/env python3
"""
Standalone email verification code fetcher.

Polls Gmail IMAP for a verification code and writes it to a file.
Designed to run as a child process while the browser agent keeps the session alive.

Usage:
    python3 fetch_verification_code.py --app-dir /path/to/dir [--sender greenhouse] [--timeout 300]

Output:
    On success: writes code to <app_dir>/verification_code.txt
    On failure: writes error to <app_dir>/verification_error.txt
"""

import argparse
import email
import email.utils
import imaplib
import os
import re
import sys
import time
from pathlib import Path

# Load env from tools/.env
TOOLS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))
try:
    from dotenv import load_dotenv
    load_dotenv(TOOLS_DIR / ".env")
except ImportError:
    pass


def extract_code(text: str) -> str | None:
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

    # Pattern 6: 8-character alphanumeric on its own line (Greenhouse style)
    m = re.search(r"(?:^|\n)\s*([A-Za-z0-9]{8})\s*(?:\n|$)", text)
    if m:
        return m.group(1)

    return None


def check_imap(gmail_user: str, gmail_pass: str, sender_keyword: str = "") -> tuple[str | None, str | None]:
    """Single IMAP check. Returns (code, error)."""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(gmail_user, gmail_pass)
        mail.select("INBOX")

        search_criteria = "(UNSEEN)"
        if sender_keyword:
            search_criteria = f'(UNSEEN FROM "{sender_keyword}")'

        status, msg_ids = mail.search(None, search_criteria)
        if status != "OK" or not msg_ids[0]:
            mail.logout()
            return None, None  # No emails yet, not an error

        # Get the most recent matching email
        latest_id = msg_ids[0].split()[-1]
        status, msg_data = mail.fetch(latest_id, "(RFC822)")
        mail.logout()

        if status != "OK":
            return None, None

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
        code = extract_code(combined)

        if code:
            return code, None
        else:
            return None, f"Email found but no code extracted. Subject: {subject}"

    except imaplib.IMAP4.error as e:
        return None, f"IMAP error: {e}"
    except Exception as e:
        return None, f"Error: {e}"


def main():
    parser = argparse.ArgumentParser(description="Fetch email verification code")
    parser.add_argument("--app-dir", required=True, help="Application directory for output files")
    parser.add_argument("--sender", default="", help="Sender keyword filter (e.g. 'greenhouse')")
    parser.add_argument("--timeout", type=int, default=300, help="Max seconds to poll (default 300)")
    args = parser.parse_args()

    app_dir = Path(args.app_dir)
    code_file = app_dir / "verification_code.txt"
    error_file = app_dir / "verification_error.txt"

    gmail_user = os.environ.get("EMAIL_ADDRESS", "bengrady4@gmail.com")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD") or os.environ.get("EMAIL_PASSWORD")

    if not gmail_pass:
        error_file.write_text("GMAIL_APP_PASSWORD not set. Cannot check email.")
        sys.exit(1)

    poll_interval = 5
    elapsed = 0
    last_error = None

    print(f"Polling IMAP for verification code (timeout={args.timeout}s, sender={args.sender or 'any'})")

    while elapsed < args.timeout:
        code, err = check_imap(gmail_user, gmail_pass, args.sender)

        if code:
            code_file.write_text(code)
            print(f"Found verification code: {code}")
            sys.exit(0)

        if err:
            last_error = err
            print(f"[{elapsed}s] {err}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    # Timeout
    msg = f"No verification code found after {args.timeout}s."
    if last_error:
        msg += f" Last error: {last_error}"
    error_file.write_text(msg)
    print(msg)
    sys.exit(1)


if __name__ == "__main__":
    main()
