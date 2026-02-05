---
name: browser
description: Browse the web with an AI-powered browser agent. Supports interactive sessions (browser stays alive across messages) and one-shot tasks. Has CAPTCHA solving and email verification. For job applications, prefer the job-apply skill.
metadata: {"moltbot":{"os":["linux"],"requires":{"bins":["python3"],"env":["ANTHROPIC_API_KEY"]}}}
---

# Browser Automation

> **IMPORTANT — Context Management**
>
> **Always use `browse_session.py` or `browser_agent.py`** for web browsing tasks.
> These run a **separate AI agent in a subprocess** with its own LLM context,
> so only a small JSON result comes back to your session — keeping your context lean.
>
> **Do NOT use the built-in `browser` tool** (snapshot/act) for browsing tasks.
> Each snapshot adds ~1-2K tokens to your session context. Over a few interactions
> this bloats the session to 50K+ tokens, hitting rate limits and causing context overflow.
>
> The **only** acceptable use of the built-in browser is to read a single element
> from an already-open page (e.g. confirm a URL). For anything else, use the scripts below.

**For job applications, use the `job-apply` skill instead.**

## When to Use This Skill

- Any web browsing task (searching, reading, interacting with websites)
- Page has a CAPTCHA (reCAPTCHA, hCaptcha, Turnstile)
- Complex multi-step flow that needs AI judgment
- Need to log into a service
- Interactive browsing where the user sends follow-up instructions

## Interactive Session (Recommended)

Start a persistent browser that stays alive between messages. Use when the user wants to browse interactively or when a task may need follow-up instructions.

```bash
# Start session (runs in background)
{baseDir}/../tools/.venv/bin/python {baseDir}/scripts/browse_session.py --task "Go to github.com and show my notifications" --timeout 600 --max-lifetime 1800 &
```

### Stdout Protocol

The daemon prints line-buffered structured output:

| Line | Meaning |
|------|---------|
| `SESSION_ID:<id>` | Session ID (printed once at start) |
| `SCREENSHOT:<path>` | Path to latest screenshot |
| `RESULT:{"output":"...","errors":[]}` | JSON result of the last task |
| `WAITING` | Daemon is idle, waiting for next task |
| `MAX_LIFETIME_REACHED` | Session auto-terminated after max lifetime |

### Sending Follow-up Tasks

Write a JSON file to the session directory:

```bash
echo '{"instruction":"Click on the login button"}' > captures/browser-sessions/<id>/next_task.json
```

### Closing a Session

```bash
echo '{"instruction":"close"}' > captures/browser-sessions/<id>/next_task.json
```

### Session Directory Layout

```
captures/browser-sessions/<id>/
  status.json          # {"state":"idle|running|closed","pid":12345,...}
  next_task.json       # Written by you, read by daemon
  result.json          # Latest result
  screenshot.png       # Latest screenshot
  storage_state.json   # Browser state (saved on close)
  screenshots/         # Last 20 screenshots (older auto-deleted)
```

### Session Safety

- **Idle timeout**: Session closes after 10 minutes of inactivity (configurable via `--timeout`)
- **Max lifetime**: Hard cap of 30 minutes total (configurable via `--max-lifetime`)
- **CDP heartbeat**: Browser health checked every ~10 seconds; exits if browser dies
- **Crash cleanup**: Signal handlers + atexit ensure browser is killed on unexpected termination
- **Stale reaper**: On startup, dead sessions from previous runs are automatically cleaned up
- **Screenshot cap**: Only the last 20 screenshots are kept per session

## One-Shot Mode

For single tasks where you don't need follow-ups:

```bash
{baseDir}/../tools/.venv/bin/python {baseDir}/../tools/browser_agent.py "Go to example.com and return the page title"
```

## Available Actions

Both modes provide these agent actions:

| Action | Description |
|--------|-------------|
| `solve_captcha_paid` | Auto-detects and solves reCAPTCHA v2, hCaptcha, Cloudflare Turnstile via CapSolver/2Captcha |
| `check_email_for_verification_code` | Polls Gmail IMAP for verification codes (up to 5 min). User can also manually write code to `verification_code.txt` |

## Environment Variables

Loaded from `{baseDir}/../tools/.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for the browser agent's LLM |
| `CAPSOLVER_API_KEY` | No | CapSolver API key for CAPTCHA solving |
| `TWOCAPTCHA_API_KEY` | No | 2Captcha API key (fallback) |
| `GMAIL_APP_PASSWORD` | No | Gmail App Password for email verification |

## Key Files

| File | Purpose |
|------|---------|
| `{baseDir}/scripts/browse_session.py` | Interactive session daemon |
| `{baseDir}/../tools/browser_agent.py` | One-shot browser agent |
| `{baseDir}/../tools/browser_utils.py` | Shared utilities (LLM, profile, CAPTCHA, email) |
| `{baseDir}/../tools/.env` | API keys |
| `{baseDir}/../tools/.venv/` | Python virtual environment |
