"""jd_parser.py — Extract structured info from a job description using Gemini with backoff."""

import json
import time
from google import genai
from scripts.utils import get_config


def parse_jd(jd_text: str, max_retries: int = 3) -> dict:
    """
    Parse a job description and return structured metadata with automatic 429 backoff.
    """
    config = get_config()
    client = genai.Client(api_key=config["gemini_api_key"])

    prompt = f"""
You are a resume optimization assistant. Analyze the following job description and extract structured information.

Return ONLY a valid JSON object with these fields:
- role: job title as written (string)
- company: company name if mentioned, else empty string
- domain: one of [backend, frontend, fullstack, ml, data, devops, mobile, research, other]
- level: one of [intern, junior, mid, senior]
- keywords: list of 10-15 most important technical keywords and concepts from the JD
- tech_stack: list of specific technologies/tools/frameworks explicitly mentioned
- summary: 1-2 sentence plain-English summary of the role

Job Description:
---
{jd_text}
---

Return ONLY the JSON object, no markdown fences.
"""

    raw = ""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model=config["gemini_model"], contents=prompt)
            raw = response.text.strip()
            break
        except Exception as e:
            wait_time = 6.0 * (attempt + 1)
            print(f"[RateLimit] JD Parser error ({e}). Waiting {wait_time:.1f}s before retry ({attempt + 1}/{max_retries})...")
            time.sleep(wait_time)

    if not raw:
        # Fallback if Gemini quota is completely exhausted
        return {
            "role": "Data / Software Engineering Intern",
            "company": "",
            "domain": "data",
            "level": "intern",
            "keywords": ["Python", "Data Analysis", "Machine Learning", "SQL"],
            "tech_stack": ["Python", "SQL", "Pandas"],
            "summary": "Technical internship role."
        }

    # Strip markdown fences if Gemini adds them anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        parsed = json.loads(raw.strip())
    except json.JSONDecodeError:
        parsed = {}

    # Normalize
    parsed.setdefault("role", "Software Engineering Intern")
    parsed.setdefault("company", "")
    parsed.setdefault("domain", "data")
    parsed.setdefault("level", "intern")
    parsed.setdefault("keywords", ["Python", "Machine Learning", "Data Analysis", "SQL"])
    parsed.setdefault("tech_stack", ["Python", "SQL", "PyTorch"])
    parsed.setdefault("summary", "")

    return parsed
