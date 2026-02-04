#!/usr/bin/env python3
"""
Cover letter generation pipeline.

Fetches a job posting, generates a tailored cover letter via Claude,
renders it into a professional HTML template, and converts to PDF.

Usage:
    python cover_letter.py <job_url> --company <slug>
    python cover_letter.py <job_url> --company <slug> --job-description posting.txt
    python cover_letter.py <job_url> --company <slug> --output /path/to/output.pdf
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

# Add tools directory to path
TOOLS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from dotenv import load_dotenv

load_dotenv(TOOLS_DIR / ".env")

# Paths
WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
CAPTURES = WORKSPACE / "captures"
APPLICATIONS = CAPTURES / "applications"
RESUME_PATH = CAPTURES / "resume" / "Benjamin Grady - Senior Software Engineer.pdf"
TEMPLATE_PATH = Path(__file__).resolve().parent / "cover_letter_template.html"
CHROMIUM_PATH = Path.home() / ".cache" / "ms-playwright" / "chromium-1208" / "chrome-linux64" / "chrome"


class _HTMLTextExtractor(HTMLParser):
    """Strip HTML tags and extract text content."""

    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "header", "footer", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer", "noscript"):
            self._skip = False
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"):
            self._text.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def get_text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self._text)).strip()


def html_to_text(html: str) -> str:
    """Convert HTML to plain text."""
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def extract_resume_text() -> str:
    """Extract text from the resume PDF using pypdf."""
    if not RESUME_PATH.exists():
        return ""
    from pypdf import PdfReader

    reader = PdfReader(str(RESUME_PATH))
    text = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text.append(t)
    return "\n".join(text)


def fetch_job_posting(url: str) -> str:
    """Fetch a job posting URL and extract text content."""
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "html" in content_type:
        return html_to_text(resp.text)
    return resp.text


def generate_cover_letter(job_text: str, resume_text: str) -> dict:
    """Generate a tailored cover letter using Claude."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = """You are writing a cover letter for Benjamin Grady, a Senior Software Engineer with 9+ years of experience. Write a concise, professional cover letter tailored to the specific job posting.

RULES:
- 3 paragraphs maximum. Be concise.
- First paragraph: state the specific role and express genuine interest. Mention one standout qualification.
- Middle paragraph(s): highlight 2-3 specific experiences from the resume that directly match the job requirements. Use concrete details — technologies, team sizes, outcomes. Do NOT be generic.
- Final paragraph: brief closing with availability and enthusiasm. One or two sentences.
- Do NOT use filler phrases like "I am writing to express my interest", "I believe I would be a great fit", "I am excited about the opportunity", or "Thank you for considering my application".
- Be direct and specific. Every sentence should add value.
- Match the tone to the company — more formal for enterprise/finance, slightly relaxed for startups/gaming.

IMPORTANT: Return ONLY valid JSON with this exact structure:
{
  "company_name": "Company Name",
  "job_title": "Job Title",
  "hiring_manager": "Hiring Manager",
  "body_paragraphs": [
    "First paragraph text...",
    "Second paragraph text...",
    "Third paragraph text..."
  ]
}

If you can identify a hiring manager name from the posting, use it. Otherwise use "Hiring Manager".
Do NOT include the greeting ("Dear...") or closing ("Sincerely...") — those are in the template."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"JOB POSTING:\n{job_text[:6000]}\n\nRESUME:\n{resume_text[:4000]}",
            }
        ],
    )

    response_text = message.content[0].text.strip()

    # Extract JSON from response (handle markdown code fences)
    json_match = re.search(r"\{[\s\S]*\}", response_text)
    if not json_match:
        raise ValueError(f"Failed to parse JSON from response: {response_text[:200]}")

    return json.loads(json_match.group())


def render_html(letter_data: dict) -> str:
    """Render the cover letter into the HTML template."""
    template = TEMPLATE_PATH.read_text()

    body_html = "\n    ".join(
        f"<p>{para}</p>" for para in letter_data["body_paragraphs"]
    )

    date_str = datetime.now().strftime("%B %d, %Y")

    html = template
    html = html.replace("{date}", date_str)
    html = html.replace("{company_name}", letter_data.get("company_name", ""))
    html = html.replace("{hiring_manager}", letter_data.get("hiring_manager", "Hiring Manager"))
    html = html.replace("{job_title}", letter_data.get("job_title", ""))
    html = html.replace("{body}", body_html)
    return html


async def html_to_pdf(html: str, output_path: str):
    """Convert HTML to PDF using Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=str(CHROMIUM_PATH),
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.pdf(
            path=output_path,
            format="Letter",
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            print_background=True,
        )
        await browser.close()


async def main():
    parser = argparse.ArgumentParser(description="Generate a tailored cover letter")
    parser.add_argument("url", help="Job posting URL")
    parser.add_argument("--company", help="Company slug for directory naming")
    parser.add_argument("--job-description", help="Path to job description text file (instead of fetching URL)")
    parser.add_argument("--output", help="Output PDF path (default: captures/applications/<company>/cover_letter.pdf)")
    args = parser.parse_args()

    # Determine company slug
    if args.company:
        company = args.company
    else:
        from urllib.parse import urlparse

        domain = urlparse(args.url).netloc
        domain = re.sub(r"^www\.", "", domain)
        domain = re.sub(r"\.(com|org|net|io|co|careers|jobs).*$", "", domain)
        company = re.sub(r"[^\w-]", "-", domain.split(".")[0].lower()).strip("-")

    # Output paths
    app_dir = APPLICATIONS / company
    app_dir.mkdir(parents=True, exist_ok=True)
    output_pdf = args.output or str(app_dir / "cover_letter.pdf")
    output_html = str(app_dir / "cover_letter.html")

    print(f"Job URL: {args.url}")
    print(f"Company: {company}")
    print(f"Output: {output_pdf}")
    print("---")

    # Step 1: Get job posting text
    if args.job_description:
        print(f"Reading job description from: {args.job_description}")
        job_text = Path(args.job_description).read_text()
    else:
        print("Fetching job posting...")
        job_text = fetch_job_posting(args.url)

    if not job_text or len(job_text) < 50:
        print("WARNING: Job posting text is very short or empty. The cover letter may be generic.")

    # Step 2: Extract resume text
    print("Reading resume...")
    resume_text = extract_resume_text()

    # Step 3: Generate cover letter via Claude
    print("Generating cover letter...")
    letter_data = generate_cover_letter(job_text, resume_text)
    print(f"  Company: {letter_data.get('company_name')}")
    print(f"  Role: {letter_data.get('job_title')}")

    # Step 4: Render HTML
    print("Rendering HTML...")
    rendered_html = render_html(letter_data)
    Path(output_html).write_text(rendered_html)

    # Step 5: Convert to PDF
    print("Converting to PDF...")
    await html_to_pdf(rendered_html, output_pdf)

    print("---")
    print(f"Cover letter PDF: {output_pdf}")
    print(f"Cover letter HTML: {output_html}")
    print(json.dumps({"pdf": output_pdf, "html": output_html, "company": company, "job_title": letter_data.get("job_title")}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
