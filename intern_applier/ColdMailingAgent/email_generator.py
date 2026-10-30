"""
email_generator.py — High-Open, Value-First Human Cold Email Writer.

Generates concise, value-first cold emails (~75 words) that avoid boilerplate openers
and connect the candidate's real engineering accomplishments to the target company's challenges.
"""

import json
import random
import re
import time
from google import genai
import config
from company_researcher import research_company


def generate_subject(company: str, best_project: str = "") -> str:
    """Generate a clean, high-open-rate SDE/engineering subject line without mentioning 'intern' or 'remote'."""
    company_clean = company if company else "your team"
    norm_project = best_project.lower()
    
    if "interview" in norm_project or "mock" in norm_project:
        templates = [
            f"Query regarding {company_clean}'s backend architecture & API design",
            f"Full-stack Next.js + Gemini AI platform query ({company_clean})",
            f"Question regarding {company_clean}'s engineering stack & scalable systems",
            f"Scaling interactive web platforms & backend services ({company_clean})",
        ]
    elif "code" in norm_project or "execution" in norm_project or "docker" in norm_project:
        templates = [
            f"Dockerized multi-language code execution engine ({company_clean})",
            f"Query regarding {company_clean}'s backend architecture & sandboxed execution",
            f"Question regarding distributed systems & low-latency execution ({company_clean})",
            f"Backend systems & sandboxed runner architecture ({company_clean})",
        ]
    elif "internapplier" in norm_project or "applier" in norm_project or "automation" in norm_project:
        templates = [
            f"Automated pipeline design & backend data ingestion ({company_clean})",
            f"Query regarding {company_clean}'s distributed automation & service architecture",
            f"Full-stack automation & asynchronous queue pipelines ({company_clean})",
        ]
    else:
        templates = [
            f"Software engineering & backend systems ({company_clean})",
            f"Query regarding {company_clean}'s engineering stack & microservices",
            f"Building scalable backend services & robust APIs ({company_clean})",
            f"Question regarding {company_clean}'s core developer infrastructure",
        ]
        
    return random.choice(templates)


def get_smart_fallback_body(first_name: str, company: str, best_project: str, research_data: dict) -> str:
    """
    Generate a dynamic, value-first fallback email body targeting SDE roles,
    starting directly with the company's domain/challenge instead of self-introductions.
    """
    domain = research_data.get('domain', 'high-scale systems')
    focus = research_data.get('engineering_focus', 'building robust microservices, scalable backend APIs, and distributed systems')
    
    # Template variant 1: AI Mock Interview focus (Next.js, React, PostgreSQL, Gemini AI)
    variant_1 = f"""Hi {first_name},

I saw that {company} is scaling engineering to tackle {focus} in the {domain} space.

I recently built an AI Mock Interview Platform—a full-stack system using Next.js, React, PostgreSQL, Drizzle ORM, and Google Gemini AI featuring clean relational schema design, optimized queries, and real-time evaluation pipelines. If you have {config.YOUR_TARGET_ROLE} openings, I'd love to help your engineering team build scalable backend APIs and ship production-ready features.

My resume is attached with direct links to my live demo and GitHub. Would you be open to a quick 5-minute chat, or could you point me to the right engineering lead?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Template variant 2: Online Code Execution Platform (Docker, Node.js, Next.js, distributed backend)
    variant_2 = f"""Hi {first_name},

I was reading about {company}'s work in {domain}, particularly your engineering focus on {focus}.

Lately, I built an Online Code Execution Platform—a full-stack sandboxed execution engine using Next.js, Node.js, PostgreSQL, and Docker that securely compiles and evaluates C++, Java, Python, and JavaScript in real-time with sub-second latency. If you're looking for an SDE to help design high-throughput backends, optimize data structures, and build reliable services, I'd love to contribute.

Attached is my resume with GitHub repositories and live links. Would you be open to a brief conversation, or is there an engineering manager you could connect me with?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Template variant 3: Direct problem-solving angle (DSA & Systems)
    variant_3 = f"""Hi {first_name},

Since {company} deals with modern engineering challenges in the {domain} space, I imagine scaling systems for {focus} is a key priority for your team.

I'm a {config.YOUR_YEAR_AND_DEGREE} specializing in backend engineering, data structures, and distributed services. I built a multi-language sandboxed code execution engine with Docker and an AI evaluation platform with Next.js and PostgreSQL. I'm actively seeking an SDE opportunity where I can write clean, high-performance code and build robust APIs.

My resume is attached with code links. Who is the best engineering manager on your team to contact regarding software engineering roles?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Template variant 4: InternApplier / Automation & backend pipelines
    variant_4 = f"""Hi {first_name},

I've been following {company}'s technical growth, specifically how your team handles {focus}.

My background is in software engineering at {config.YOUR_COLLEGE}, where I recently engineered InternApplier—an automated end-to-end pipeline and parser using Python, asynchronous task queues, and Gemini AI. I'm looking for an SDE role and would love to help design scalable backend services, optimize database schemas, and implement CI/CD-driven features for your team.

My resume with links to GitHub repositories is attached. Would you be open to pointing me toward the right engineering team lead?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Determine output based on best matched project name
    norm_project = best_project.lower()
    if "code" in norm_project or "execution" in norm_project or "docker" in norm_project:
        return variant_2
    elif "applier" in norm_project or "internapplier" in norm_project or "automation" in norm_project:
        return variant_4
    else:
        return random.choice([variant_1, variant_3])


