"""ats_scorer.py — Multi-Engine Deterministic ATS Scorer for Resumes.

Uses 3 independent algorithmic scanner engines (no LLM hallucination):
  Engine 1: TF-IDF & Keyword Vector Matcher (Greenhouse/Lever style)
  Engine 2: Structural Integrity & Impact Quantifier (ATS Parser & Action Verb Analysis)
  Engine 3: Skills & Technical Entity Jaccard Overlap (Hard Technical Match)
"""

import re
import math
from collections import Counter
from typing import Dict, List, Set, Tuple


# ─── Power Verbs & Metric Patterns ───────────────────────────────────────────

ACTION_VERBS = {
    "accelerated", "accomplished", "achieved", "analyzed", "architected", "automated",
    "built", "calculated", "classified", "cleaned", "constructed", "coordinated",
    "created", "debugged", "decreased", "delivered", "deployed", "designed",
    "developed", "discovered", "documented", "engineered", "enhanced", "established",
    "evaluated", "executed", "expanded", "extracted", "formulated", "generated",
    "implemented", "improved", "increased", "indexed", "ingested", "initiated",
    "integrated", "launched", "led", "managed", "maximized", "minimized", "modeled",
    "modernized", "monitored", "optimized", "orchestrated", "organized", "outperformed",
    "pipeline", "predicted", "produced", "quantified", "rebalanced", "reduced",
    "refactored", "resolved", "restructured", "scaled", "scored", "simulated",
    "spearheaded", "standardized", "streamlined", "synthesized", "tested", "trained",
    "transformed", "upgraded", "validated", "visualized"
}

METRIC_REGEX = re.compile(r"(\b\d+(\.\d+)?%|\b\d+K\+?|\b\d+M\+?|\b\d+x\b|\b\d+\+?|\b<\s*\d+ms\b|\$\d+)", re.IGNORECASE)

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers",
    "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm",
    "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's",
    "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should",
    "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their",
    "theirs", "them", "themselves", "then", "there", "there's", "these", "they",
    "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's",
    "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "role", "job", "intern", "internship", "work", "responsibilities"
}


# ─── Text Extraction & Tokenization Helpers ────────────────────────────────────

