---
name: job-apply
description: Apply to jobs autonomously. Takes a job posting URL and handles the entire process — generates a cover letter, navigates to the application, fills forms, uploads resume and cover letter, solves CAPTCHAs, captures screenshots, and archives everything. Use when the user shares a job link, asks to apply, or wants to submit an application.
metadata: {"moltbot":{"os":["linux"],"requires":{"bins":["python3"],"env":["ANTHROPIC_API_KEY","CAPSOLVER_API_KEY"]}}}
---

# Job Application Skill

Two-step job application automation. The user pastes a job URL, you generate a cover letter then apply.

## Standard Workflow

**Always generate a cover letter first, then apply with it:**

```bash
# Step 1: Generate a tailored cover letter
/home/bengrady4/clawd/tools/.venv/bin/python /home/bengrady4/clawd/skills/job-apply/scripts/cover_letter.py "<JOB_URL>" --company <slug>

# Step 2: Apply with the cover letter
/home/bengrady4/clawd/tools/.venv/bin/python /home/bengrady4/clawd/skills/job-apply/scripts/apply.py "<JOB_URL>" --company <slug> --cover-letter /home/bengrady4/clawd/captures/applications/<slug>/cover_letter.pdf
```

The apply script handles everything:
- Navigates to the job posting and finds the apply button
- Fills all form fields with Ben's info (name, email, phone, location)
- Uploads the resume PDF and cover letter
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

# Resume a previously failed application (loads saved browser session)
... apply.py "<URL>" --company <slug> --resume
```

### Resuming a Failed Application

If an application failed partway through (timeout, email verification needed, context overflow), the browser session is automatically saved. To resume:

```bash
... apply.py "<URL>" --company <slug> --resume
```

**Auto-detection:** If you re-run the same company URL without `--resume`, the script automatically detects the previous failed attempt and resumes with saved cookies. The `--resume` flag is an explicit override.

The resume feature:
- Loads saved cookies and localStorage from `captures/applications/<company>/storage_state.json`
- Uses a modified prompt that tells the agent it is resuming
- Avoids duplicate account creation by preserving logged-in state
- Includes context from the previous attempt (errors, status)

**Note:** Always provide `--company` when resuming to ensure the correct directory is used.

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

## Cover Letter Generation

The `cover_letter.py` script generates a tailored cover letter for each application:

```bash
/home/bengrady4/clawd/tools/.venv/bin/python /home/bengrady4/clawd/skills/job-apply/scripts/cover_letter.py "<JOB_URL>" --company <slug>
```

What it does:
1. Fetches the job posting and extracts text
2. Reads Ben's resume PDF for context
3. Generates a tailored cover letter via Claude (concise, 3 paragraphs, specific to the role)
4. Renders into a professional HTML template matching the resume's style (Calibri, blue accents)
5. Converts HTML to PDF via Playwright

Options:
```bash
# Use a local job description file instead of fetching URL
... cover_letter.py "<URL>" --company <slug> --job-description /path/to/posting.txt

# Custom output path
... cover_letter.py "<URL>" --company <slug> --output /custom/path.pdf
```

Output: `captures/applications/<company>/cover_letter.pdf` and `cover_letter.html`

The HTML template is at `{baseDir}/scripts/cover_letter_template.html`. It uses the same header style as the resume (centered name, blue "Senior Software Engineer" subtitle, contact line with dot separators, thin divider).

## Key Paths

| Resource | Path |
|----------|------|
| Apply script | `{baseDir}/scripts/apply.py` |
| Cover letter script | `{baseDir}/scripts/cover_letter.py` |
| Cover letter template | `{baseDir}/scripts/cover_letter_template.html` |
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
  cover_letter.pdf     # Generated cover letter (if requested)
  cover_letter.html    # HTML source for the cover letter
  result.json          # Full result with status, errors, URLs
  storage_state.json   # Saved browser cookies/localStorage for resume
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