def generate_cold_email(
    recruiter_name: str,
    designation: str,
    company: str,
    research_data: dict = None,
    selected_projects: list = None,
) -> dict:
    """
    Generate a hyper-personalized, human-like cold email for a remote data intern role.
    Applies modern cold email best practices: no self-intro opener, value-first, ultra-concise.

    Returns:
        {
            "subject": str,
            "body": str,
            "company_hook": str,
            "matched_project": str,
        }
    """
    if not research_data:
        research_data = research_company(company, designation)

    first_name = recruiter_name.strip().split()[0] if recruiter_name.strip() else "there"
    first_name = re.sub(r"^(mr\.|ms\.|dr\.|mrs\.)\s*", "", first_name, flags=re.IGNORECASE)

    company_clean = company.strip() if company.strip() else "your team"
    hook = research_data.get("personal_hook", "")
    core_product = research_data.get("core_product", "")
    
    # Synchronize best_project with selected_projects on the resume
    best_project = research_data.get("best_matched_project", "AI Mock Interview Platform (Next.js & AI)")
    if selected_projects:
        has_mock = any("interview" in p.lower() or "mock" in p.lower() for p in selected_projects)
        has_code = any("code" in p.lower() or "execution" in p.lower() for p in selected_projects)
        has_applier = any("internapplier" in p.lower() or "applier" in p.lower() for p in selected_projects)
        
        if has_mock:
            best_project = "AI Mock Interview Platform (Next.js & Gemini AI)"
        elif has_code:
            best_project = "Online Code Execution Platform (Docker & Node.js)"
        elif has_applier:
            best_project = "InternApplier (Full-Stack AI Automation)"
        else:
            best_project = selected_projects[0]

    if not config.GEMINI_API_KEY:
        subject = generate_subject(company_clean)
        body = get_smart_fallback_body(first_name, company_clean, best_project, research_data)
        return {
            "subject": subject,
            "body": body,
            "company_hook": hook,
            "matched_project": best_project,
        }

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    prompt = f"""
You are a cold outreach specialist who helps elite software engineering students get Software Development Engineer (SDE / Backend / Full Stack / Systems) roles. Write a short, highly personalized cold email from {config.YOUR_NAME} to an engineering manager, tech lead, or recruiter.

Candidate Profile:
- Name: {config.YOUR_NAME} ({config.YOUR_YEAR_AND_DEGREE})
- Core Focus: Software Development Engineer (SDE / Backend / Systems)
- Key Competencies: Data structures & algorithms, scalable backend microservices, REST APIs, distributed systems, clean code, Docker, CI/CD, SQL optimization.
- Real Project 1: AI Mock Interview Platform (Full-stack platform using Next.js, React, PostgreSQL, Drizzle ORM, Google Gemini AI, Clerk Auth)
- Real Project 2: Online Code Execution Platform (Multi-language sandboxed code execution engine supporting C++, Java, Python, JS with Docker, Redis, and Node.js)
- Real Project 3: InternApplier (Automated backend pipeline for data ingestion, ATS tailoring, and outreach using Python, Flask, Gemini AI)
- Target Role: {config.YOUR_TARGET_ROLE}

Recipient:
- Name: {first_name}
- Title: {designation}
- Company: {company_clean}
- Company Focus / Product: {core_product}
- Engineering Challenge: {research_data.get('engineering_focus', '')}
- Specific Hook: {hook}
- Best Matched Candidate Project (You MUST highlight this project): {best_project}

STRICT OUTREACH FORMATTING RULES:
1. GREETING (MANDATORY): Every email MUST begin with exactly: "Hi {first_name}," followed by a blank line.
2. BODY OPENING: Do NOT start the email body with a self-introduction (do not say "My name is {config.YOUR_FIRST_NAME}", "I am a student at...", or "I am writing to..."). Instead, the very first sentence of the message body (after the greeting) must start directly with a specific observation about {company_clean}'s engineering focus, technical architecture, or scaling challenges (e.g. "Since {company_clean} handles...", "I saw that {company_clean} is scaling backend services for...").
3. SDE EMPHASIS & TECHNICAL ALIGNMENT: Connect your project ({best_project}) to that observation to show direct technical alignment. Highlight concrete software engineering strengths: system design, high-performance APIs, scalable databases, or sandboxed execution. Explicitly mention that you are targeting an SDE / Software Engineering role.
4. LENGTH & TONE: Keep the total body between 60 and 85 words. No fluff. No corporate buzzwords (delighted, synergy, cutting-edge, dynamic, testament). Direct, respectful, peer-to-peer engineering tone.
5. SUBJECT LINE: Write a crisp, engineering-focused subject line. It must relate to the technical project, backend architecture, or {company_clean}'s engineering stack. Do NOT mention 'intern', 'internship', 'remote', or 'job application' in the subject line (e.g. use 'Backend Architecture & Sandboxed Code Execution' or 'Scaling High-Throughput APIs | Systems Engineering').
6. SIGN-OFF: End the email exactly with:
   Best regards,
   {config.YOUR_NAME}
   {config.YOUR_COLLEGE}

Output format: Return ONLY a valid JSON object:
{{
  "subject": "Catchy Engineering Subject Line",
  "body": "Hi {first_name},\\n\\n[Email body text here]\\n\\nBest regards,\\n{config.YOUR_NAME}\\n{config.YOUR_COLLEGE}"
}}
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
            print(f"Warning: Gemini email generation attempt {attempt+1}/3 error: {e}")
            time.sleep(5.0 * (attempt + 1))

    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw.strip())
        subject = data.get("subject", generate_subject(company_clean, best_project))
        body = data.get("body", "").strip()
    except Exception:
        subject = generate_subject(company_clean, best_project)
        body = get_smart_fallback_body(first_name, company_clean, best_project, research_data)

    return {
        "subject": subject,
        "body": body,
        "company_hook": hook,
        "matched_project": best_project,
    }
