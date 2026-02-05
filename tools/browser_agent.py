"""
Browser automation agent for clawdbot (one-shot mode).

Uses browser-use to autonomously navigate websites, fill forms, and solve CAPTCHAs.
Runs headless on Ubuntu server with anti-detection configuration.

Usage:
    # As a module
    from browser_agent import run_browser_task
    result = await run_browser_task("Go to example.com and get the page title")

    # CLI
    python browser_agent.py "Go to example.com and return the page title"
"""

import asyncio
import logging
import os
import sys

# Suppress verbose browser-use and httpx INFO logs
logging.getLogger("browser_use").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from browser_use import Agent, Controller
from browser_utils import get_llm, get_browser_profile, register_captcha_actions


async def run_browser_task(
    task: str,
    max_steps: int = 50,
    headless: bool = True,
    sensitive_data: dict | None = None,
) -> str:
    """
    Run a one-shot browser automation task using an AI agent.

    Args:
        task: Natural language description of what to do.
        max_steps: Maximum number of agent steps before stopping.
        headless: Run browser without visible window (default True).
        sensitive_data: Dict of placeholder->value mappings for sensitive data.

    Returns:
        The agent's final response as a string.
    """
    controller = Controller()
    register_captcha_actions(controller)

    agent = Agent(
        task=task,
        llm=get_llm(),
        browser_profile=get_browser_profile(headless=headless),
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
