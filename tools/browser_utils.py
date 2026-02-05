"""
Shared browser automation utilities for clawdbot.

Provides common functions used by both browser_agent.py (one-shot) and
browse_session.py (interactive), and the job-apply skill's apply.py.

Functions:
    get_llm()                        - Create a ChatAnthropic LLM instance
    get_browser_profile()            - Create a BrowserProfile with anti-detection args
    register_captcha_actions()       - Add CAPTCHA-solving actions to a Controller
    register_email_verify_action()   - Add email verification action to a Controller
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from browser_use import ActionResult, BrowserProfile, Controller

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

def get_llm(model: str = "claude-sonnet-4-20250514"):
    """Get a ChatAnthropic instance for the browser agent's LLM."""
    from browser_use import ChatAnthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Add it to tools/.env or export it."
        )
    return ChatAnthropic(model=model, api_key=api_key)


# ---------------------------------------------------------------------------
# Browser Profile
# ---------------------------------------------------------------------------

def get_browser_profile(
    headless: bool = True,
    storage_state_path: str | None = None,
    keep_alive: bool = False,
) -> BrowserProfile:
    """Create a BrowserProfile configured for headless server with anti-detection."""
    return BrowserProfile(
        headless=headless,
        storage_state=storage_state_path,
        keep_alive=keep_alive,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
        disable_security=False,
    )


# ---------------------------------------------------------------------------
# CAPTCHA solving internals
# ---------------------------------------------------------------------------

async def _solve_with_capsolver(
    api_key: str, captcha_type: str, site_key: str, page_url: str
) -> str | None:
    """Submit CAPTCHA to CapSolver and return the solution token."""
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
        json={
            "clientKey": api_key,
            "task": {
                "type": task_type,
                "websiteURL": page_url,
                "websiteKey": site_key,
            },
        },
        timeout=30,
    )
    data = resp.json()
    if data.get("errorId", 0) != 0:
        raise Exception(f"CapSolver createTask error: {data.get('errorDescription')}")

    task_id = data["taskId"]

    for _ in range(60):
        await asyncio.sleep(3)
        result = requests.post(
            "https://api.capsolver.com/getTaskResult",
            json={"clientKey": api_key, "taskId": task_id},
            timeout=30,
        )
        result_data = result.json()
        if result_data.get("status") == "ready":
            solution = result_data.get("solution", {})
            return solution.get("gRecaptchaResponse") or solution.get("token")
        if result_data.get("errorId", 0) != 0:
            raise Exception(
                f"CapSolver error: {result_data.get('errorDescription')}"
            )

    raise Exception("CapSolver timeout after 3 minutes")


async def _solve_with_2captcha(
    api_key: str, captcha_type: str, site_key: str, page_url: str
) -> str | None:
    """Submit CAPTCHA to 2Captcha and return the solution token."""
    from twocaptcha import TwoCaptcha

    solver = TwoCaptcha(api_key)
    loop = asyncio.get_event_loop()

    if captcha_type == "recaptcha_v2":
        result = await loop.run_in_executor(
            None, lambda: solver.recaptcha(sitekey=site_key, url=page_url)
        )
    elif captcha_type == "hcaptcha":
        result = await loop.run_in_executor(
            None, lambda: solver.hcaptcha(sitekey=site_key, url=page_url)
        )
    elif captcha_type == "turnstile":
        result = await loop.run_in_executor(
            None, lambda: solver.turnstile(sitekey=site_key, url=page_url)
        )
    else:
        return None

    return result.get("code")


async def _inject_captcha_token(browser_session, captcha_type: str, token: str):
    """Inject the CAPTCHA solution token into the page."""
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
            var iframe = document.querySelector('iframe[src*="hcaptcha"]');
            if (iframe) iframe.setAttribute('data-hcaptcha-response', '{token}');
        }})()"""
    elif captcha_type == "turnstile":
        js = f"""(function() {{
            var inp = document.querySelector('[name="cf-turnstile-response"]');
            if (inp) inp.value = '{token}';
            if (typeof turnstile !== 'undefined' && turnstile.getResponse) {{
                var widgets = document.querySelectorAll('.cf-turnstile');
                widgets.forEach(function(w) {{
                    var cb = w.getAttribute('data-callback');
                    if (cb && typeof window[cb] === 'function') window[cb]('{token}');
                }});
            }}
        }})()"""
    else:
        return

    await target.cdp_client.send(EvaluateParameters(expression=js))


_DETECT_CAPTCHA_JS = """
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


# ---------------------------------------------------------------------------
# Controller action registrations
# ---------------------------------------------------------------------------

