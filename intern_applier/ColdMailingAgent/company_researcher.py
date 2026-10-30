"""
company_researcher.py — Deep Intelligence & Hook Generator for Companies.

Extracts structured insights about the company (domain, core product, data/engineering
initiatives) and crafts a genuine connection hook for human-like cold outreach.
"""

import json
import os
import time
from pathlib import Path
from google import genai
import config

_CACHE = {}


def _load_cache():
    global _CACHE
    cache_path = Path(config.RESEARCH_CACHE_FILE)
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                _CACHE = json.load(f)
        except Exception:
            _CACHE = {}


def _save_cache():
    try:
        os.makedirs(os.path.dirname(config.RESEARCH_CACHE_FILE), exist_ok=True)
        with open(config.RESEARCH_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_CACHE, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to save company research cache: {e}")


def research_company(company_name: str, designation: str = "") -> dict:
    """
    Research a target company using Gemini with persistent caching.

    Returns:
        {
            "company": str,
            "domain": str,              # e.g. "Fintech & Payments", "Quick Commerce & Logistics"
            "core_product": str,        # 1-sentence summary of what they build
            "engineering_focus": str,   # specific data/ML/engineering focus areas
            "relevant_projects": list,  # which of candidate's projects fit best
            "personal_hook": str,       # 1-2 sentence human-sounding reason for outreach
        }
    """
    _load_cache()
    norm_name = company_name.strip().lower()
    
    if norm_name in _CACHE:
        return _CACHE[norm_name]

    if not config.GEMINI_API_KEY:
        # Fallback if no API key
        fallback = {
            "company": company_name,
            "domain": "Technology & Software",
            "core_product": f"High-scale web platforms and distributed software infrastructure at {company_name}",
            "engineering_focus": "Building robust microservices, scalable backend APIs, database optimization, and cloud architecture",
            "relevant_projects": ["AI Mock Interview Platform (Next.js & Gemini AI)", "Online Code Execution Platform (Docker & Node.js)"],
            "personal_hook": f"I've been closely following what {company_name} is building and love the backend architecture and clean engineering standards behind your systems.",
        }
        return fallback

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    prompt = f"""
You are a career intelligence researcher assisting {config.YOUR_YEAR_AND_DEGREE} ({config.YOUR_NAME}) in finding meaningful technical connections for a cold outreach email seeking a {config.YOUR_TARGET_ROLE} role.

Candidate Background:
- 3rd-year B.Tech. student at IIT Kharagpur (CGPA 9.18)
- Real Project 1: AI Mock Interview Platform (Full-stack platform using Next.js, React, PostgreSQL, Drizzle ORM, Google Gemini AI, Clerk Auth)
- Real Project 2: Online Code Execution Platform (Multi-language sandboxed code execution engine supporting C++, Java, Python, JS with Docker, Redis, and Node.js)
- Real Project 3: InternApplier (Automated AI pipeline for ATS tailoring, LaTeX compiling, and recruiter outreach using Python, Flask, Gemini AI)
- Core SDE Competencies: Data Structures & Algorithms, Scalable Backend APIs, Microservices, Distributed Systems, Database Optimization (SQL/PostgreSQL), Docker, Git/CI/CD.
- Tech Stack: Python, C++, Java, JavaScript, TypeScript, Next.js, React, Node.js, PostgreSQL, Docker, Redis, REST APIs

Target Company: {company_name}
Target Recruiter/POC Designation: {designation}

Task:
Analyze this company and return ONLY a valid JSON object with:
1. "domain": Primary industry/technical domain (e.g. "Fintech & Payments", "Quick Commerce & Logistics", "DevTools & Cloud Infrastructure", "AI & EdTech", "SaaS & Enterprise Systems", "E-commerce & High-Scale Marketplaces")
2. "core_product": Brief 1-sentence factual description of what {company_name} builds/does.
3. "engineering_focus": 1-sentence describing their core software engineering (SDE / backend / systems) challenges and tech stack (e.g., "high-throughput low-latency REST/gRPC APIs, scalable microservices, distributed data pipelines, and robust cloud services").
4. "best_matched_project": Either "AI Mock Interview Platform (Next.js & AI)" or "Online Code Execution Platform (Docker & Backend)" or "InternApplier (Full-Stack AI Automation)" based on what is most relevant to {company_name}'s SDE tech stack.
5. "personal_hook": A natural, conversational, 1-sentence reason why an SDE student passionate about building performant backends, clean APIs, and distributed systems is excited about {company_name}'s specific engineering stack or scaling challenges (NO robotic buzzwords like 'synergy', 'testament', 'cutting-edge').

Return ONLY the JSON object.
"""

    raw = ""
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt
            )
            raw = response.text.strip()
            break
        except Exception as e:
            print(f"Warning: API attempt {attempt + 1}/3 failed for {company_name}: {e}")
            time.sleep(5.0 * (attempt + 1))

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        data = json.loads(raw.strip())
    except Exception:
        data = {
            "domain": "Technology & Software",
            "core_product": f"Core platforms and digital products at {company_name}",
            "engineering_focus": "Scalable web applications, backend services, and high-performance APIs",
            "best_matched_project": "AI Mock Interview Platform (Next.js & AI)",
            "personal_hook": f"I really admire how {company_name} is solving complex architectural challenges in this space.",
        }

    result = {
        "company": company_name,
        "domain": data.get("domain", "Technology"),
        "core_product": data.get("core_product", ""),
        "engineering_focus": data.get("engineering_focus", ""),
        "best_matched_project": data.get("best_matched_project", "AI Mock Interview Platform (Next.js & AI)"),
        "personal_hook": data.get("personal_hook", ""),
    }

    _CACHE[norm_name] = result
    _save_cache()
    return result
