# Quick Capture Methods

## Data Ingestion Channels
- WhatsApp: Direct message to Clawdbot
- Email: Forward to capture@clawd.bot
- Browser: Bookmark extension
- Voice Notes: Record and send via WhatsApp

## Capture Categories
1. Job Search Insights
2. Love Ethic Reflections
3. Fitness Observations
4. Communication Notes
5. Random Thoughts/Ideas

## Tagging System
Use hashtags to categorize:
- #jobsearch
- #selflove
- #fitness
- #communication
- #insight
- #goal

Example Capture Message:
"#insight Realized today that active listening is key to practicing bell hooks' love ethic."

## Quick Capture Workflow for Links
1. Forward or send the link to me via:
   - WhatsApp
   - Email (capture@clawd.bot)
   - Direct message
2. Include context or hashtags if possible
3. I will:
   - Save the link
   - Create a capture document
   - Categorize and tag
   - Provide initial insights
   - Store in appropriate capture directory

## Link Capture Directories
- `/captures/links/` - General links
- `/captures/recipes/` - Recipe and cooking links
- `/captures/insights/` - Particularly meaningful or goal-related links

## Recommended Hashtags
- Job Search: #jobsearch #career #opportunity
- Love Ethic: #selflove #growth #relationships
- Fitness: #fitness #mobility #health
- Personal Development: #learning #skills #improvement

Example:
"Check out this article #jobsearch #technology about emerging tech careers"

## WhatsApp File Sending

**WhatsApp silently drops certain file types**, including `.html` files. They appear as "sent" in logs but never arrive. Always convert before sending.

### Blocked file types (do NOT send directly)
- `.html` / `.htm`
- `.js`, `.sh`, `.py`, `.exe`, `.bat` (executables/scripts)

### Safe file types
- `.pdf`, `.txt`, `.docx`, `.xlsx`, `.csv`
- Images: `.jpg`, `.png`, `.webp`, `.gif`
- Audio/Video: `.mp3`, `.mp4`, `.ogg`

### HTML to PDF conversion
Use puppeteer (installed at `~/clawd/tools/node_modules/puppeteer`):

```javascript
node -e "
const puppeteer = require('/home/bengrady4/clawd/tools/node_modules/puppeteer');
(async () => {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.goto('file:///path/to/input.html', { waitUntil: 'networkidle0' });
  await page.pdf({ path: '/path/to/output.pdf', format: 'Letter', printBackground: true });
  await browser.close();
})();
"
```

**Rule: Before sending any file via WhatsApp, check the extension. If it's not in the safe list, convert to PDF first.**

## Browser Automation

Two browser tools are available. Choose based on the task:

### Built-in `browser` tool (clawdbot native)

The primary browser tool. Uses the `clawd` profile (headless, autonomous, isolated).

- **Best for:** Step-by-step navigation, reading pages, filling simple forms, screenshots
- **Capabilities:** snapshot, act (click/type/drag), screenshot, navigate, PDF, cookies, storage
- **No CAPTCHA solving** built in

```
browser start
browser open https://example.com
browser snapshot --interactive
browser click e12
browser type e15 "text"
browser upload /path/to/file.pdf
browser screenshot --full-page
```

### browser_agent.py (autonomous AI browser)

Python browser-use agent. Runs its own headless Chromium with AI decision-making.

- **Best for:** Complex multi-step flows, forms with CAPTCHAs, tasks requiring judgment
- **Has:** CAPTCHA solving (CapSolver + 2Captcha), anti-detection, AI vision
- **Environment:** `CAPSOLVER_API_KEY` loaded from `tools/.env` and injected via skills config

```bash
/home/bengrady4/clawd/tools/.venv/bin/python /home/bengrady4/clawd/tools/browser_agent.py "task description"
```

### When to use which

| Scenario | Tool |
|----------|------|
| Read a web page | Built-in `browser` |
| Fill a simple form | Built-in `browser` |
| Form with CAPTCHA | `browser_agent.py` |
| Complex multi-step application | `browser_agent.py` |
| Take a screenshot | Built-in `browser` |
| Interact with dynamic JS pages | Either (built-in for precision, agent for autonomy) |

See `skills/browser/SKILL.md` and `skills/job-apply/SKILL.md` for full documentation.

## Document Capture Paths

| Document | Path |
|----------|------|
| Resume | `captures/resume/Benjamin Grady - Senior Software Engineer.pdf` |
| Application tracker | `captures/applications/tracker.md` |
| Per-company archive | `captures/applications/<company-slug>/` |
| Cover letters | `captures/applications/<company-slug>/cover_letter.pdf` |
| Job posting snapshots | `captures/applications/<company-slug>/posting.md` |
| Application screenshots | `captures/applications/<company-slug>/screenshots/` |
| General link captures | `captures/links/` |
| Insight captures | `captures/insights/` |