def tokenize(text: str) -> List[str]:
    """Tokenize and normalize text into clean lowercase alphanumeric tokens."""
    tokens = re.findall(r"\b[a-zA-Z0-9\+\#\.\-]{2,}\b", text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


def extract_resume_full_text(master_data: dict, tailored: dict) -> str:
    """Extract flat plain text representation from structured resume data."""
    parts = []
    
    # Profile
    p = master_data.get("profile", {})
    parts.extend([p.get("name", ""), p.get("email", ""), p.get("linkedin", ""), p.get("github", "")])

    # Education
    for edu in master_data.get("education", []):
        parts.extend([edu.get("institution", ""), edu.get("degree", ""), edu.get("gpa", ""), edu.get("score", "")])
        parts.extend(edu.get("relevant_courses", []))

    # Skills
    for cat, items in master_data.get("skills", {}).items():
        parts.extend(items)

    # Projects
    for proj in tailored.get("projects", []):
        parts.append(proj.get("name", ""))
        parts.extend(proj.get("tech_stack", []))
        parts.extend(proj.get("bullet_points", []))

    # Experience
    for exp in tailored.get("experiences", []):
        parts.extend([exp.get("company", ""), exp.get("role", "")])
        parts.extend(exp.get("bullet_points", []))

    # Achievements
    parts.extend(master_data.get("achievements", []))

    return " ".join(filter(None, parts))


# ─── Scanner Engine 1: Keyword Vector & Cosine Match (TF-IDF Style) ───────────

def scan_keyword_density_engine(resume_text: str, jd_text: str, jd_keywords: List[str]) -> Dict:
    """
    Engine 1: Vector Space Keyword & Term-Frequency Matcher.
    Simulates Greenhouse & Lever keyword indexing.
    """
    resume_tokens = tokenize(resume_text)
    jd_tokens = tokenize(jd_text)

    r_counter = Counter(resume_tokens)
    jd_counter = Counter(jd_tokens)

    # Cosine similarity on top JD vocabulary
    all_vocab = set(jd_counter.keys())
    if not all_vocab:
        return {"score": 85, "matched_keywords": [], "missing_keywords": []}

    dot_product = sum(r_counter.get(w, 0) * jd_counter.get(w, 0) for w in all_vocab)
    r_norm = math.sqrt(sum(count ** 2 for count in r_counter.values())) or 1
    jd_norm = math.sqrt(sum(count ** 2 for count in jd_counter.values())) or 1
    cosine_sim = dot_product / (r_norm * jd_norm)

    # Specific Target Keyword matching
    target_kws = [k.lower().strip() for k in jd_keywords if k.strip()]
    matched_kws = []
    missing_kws = []

    for kw in target_kws:
        if re.search(r"\b" + re.escape(kw) + r"\b", resume_text.lower()):
            matched_kws.append(kw)
        else:
            missing_kws.append(kw)

    kw_match_ratio = (len(matched_kws) / len(target_kws)) if target_kws else 0.85
    
    # Combined weighted score (0-100)
    score = int((cosine_sim * 40) + (kw_match_ratio * 60))
    score = max(55, min(98, score + 15))  # normalize to practical ATS curve

    return {
        "engine_name": "Keyword Vector & Cosine Scanner (Greenhouse/Lever Model)",
        "score": score,
        "matched_keywords": matched_kws[:12],
        "missing_keywords": missing_kws[:6],
        "match_ratio_pct": int(kw_match_ratio * 100),
    }


# ─── Scanner Engine 2: Structural Integrity & Impact Quantifier ───────────────

def scan_structure_and_impact_engine(master_data: dict, tailored: dict) -> Dict:
    """
    Engine 2: Checks ATS section headers, contact completeness,
    action verb presence, and quantified metric density (% of bullets with numbers).
    """
    checks = []
    points = 0

    # 1. Contact completeness (25 pts)
    prof = master_data.get("profile", {})
    has_email = bool(prof.get("email"))
    has_phone = bool(prof.get("phone"))
    has_github = bool(prof.get("github"))
    has_linkedin = bool(prof.get("linkedin"))
    
    contact_score = sum([has_email, has_phone, has_github, has_linkedin]) * 6.25
    points += contact_score
    checks.append({"name": "Contact & Profile Links", "passed": contact_score >= 20, "pts": int(contact_score)})

    # 2. Section Headings Detection (25 pts)
    has_edu = len(master_data.get("education", [])) > 0
    has_skills = len(master_data.get("skills", {})) > 0
    has_proj = len(tailored.get("projects", [])) > 0
    has_exp = len(tailored.get("experiences", [])) > 0
    section_score = sum([has_edu, has_skills, has_proj, has_exp]) * 6.25
    points += section_score
    checks.append({"name": "Standard ATS Section Headings", "passed": section_score == 25, "pts": int(section_score)})

    # 3. Action Verb & Impact Metrics in Bullets (50 pts)
    all_bullets = []
    for p in tailored.get("projects", []):
        all_bullets.extend(p.get("bullet_points", []))
    for e in tailored.get("experiences", []):
        all_bullets.extend(e.get("bullet_points", []))

    total_bullets = len(all_bullets) or 1
    quantified_count = 0
    action_verb_count = 0

    for bullet in all_bullets:
        if METRIC_REGEX.search(bullet):
            quantified_count += 1
        first_words = [w.lower() for w in re.findall(r"\b[a-zA-Z]+\b", bullet)[:3]]
        if any(w in ACTION_VERBS for w in first_words):
            action_verb_count += 1

    metric_ratio = quantified_count / total_bullets
    verb_ratio = action_verb_count / total_bullets

    impact_score = int((metric_ratio * 30) + (verb_ratio * 20))
    points += impact_score
    checks.append({
        "name": "Quantified Metrics & Impact (STAR Formula)",
        "passed": metric_ratio >= 0.7,
        "pts": impact_score,
        "metric_pct": int(metric_ratio * 100),
    })

    final_score = max(50, min(99, int(points)))

    return {
        "engine_name": "Structure & Impact Scanner (Workday/Taleo Parser)",
        "score": final_score,
        "quantified_bullets_pct": int(metric_ratio * 100),
        "action_verb_pct": int(verb_ratio * 100),
        "checks": checks,
    }


# ─── Scanner Engine 3: Hard Technical Skills Overlap (Jaccard Model) ───────────

def scan_technical_skills_engine(master_data: dict, jd_tech_stack: List[str], jd_text: str) -> Dict:
    """
    Engine 3: Hard skill entity extraction and Jaccard similarity.
    Evaluates required vs demonstrated tools, frameworks, and languages.
    """
    all_resume_skills = set()
    for cat, items in master_data.get("skills", {}).items():
        for skill in items:
            all_resume_skills.add(skill.lower().strip())

    # Build JD requirement skill set
    req_skills = set(s.lower().strip() for s in jd_tech_stack if s.strip())
    if not req_skills:
        # Fallback: scan JD text for mentions of known technologies
        for skill in all_resume_skills:
            if re.search(r"\b" + re.escape(skill) + r"\b", jd_text.lower()):
                req_skills.add(skill)

    if not req_skills:
        return {
            "engine_name": "Technical Entity Overlap (iCIMS/SuccessFactors Model)",
            "score": 90,
            "matched_skills": list(all_resume_skills)[:8],
            "missing_skills": [],
            "overlap_pct": 90,
        }

    matched = req_skills.intersection(all_resume_skills)
    missing = req_skills.difference(all_resume_skills)

    overlap_ratio = len(matched) / len(req_skills) if req_skills else 1.0
    score = int(55 + (overlap_ratio * 43))

    return {
        "engine_name": "Technical Entity Overlap (iCIMS/SuccessFactors Model)",
        "score": max(55, min(98, score)),
        "matched_skills": sorted(list(matched)),
        "missing_skills": sorted(list(missing))[:5],
        "overlap_pct": int(overlap_ratio * 100),
    }


# ─── Master ATS Evaluator ─────────────────────────────────────────────────────

def evaluate_ats_scores(
    master_data: dict,
    tailored: dict,
    jd_data: dict,
    jd_text: str,
) -> Dict:
    """
    Runs all 3 deterministic scanning engines and computes composite ATS scores.

    Returns:
        {
            "overall_score": int (0-100),
            "grade": str ("A+", "A", "B+", etc.),
            "engines": [engine1, engine2, engine3],
            "top_strengths": list[str],
            "recommendations": list[str],
        }
    """
    resume_text = extract_resume_full_text(master_data, tailored)
    jd_keywords = jd_data.get("keywords", [])
    jd_tech = jd_data.get("tech_stack", [])

    # Run 3 independent scanners
    engine1 = scan_keyword_density_engine(resume_text, jd_text, jd_keywords)
    engine2 = scan_structure_and_impact_engine(master_data, tailored)
    engine3 = scan_technical_skills_engine(master_data, jd_tech, jd_text)

    # Weighted composite score
    composite = int(
        (engine1["score"] * 0.35) +
        (engine2["score"] * 0.35) +
        (engine3["score"] * 0.30)
    )

    if composite >= 92:
        grade = "A+ (Elite ATS Pass)"
    elif composite >= 85:
        grade = "A (Strong ATS Pass)"
    elif composite >= 75:
        grade = "B+ (Competitive Match)"
    else:
        grade = "B (Passing Threshold)"

    strengths = []
    if engine2.get("quantified_bullets_pct", 0) >= 70:
        strengths.append(f"{engine2['quantified_bullets_pct']}% of bullets contain quantified metrics (STAR format)")
    if len(engine3.get("matched_skills", [])) > 0:
        strengths.append(f"Matched key technical entities: {', '.join(engine3['matched_skills'][:5])}")
    if engine1.get("match_ratio_pct", 0) >= 70:
        strengths.append(f"High keyword density alignment with target job title ({engine1['match_ratio_pct']}%)")

    recommendations = []
    if engine1.get("missing_keywords"):
        recommendations.append(f"Consider integrating missing keywords: {', '.join(engine1['missing_keywords'][:4])}")
    if engine3.get("missing_skills"):
        recommendations.append(f"Target role mentions technologies: {', '.join(engine3['missing_skills'][:3])}")
    if engine2.get("quantified_bullets_pct", 0) < 60:
        recommendations.append("Add more specific percentages or benchmarks to bullet points")

    return {
        "overall_score": composite,
        "grade": grade,
        "engines": [engine1, engine2, engine3],
        "top_strengths": strengths,
        "recommendations": recommendations,
    }
