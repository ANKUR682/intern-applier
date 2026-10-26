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
    """Generate a clean, catchy, high-open-rate subject line without mentioning 'intern' or 'remote'."""
    company_clean = company if company else "your team"
    norm_project = best_project.lower()
    
    if "interview" in norm_project or "mock" in norm_project:
        templates = [
            f"Query regarding {company_clean}'s web platform / AI evaluation architecture",
            f"Full-stack Next.js + Gemini AI platform query ({company_clean})",
            f"Question regarding {company_clean}'s engineering stack & API design",
            f"Scaling interactive web applications / AI systems query ({company_clean})",
        ]
    elif "code" in norm_project or "execution" in norm_project or "docker" in norm_project:
        templates = [
            f"Dockerized multi-language code execution engine ({company_clean})",
            f"Query regarding {company_clean}'s backend architecture & sandboxed execution",
            f"Question regarding distributed systems & runner pipelines ({company_clean})",
            f"Full-stack code execution & API performance query",
        ]
    elif "internapplier" in norm_project or "applier" in norm_project or "automation" in norm_project:
        templates = [
            f"Automated pipeline design & ATS resume parsing ({company_clean})",
            f"Query regarding {company_clean}'s backend automation workflows",
            f"Full-stack automation & AI agent pipelines ({company_clean})",
        ]
    else:
        templates = [
            f"Full-stack software engineering & backend systems ({company_clean})",
            f"Query regarding {company_clean}'s engineering & platform stack",
            f"Building scalable Next.js & backend microservices ({company_clean})",
            f"Question regarding {company_clean}'s developer platforms & infrastructure",
        ]
        
    return random.choice(templates)


def get_smart_fallback_body(first_name: str, company: str, best_project: str, research_data: dict) -> str:
    """
    Generate a dynamic, value-first fallback email body that starts directly
    with the company's domain/challenge instead of self-introductions.
    """
    domain = research_data.get('domain', 'high-scale systems')
    focus = research_data.get('engineering_focus', 'building robust web architecture and backend services')
    
    # Template variant 1: AI Mock Interview focus (Next.js, React, PostgreSQL, Gemini AI)
    variant_1 = f"""Hi {first_name},

I saw that {company} is scaling engineering to tackle {focus} in the {domain} space.

I recently built an AI Mock Interview Platform—a full-stack system using Next.js, React, PostgreSQL, Drizzle ORM, and Google Gemini AI that generates personalized technical/HR interview evaluations in real time. If you have {config.YOUR_TARGET_ROLE} openings, I'd love to help your engineering team ship clean features and scalable APIs.

My resume is attached with direct links to my live demo and GitHub. Would you be open to a quick 5-minute chat, or could you point me to the right engineering manager?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Template variant 2: Online Code Execution Platform (Docker, Node.js, Next.js)
    variant_2 = f"""Hi {first_name},

I was reading about {company}'s work in {domain}, particularly your engineering focus on {focus}.

Lately, I built an Online Code Execution Platform—a full-stack sandboxed execution engine using Next.js, Node.js, PostgreSQL, and Docker that securely compiles and evaluates C++, Java, Python, and JavaScript in real-time. If you're looking for a {config.YOUR_TARGET_ROLE} to help build high-throughput backends and reliable services, I'd love to contribute.

Attached is my resume with GitHub repositories and live links. Would you be open to a brief conversation, or is there an engineering lead you could connect me with?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Template variant 3: Direct problem-solving angle
    variant_3 = f"""Hi {first_name},

Since {company} deals with modern engineering challenges in the {domain} space, I imagine scaling systems for {focus} is a key priority for your team.

I'm a {config.YOUR_YEAR_AND_DEGREE} specializing in full-stack web and backend engineering. I built an AI Mock Interview Platform (Next.js, Drizzle, Gemini) and a multi-language sandboxed code execution engine with Docker. I'm actively seeking a {config.YOUR_TARGET_ROLE} role where I can hit the ground running and write production-ready code.

My resume is attached with code links. Who is the best engineering manager on your team to contact regarding internships?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Template variant 4: InternApplier / Automation focus
    variant_4 = f"""Hi {first_name},

I've been following {company}'s technical growth, specifically how your team handles {focus}.

My background is in full-stack development at {config.YOUR_COLLEGE}, where I recently engineered InternApplier—an automated end-to-end outreach and ATS resume pipeline using Python, Flask, and Gemini AI. I'm looking for a {config.YOUR_TARGET_ROLE} opportunity and would love to help build performant backends and reliable web applications for your team.

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
You are a cold outreach specialist who helps top-tier engineering students get internships. Write a short, highly personalized cold email from {config.YOUR_NAME} to a tech lead.

Candidate Profile:
- Name: {config.YOUR_NAME} ({config.YOUR_YEAR_AND_DEGREE})
- Real Project 1: AI Mock Interview Platform (Full-stack platform using Next.js, React, PostgreSQL, Drizzle ORM, Google Gemini AI, Clerk Auth)
- Real Project 2: Online Code Execution Platform (Multi-language sandboxed code execution engine supporting C++, Java, Python, JS with Docker and Node.js)
- Real Project 3: InternApplier (Automated AI pipeline for ATS tailoring, LaTeX compiling, and recruiter outreach using Python, Flask, Gemini AI)
- Target Role: {config.YOUR_TARGET_ROLE}

Recipient:
- Name: {first_name}
- Title: {designation}
- Company: {company_clean}
- Company Focus / Product: {core_product}
- Engineering Challenge: {research_data.get('engineering_focus', '')}
- Specific Hook: {hook}
- Best Matched Candidate Project (You MUST write about this project): {best_project}

STRICT OUTREACH FORMATTING RULES:
1. GREETING (MANDATORY): Every email MUST begin with exactly: "Hi {first_name}," followed by a blank line.
2. BODY OPENING: Do NOT start the email body with a self-introduction (do not say "My name is {config.YOUR_FIRST_NAME}", "I am a student at...", or "I am writing to..."). Instead, the very first sentence of the message body (after the greeting) must start directly with a specific observation about {company_clean}'s engineering focus or challenges (e.g. "Since {company_clean} handles...", "I saw that {company_clean} is scaling...").
3. BODY CONTENT: Connect your project ({best_project}) to that observation to show direct technical alignment. Explicitly state that you are seeking a "{config.YOUR_TARGET_ROLE}" role.
4. LENGTH & TONE: Keep the total body between 60 and 85 words. No fluff. No corporate speak. No "hope you are well". Avoid all AI buzzwords (delighted, synergy, cutting-edge, dynamic, testament).
5. SUBJECT LINE: Write a catchy, engineering-focused subject line. It must relate to the technical project or {company_clean}'s engineering domain. Do NOT mention 'intern', 'internship', 'remote', or 'application' in the subject line (e.g. use 'Full-Stack Next.js + Gemini AI Architecture' or 'Dockerized Code Execution Engine').
6. SIGN-OFF: End the email exactly with:
   Best regards,
   {config.YOUR_NAME}
   {config.YOUR_COLLEGE}

Output format: Return ONLY a valid JSON object:
{{
  "subject": "Catchy Subject Line",
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
