---
name: job-apply
description: Apply to jobs autonomously. Takes a job posting URL and handles the entire process — navigates to the application, fills forms, uploads resume, solves CAPTCHAs, captures screenshots, and archives everything. Use when the user shares a job link, asks to apply, or wants to submit an application.
metadata: {"moltbot":{"os":["linux"],"requires":{"bins":["python3"],"env":["ANTHROPIC_API_KEY","CAPSOLVER_API_KEY"]}}}
---

# Job Application Skill

One-command job application automation. The user pastes a job URL, you run one script, report the result.

## How to Apply

Run the apply script with the job URL:

```bash
/home/bengrady4/clawd/tools/.venv/bin/python /home/bengrady4/clawd/skills/job-apply/scripts/apply.py "<JOB_URL>"
```

That's it. The script handles everything:
- Navigates to the job posting and finds the apply button
- Fills all form fields with Ben's info (name, email, phone, location)
- Uploads the resume PDF
- Solves CAPTCHAs via CapSolver
- Takes screenshots at each step
- Saves a session GIF, conversation log, and full history
- Updates the application tracker
- Outputs a JSON result

### Options

```bash
# Specify company name (otherwise auto-detected from URL)
... apply.py "<URL>" --company rockstar-games

# Include a cover letter
... apply.py "<URL>" --cover-letter /path/to/cover_letter.pdf

# Dry run — stops before submitting
... apply.py "<URL>" --dry-run
```

### Output

The script prints a JSON result at the end with:
- `status`: "submitted", "failed", "error", or "dry_run_complete"
- `agent_result`: what the browser agent reported
- `app_dir`: path to saved artifacts
- `screenshots`: paths to captured screenshots
- `errors`: any errors encountered

## After Running

Report to the user:
1. Whether the application was submitted successfully
2. The company name and role (from agent_result)
3. Any errors or fields that couldn't be filled
4. Where artifacts are saved (screenshots, GIF)

If the application failed, check `captures/applications/<company>/result.json` for details.

## Generating a Cover Letter

If the user wants a cover letter before applying:

1. Read the job posting (use `web_fetch` or the built-in `browser` tool)
2. Read the resume: `captures/resume/Benjamin Grady - Senior Software Engineer.pdf`
3. Write a tailored cover letter
4. Convert to PDF:

```bash
node -e "
const puppeteer = require('/home/bengrady4/clawd/tools/node_modules/puppeteer');
(async () => {
  const b = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const p = await b.newPage();
  await p.setContent(\`<html><body style='font-family:Georgia,serif;max-width:700px;margin:40px auto;line-height:1.6'>
    COVER_LETTER_HTML_HERE
  </body></html>\`);
  await p.pdf({ path: '/home/bengrady4/clawd/captures/applications/COMPANY/cover_letter.pdf', format: 'Letter', margin: {top:'1in',bottom:'1in',left:'1in',right:'1in'} });
  await b.close();
})();
"
```

5. Then run apply.py with `--cover-letter` pointing to the PDF

## Key Paths

| Resource | Path |
|----------|------|
| Apply script | `{baseDir}/scripts/apply.py` |
| Resume | `/home/bengrady4/clawd/captures/resume/Benjamin Grady - Senior Software Engineer.pdf` |
| Application archives | `/home/bengrady4/clawd/captures/applications/<company>/` |
| Tracker | `/home/bengrady4/clawd/captures/applications/tracker.md` |
| Python venv | `/home/bengrady4/clawd/tools/.venv/bin/python` |

## Candidate Info

- **Name:** Benjamin Grady
- **Email:** bengrady4@gmail.com
- **Phone:** +1 (613) 217-7549
- **Location:** Toronto, Ontario, Canada
- **Title:** Senior Software Engineer
- **Stack:** React, .NET/C#, Golang, Python, Java (fullstack, backend preference)

## What Gets Saved (per application)

```
captures/applications/<company>/
  result.json          # Full result with status, errors, URLs
  task_prompt.txt      # The prompt sent to the browser agent
  conversation.json    # Full agent conversation log
  history.json         # Step-by-step agent history
  session.gif          # Animated GIF of the browser session
  screenshots/         # Screenshots from each step
    step_000.png
    step_001.png
    ...
```

## Email Verification

The script automatically handles email verification codes. When an ATS sends a verification code to bengrady4@gmail.com, the browser agent:
1. Calls `check_email_for_verification_code` action
2. Connects to Gmail via IMAP and polls for the code (up to 60s)
3. Extracts the numeric/alphanumeric code from the email
4. Enters it into the form

**Requires:** `GMAIL_APP_PASSWORD` in `~/.clawdbot/.env` or `tools/.env`
Generate one at: https://myaccount.google.com/apppasswords

## Troubleshooting

- **CAPTCHA fails**: Check `CAPSOLVER_API_KEY` is set in `/home/bengrady4/clawd/tools/.env`
- **Email verification fails**: Check `GMAIL_APP_PASSWORD` is set (not the Gmail password — must be an App Password)
- **Resume not found**: Verify file exists at the resume path above
- **Application hangs**: The script has a max of 80 steps; if it times out, check `result.json`
- **ATS redirect**: The agent follows redirects to Greenhouse, Lever, Workday, etc. automatically
