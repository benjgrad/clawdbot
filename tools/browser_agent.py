"""
Browser automation agent for clawdbot.

Uses browser-use to autonomously navigate websites, fill forms, and solve CAPTCHAs.
Runs headless on Ubuntu server with anti-detection configuration.

Usage:
    # As a module
    from browser_agent import run_browser_task
    result = await run_browser_task("Go to example.com and get the page title")

    # CLI test
    python browser_agent.py "Go to example.com and return the page title"
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Load API keys from .env in the same directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from browser_use import Agent, BrowserProfile, Controller, ActionResult


def _get_browser_profile(headless: bool = True) -> BrowserProfile:
    """Create a browser profile configured for headless server with anti-detection."""
    return BrowserProfile(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
        disable_security=False,
    )


def _get_llm():
    """Get the LLM instance for the browser agent."""
    from browser_use import ChatAnthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Add it to tools/.env or export it."
        )
    return ChatAnthropic(model="claude-sonnet-4-20250514", api_key=api_key)


def _get_controller() -> Controller:
    """Create a controller with CAPTCHA-solving actions."""
    controller = Controller()

    @controller.action("Solve a CAPTCHA on the current page using a paid solving service")
    async def solve_captcha_paid(browser_session):
        """
        Attempts to solve reCAPTCHA/hCaptcha using CapSolver or 2Captcha API.
        Extracts the site key from the page, submits to the solving service,
        and injects the solution token.
        """
        import json
        import time

        import requests

        capsolver_key = os.environ.get("CAPSOLVER_API_KEY")
        twocaptcha_key = os.environ.get("TWOCAPTCHA_API_KEY")

        if not capsolver_key and not twocaptcha_key:
            return ActionResult(
                error="No CAPTCHA solving API keys configured. Set CAPSOLVER_API_KEY or TWOCAPTCHA_API_KEY in tools/.env",
                success=False,
            )

        # Get current page info via CDP
        page = await browser_session.get_current_page()
        current_url = page.url if page else "unknown"

        # Try to find reCAPTCHA site key
        try:
            from cdp_use.cdp.runtime.commands import EvaluateParameters

            target = browser_session.session_manager.get_active_page_target()
            result = await target.cdp_client.send(
                EvaluateParameters(
                    expression="""
                    (function() {
                        // reCAPTCHA v2
                        var el = document.querySelector('.g-recaptcha');
                        if (el) return JSON.stringify({type: 'recaptcha_v2', sitekey: el.getAttribute('data-sitekey')});

                        // reCAPTCHA v2 invisible
                        var el2 = document.querySelector('[data-sitekey]');
                        if (el2) return JSON.stringify({type: 'recaptcha_v2', sitekey: el2.getAttribute('data-sitekey')});

                        // hCaptcha
                        var hc = document.querySelector('.h-captcha');
                        if (hc) return JSON.stringify({type: 'hcaptcha', sitekey: hc.getAttribute('data-sitekey')});

                        // Cloudflare Turnstile
                        var cf = document.querySelector('.cf-turnstile');
                        if (cf) return JSON.stringify({type: 'turnstile', sitekey: cf.getAttribute('data-sitekey')});

                        return JSON.stringify({type: 'unknown', sitekey: null});
                    })()
                    """
                )
            )
            captcha_info = json.loads(result.result.value)
        except Exception as e:
            return ActionResult(
                error=f"Failed to detect CAPTCHA type: {e}",
                success=False,
            )

        if not captcha_info.get("sitekey"):
            return ActionResult(
                error="Could not find a CAPTCHA site key on this page. The CAPTCHA may need to be solved visually by the AI agent instead.",
                success=False,
            )

        captcha_type = captcha_info["type"]
        site_key = captcha_info["sitekey"]

        # Try CapSolver first
        if capsolver_key:
            try:
                token = await _solve_with_capsolver(
                    capsolver_key, captcha_type, site_key, current_url
                )
                if token:
                    await _inject_captcha_token(browser_session, captcha_type, token)
                    return ActionResult(
                        extracted_content=f"CAPTCHA solved via CapSolver ({captcha_type})",
                        success=True,
                    )
            except Exception as e:
                if not twocaptcha_key:
                    return ActionResult(error=f"CapSolver failed: {e}", success=False)

        # Fall back to 2Captcha
        if twocaptcha_key:
            try:
                token = await _solve_with_2captcha(
                    twocaptcha_key, captcha_type, site_key, current_url
                )
                if token:
                    await _inject_captcha_token(browser_session, captcha_type, token)
                    return ActionResult(
                        extracted_content=f"CAPTCHA solved via 2Captcha ({captcha_type})",
                        success=True,
                    )
            except Exception as e:
                return ActionResult(error=f"2Captcha failed: {e}", success=False)

        return ActionResult(error="All CAPTCHA solving methods failed", success=False)

    return controller


async def _solve_with_capsolver(api_key: str, captcha_type: str, site_key: str, page_url: str) -> str | None:
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

    # Create task
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

    # Poll for result
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
            raise Exception(f"CapSolver error: {result_data.get('errorDescription')}")

    raise Exception("CapSolver timeout after 3 minutes")


async def _solve_with_2captcha(api_key: str, captcha_type: str, site_key: str, page_url: str) -> str | None:
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
        await target.cdp_client.send(
            EvaluateParameters(
                expression=f"""
                (function() {{
                    var textarea = document.getElementById('g-recaptcha-response');
                    if (textarea) {{
                        textarea.style.display = '';
                        textarea.value = '{token}';
                    }}
                    // Also try invisible reCAPTCHA callback
                    if (typeof ___grecaptcha_cfg !== 'undefined') {{
                        var clients = ___grecaptcha_cfg.clients;
                        if (clients) {{
                            for (var key in clients) {{
                                var client = clients[key];
                                if (client && client.$ && client.$.$ && typeof client.$.$.callback === 'function') {{
                                    client.$.$.callback('{token}');
                                }}
                            }}
                        }}
                    }}
                }})()
                """
            )
        )
    elif captcha_type == "hcaptcha":
        await target.cdp_client.send(
            EvaluateParameters(
                expression=f"""
                (function() {{
                    var textarea = document.querySelector('[name="h-captcha-response"]');
                    if (textarea) textarea.value = '{token}';
                    var iframe = document.querySelector('iframe[src*="hcaptcha"]');
                    if (iframe) {{
                        iframe.setAttribute('data-hcaptcha-response', '{token}');
                    }}
                }})()
                """
            )
        )
    elif captcha_type == "turnstile":
        await target.cdp_client.send(
            EvaluateParameters(
                expression=f"""
                (function() {{
                    var input = document.querySelector('[name="cf-turnstile-response"]');
                    if (input) input.value = '{token}';
                    if (typeof turnstile !== 'undefined' && turnstile.getResponse) {{
                        // Trigger callback
                        var widgets = document.querySelectorAll('.cf-turnstile');
                        widgets.forEach(function(w) {{
                            var cb = w.getAttribute('data-callback');
                            if (cb && typeof window[cb] === 'function') window[cb]('{token}');
                        }});
                    }}
                }})()
                """
            )
        )


async def run_browser_task(
    task: str,
    max_steps: int = 50,
    headless: bool = True,
    sensitive_data: dict | None = None,
) -> str:
    """
    Run a browser automation task using an AI agent.

    Args:
        task: Natural language description of what to do.
        max_steps: Maximum number of agent steps before stopping.
        headless: Run browser without visible window (default True).
        sensitive_data: Dict of placeholder->value mappings for sensitive data
                       (e.g. {"password": "secret123"}). The agent will see
                       placeholders, and browser-use substitutes real values.

    Returns:
        The agent's final response as a string.
    """
    llm = _get_llm()
    browser_profile = _get_browser_profile(headless=headless)
    controller = _get_controller()

    agent = Agent(
        task=task,
        llm=llm,
        browser_profile=browser_profile,
        controller=controller,
        sensitive_data=sensitive_data,
        use_vision=True,
        max_failures=3,
    )

    history = await agent.run(max_steps=max_steps)
    result = history.final_result()
    return result if result else "Task completed (no explicit result returned)"


async def main():
    if len(sys.argv) < 2:
        print("Usage: python browser_agent.py <task>")
        print('Example: python browser_agent.py "Go to example.com and return the page title"')
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    print(f"Running task: {task}")
    result = await run_browser_task(task)
    print(f"\nResult: {result}")


if __name__ == "__main__":
    asyncio.run(main())
