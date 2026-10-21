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
    
    if "revlens" in norm_project:
        templates = [
            f"Query regarding {company_clean}'s analytics stack / SQL transforms",
            "Orchestrating SaaS data marts (DuckDB + Streamlit)",
            "Query about analytics engineering / SaaS data pipeline design",
            f"Question regarding {company_clean}'s data pipeline / RevLens project",
        ]
    elif "time" in norm_project or "forecasting" in norm_project or "series" in norm_project:
        templates = [
            f"Hybrid ARIMA + LSTM forecasting query ({company_clean})",
            "Risk estimation using Monte Carlo Dropout / Forecasting query",
            f"Question regarding {company_clean}'s ML modeling / Time-Series prediction",
            "Quantitative modeling & portfolio optimization query",
        ]
    else: # FraudSentinel default
        templates = [
            "Graph ML anomaly detection / FraudSentinel project query",
            f"Query regarding {company_clean}'s fraud detection engineering",
            "Applying GNNs to transaction logs / FraudSentinel",
            f"Question about GNNs & fraud prevention models at {company_clean}",
        ]
        
    return random.choice(templates)


def get_smart_fallback_body(first_name: str, company: str, best_project: str, research_data: dict) -> str:
    """
    Generate a dynamic, value-first fallback email body that starts directly
    with the company's domain/challenge instead of self-introductions.
    """
    domain = research_data.get('domain', 'high-scale systems')
    focus = research_data.get('engineering_focus', 'optimizing real-time data pipelines and predictive models')
    
    # Template variant 1: GNN/FraudSentinel focus (direct, hook-first)
    variant_1 = f"""Hi {first_name},

I saw that {company} is scaling models to handle {focus} in the {domain} space. 

I recently built FraudSentinel—a GNN and XGBoost anomaly detection pipeline that isolated illicit nodes across a 203K+ Bitcoin transaction graph. If you are opening remote data or ML intern roles, I'd love to help your engineering team build clean pipelines or scale network models.

I have attached my resume with direct links to my code and demo. Would you be open to a quick 5-minute chat, or could you point me to the right lead on your data team?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Template variant 2: Time Series & Forecasting focus
    variant_2 = f"""Hi {first_name},

I was reading about {company}'s work in {domain}, particularly your engineering focus on {focus}.

Lately, I've been working on hybrid ARIMA + LSTM modeling engines for financial time-series forecasting, utilizing Monte Carlo Dropout for risk estimation. If you're looking for a remote data or analytics intern to help build clean streams and quantitative models, I'd love to contribute.

Attached is my resume with GitHub repositories and live Streamlit demo links. Would you be open to a quick chat next week, or is there a data lead you could connect me with?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Template variant 3: Direct problem-solving angle
    variant_3 = f"""Hi {first_name},

Since {company} deals with massive data streams in the {domain} space, I imagine scaling pipelines for {focus} is a key focus for your engineering team.

I'm a {config.YOUR_YEAR_AND_DEGREE} specializing in applied ML and data engineering. I built FraudSentinel (GNNs on 203K+ transactions) and a portfolio time-series forecasting pipeline. I'm actively looking for a {config.YOUR_TARGET_ROLE} role where I can jump in and write clean code immediately.

My resume is attached with direct links to my repositories. Who is the best engineering manager to contact regarding internships?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Template variant 4: Value-first, concise
    variant_4 = f"""Hi {first_name},

I've been tracking {company}'s technical growth, specifically how your team handles {focus}.

My background is in applied ML at {config.YOUR_COLLEGE}, where I recently built a graph-based anomaly detection pipeline (FraudSentinel) that processed 200K+ transaction logs. I'm looking for a {config.YOUR_TARGET_ROLE} opening and would love to help write pipelines or train models for your team.

My resume with links to code and live Streamlit demos is attached. Would you be open to pointing me toward the right engineering team lead?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Template variant 5: RevLens Analytics / SaaS metrics focus
    variant_revlens = f"""Hi {first_name},

I was looking at {company}'s operations in {domain}, especially how your team manages {focus}.

Recently, I built RevLens Analytics—a SaaS revenue and cohort analytics engine using DuckDB and Streamlit to orchestrate staging, intermediate, and presentation marts. If you have {config.YOUR_TARGET_ROLE} roles, I'd love to help build reliable data marts or optimize SQL transformations.

My resume is attached with direct links to my code and demo. Would you be open to a quick 5-minute chat, or could you point me to the right lead on your data team?

Best regards,
{config.YOUR_NAME}
{config.YOUR_COLLEGE}"""

    # Determine output based on best matched project name
    norm_project = best_project.lower()
    if "revlens" in norm_project:
        return variant_revlens
    elif "time" in norm_project or "forecasting" in norm_project or "series" in norm_project:
        return variant_2
    else:
        return random.choice([variant_1, variant_3, variant_4])


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
    best_project = research_data.get("best_matched_project", "FraudSentinel (Graph ML & Anomaly Detection)")
    if selected_projects:
        has_fraud = any("fraud" in p.lower() or "sentinel" in p.lower() for p in selected_projects)
        has_revlens = any("revlens" in p.lower() or "cohort" in p.lower() for p in selected_projects)
        has_timeseries = any("time" in p.lower() or "series" in p.lower() or "forecasting" in p.lower() for p in selected_projects)
        
        if has_fraud:
            best_project = "FraudSentinel (Graph ML & Fraud Detection)"
        elif has_revlens:
            best_project = "RevLens Analytics (SaaS Data Engine)"
        elif has_timeseries:
            best_project = "Financial Time Series Engine"
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
- Real Project 1: FraudSentinel (Graph Neural Networks & XGBoost on 203K+ Bitcoin network transaction logs, 2.4x cluster discovery)
- Real Project 2: Financial Time Series Engine (Hybrid ARIMA + LSTM with Monte Carlo Dropout, Modern Portfolio Theory)
- Real Project 3: RevLens Analytics (Customer cohort retention matrices & MRR movement accounting models using DuckDB and Streamlit)
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
5. SUBJECT LINE: Write a catchy, engineering-focused subject line. It must relate to the technical project or {company_clean}'s engineering domain. Do NOT mention 'intern', 'internship', 'remote', or 'application' in the subject line (e.g. use 'GNN Anomaly Detection / FraudSentinel' or 'Orchestrating SaaS data marts').
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
