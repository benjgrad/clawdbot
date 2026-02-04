---
name: browser
description: Run autonomous browser tasks with AI and CAPTCHA solving via browser_agent.py. Use when the built-in browser tool is insufficient — complex multi-step flows, CAPTCHA-protected pages, or tasks needing autonomous AI navigation. For job applications, prefer the job-apply skill.
metadata: {"moltbot":{"os":["linux"],"requires":{"bins":["python3"],"env":["ANTHROPIC_API_KEY"]}}}
---

# Browser Automation (browser-use agent)

AI-powered autonomous browser agent. Use this when the built-in `browser` tool can't handle the task (CAPTCHAs, complex flows, multi-step autonomous navigation).

**For job applications, use the `job-apply` skill instead** — it handles the full workflow including document capture.

## When to Use This Skill

- Page has a CAPTCHA (reCAPTCHA, hCaptcha, Turnstile)
- Complex multi-step flow that needs AI judgment
- Need to log into a service
- The built-in `browser` tool's snapshot/act cycle is too tedious for the task

## When to Use the Built-in `browser` Tool Instead

- Reading a page, taking screenshots
- Simple form filling (no CAPTCHA)
- Navigating known page structures step by step

## Run a Browser Task

```bash
{baseDir}/../tools/.venv/bin/python {baseDir}/../tools/browser_agent.py "task description here"
```

## CAPTCHA Solving

The agent has a built-in `solve_captcha_paid` action that:
1. Auto-detects CAPTCHA type (reCAPTCHA v2, hCaptcha, Cloudflare Turnstile)
2. Extracts the site key from the page
3. Submits to CapSolver (primary) or 2Captcha (fallback)
4. Injects the solution token into the page

**Requires:** `CAPSOLVER_API_KEY` in environment (injected via skills.entries config).

## Environment Variables

Loaded from `{baseDir}/../tools/.env` by the agent, and also injected via `skills.entries` in clawdbot.json:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for the browser agent's LLM |
| `CAPSOLVER_API_KEY` | No | CapSolver API key for paid CAPTCHA solving |
| `TWOCAPTCHA_API_KEY` | No | 2Captcha API key (alternative to CapSolver) |

## Files

| File | Purpose |
|------|---------|
| `{baseDir}/../tools/browser_agent.py` | Main automation module |
| `{baseDir}/../tools/.env` | API keys (gitignored) |
| `{baseDir}/../tools/.venv/` | Python virtual environment |
| `{baseDir}/../tools/requirements.txt` | Python dependencies |