def register_captcha_actions(controller: Controller) -> None:
    """Register the ``solve_captcha_paid`` action on *controller*."""

    @controller.action(
        "Solve a CAPTCHA on the current page using a paid solving service"
    )
    async def solve_captcha_paid(browser_session):
        from cdp_use.cdp.runtime.commands import EvaluateParameters

        capsolver_key = os.environ.get("CAPSOLVER_API_KEY")
        twocaptcha_key = os.environ.get("TWOCAPTCHA_API_KEY")

        if not capsolver_key and not twocaptcha_key:
            return ActionResult(
                error="No CAPTCHA solving API keys configured. "
                      "Set CAPSOLVER_API_KEY or TWOCAPTCHA_API_KEY.",
                success=False,
            )

        page = await browser_session.get_current_page()
        current_url = page.url if page else "unknown"

        try:
            target = browser_session.session_manager.get_active_page_target()
            result = await target.cdp_client.send(
                EvaluateParameters(expression=_DETECT_CAPTCHA_JS)
            )
            captcha_info = json.loads(result.result.value)
        except Exception as e:
            return ActionResult(
                error=f"Failed to detect CAPTCHA type: {e}", success=False
            )

        if not captcha_info.get("sitekey"):
            return ActionResult(
                error="No CAPTCHA site key found. May need visual solving.",
                success=False,
            )

        captcha_type = captcha_info["type"]
        site_key = captcha_info["sitekey"]

        if capsolver_key:
            try:
                token = await _solve_with_capsolver(
                    capsolver_key, captcha_type, site_key, current_url
                )
                if token:
                    await _inject_captcha_token(
                        browser_session, captcha_type, token
                    )
                    return ActionResult(
                        extracted_content=f"CAPTCHA solved via CapSolver ({captcha_type})",
                        success=True,
                    )
            except Exception as e:
                if not twocaptcha_key:
                    return ActionResult(
                        error=f"CapSolver failed: {e}", success=False
                    )

        if twocaptcha_key:
            try:
                token = await _solve_with_2captcha(
                    twocaptcha_key, captcha_type, site_key, current_url
                )
                if token:
                    await _inject_captcha_token(
                        browser_session, captcha_type, token
                    )
                    return ActionResult(
                        extracted_content=f"CAPTCHA solved via 2Captcha ({captcha_type})",
                        success=True,
                    )
            except Exception as e:
                return ActionResult(
                    error=f"2Captcha failed: {e}", success=False
                )

        return ActionResult(error="All CAPTCHA solving methods failed", success=False)


def register_email_verify_action(
    controller: Controller,
    app_dir: Path,
    fetch_script: Path | None = None,
) -> None:
    """Register the ``check_email_for_verification_code`` action on *controller*.

    *fetch_script* defaults to ``skills/job-apply/scripts/fetch_verification_code.py``
    relative to the workspace root (four levels up from tools/).
    """
    from pydantic import BaseModel

    if fetch_script is None:
        workspace = Path(__file__).resolve().parent.parent
        fetch_script = (
            workspace / "skills" / "job-apply" / "scripts" / "fetch_verification_code.py"
        )

    class _EmailCheckParams(BaseModel):
        sender_keyword: str = ""
        max_wait_seconds: int = 300

    @controller.action(
        "Check email for a verification code. Use when the site sends a "
        "verification/confirmation code to email. Optionally provide a "
        "sender keyword to filter (e.g. 'greenhouse', 'workday'). "
        "Spawns a background process to poll IMAP for up to 5 minutes. "
        "The user can also manually provide the code by writing it to the "
        "verification_code.txt file.",
        param_model=_EmailCheckParams,
    )
    async def check_email_for_verification_code(params: _EmailCheckParams):
        return await _check_email_for_code(
            app_dir, fetch_script, params.sender_keyword, params.max_wait_seconds
        )


async def _check_email_for_code(
    app_dir: Path,
    fetch_script: Path,
    sender_keyword: str = "",
    max_wait_seconds: int = 300,
) -> ActionResult:
    """Spawn a child process to poll IMAP, then poll for the result file."""
    code_file = app_dir / "verification_code.txt"
    error_file = app_dir / "verification_error.txt"

    for f in (code_file, error_file):
        if f.exists():
            f.unlink()

    python = sys.executable
    cmd = [
        python,
        str(fetch_script),
        "--app-dir", str(app_dir),
        "--sender", sender_keyword,
        "--timeout", str(max_wait_seconds),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        return ActionResult(error=f"Failed to spawn email checker: {e}", success=False)

    poll_interval = 5
    elapsed = 0

    while elapsed < max_wait_seconds:
        if code_file.exists():
            code = code_file.read_text().strip()
            if code:
                if proc.returncode is None:
                    proc.kill()
                return ActionResult(
                    extracted_content=f"Verification code: {code}",
                    success=True,
                )

        if error_file.exists() and proc.returncode is not None:
            err = error_file.read_text().strip()
            return ActionResult(error=f"Email check failed: {err}", success=False)

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    if proc.returncode is None:
        proc.kill()

    return ActionResult(
        error=f"No verification code found after {max_wait_seconds}s. "
              f"You can also manually write the code to: {code_file}",
        success=False,
    )
