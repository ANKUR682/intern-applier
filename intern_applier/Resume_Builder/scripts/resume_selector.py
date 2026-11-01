"""resume_selector.py — Score and select the best projects/experiences for a given JD."""

from __future__ import annotations
from scripts.utils import get_config, load_all_experiences, load_all_projects


def _score_item(item: dict, jd_data: dict) -> float:
    """
    Score a project or experience against JD data using tag + tech_stack overlap.
    Higher score = better match.
    """
    score = 0.0

    jd_keywords  = set(k.lower() for k in jd_data.get("keywords", []))
    jd_tech      = set(t.lower() for t in jd_data.get("tech_stack", []))
    jd_domain    = jd_data.get("domain", "").lower()

    item_tags    = set(t.lower() for t in item.get("tags", []))
    item_tech    = set(t.lower() for t in item.get("tech_stack", []))

    # Direct tech stack overlap (high weight)
    tech_overlap = item_tech & jd_tech
    score += len(tech_overlap) * 3.0

    # Tag overlap with JD keywords
    keyword_overlap = item_tags & jd_keywords
    score += len(keyword_overlap) * 2.0

    # Domain tag match
    if jd_domain and jd_domain in item_tags:
        score += 4.0

    # Partial keyword match in bullet points
    bullets = item.get("bullet_points", [])
    bullet_text = " ".join(bullets).lower()
    for kw in jd_keywords:
        if kw in bullet_text:
            score += 0.5

    return score


def is_position_of_responsibility(item: dict) -> bool:
    """Identify if an experience entry represents a Position of Responsibility."""
    role = item.get("role", "").lower()
    company = item.get("company", "").lower()
    source = item.get("_source_file", "").lower()
    tags = [t.lower() for t in item.get("tags", [])]

    if "secy" in source or "secretary" in role:
        return True
    if any(k in role for k in ["secretary", "lead", "coordinator", "head", "trainer", "president", "member"]):
        return True
    if any(t in tags for t in ["leadership", "sports-management", "operations", "mentoring", "event-planning"]):
        return True
    if "hall of residence" in company or "club" in company:
        return True
    return False


def select_content(master_data: dict, jd_data: dict) -> dict:
    """
    Select and rank the best projects and experiences for the given JD.
    Guarantees that a Position of Responsibility (e.g. Secretary, Sports & Games)
    is ALWAYS included alongside the top relevant work experience, irrespective
    of the company or projects chosen.

    Returns:
        {
            "projects":     list[dict],   # top N projects
            "experiences":  list[dict],   # work experience + Position of Responsibility
            "work_experiences": list[dict],
            "positions_of_responsibility": list[dict],
        }
    """
    config = get_config()
    max_projects = config.get("max_projects", 2)

    projects    = master_data.get("projects", [])
    experiences = master_data.get("experiences", [])

    # Score and sort projects
    scored_projects = sorted(projects, key=lambda p: _score_item(p, jd_data), reverse=True)

    # Separate work experiences from Positions of Responsibility (PoR)
    por_items = [e for e in experiences if is_position_of_responsibility(e)]
    work_items = [e for e in experiences if not is_position_of_responsibility(e)]

    # 1. Best work experience (e.g. IT Intern)
    scored_work = sorted(work_items, key=lambda e: _score_item(e, jd_data), reverse=True)
    selected_work = scored_work[:1] if scored_work else []

    # 2. Position of Responsibility — always prioritize Secretary, Sports & Games
    def _por_priority(e: dict) -> tuple:
        src = e.get("_source_file", "").lower()
        role = e.get("role", "").lower()
        is_secy = 1 if ("secy" in src or "secretary" in role) else 0
        return (is_secy, _score_item(e, jd_data))

    scored_por = sorted(por_items, key=_por_priority, reverse=True)
    selected_por = scored_por[:1] if scored_por else []

    # Tag entries explicitly
    for w in selected_work:
        w["is_por"] = False
    for p in selected_por:
        p["is_por"] = True

    combined_experiences = selected_work + selected_por

    return {
        "projects": scored_projects[:max_projects],
        "experiences": combined_experiences,
        "work_experiences": selected_work,
        "positions_of_responsibility": selected_por,
    }
