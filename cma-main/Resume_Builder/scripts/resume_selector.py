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


def select_content(master_data: dict, jd_data: dict) -> dict:
    """
    Select and rank the best projects and experiences for the given JD.

    Returns:
        {
            "projects":     list[dict],   # top N projects
            "experiences":  list[dict],   # top M experiences
        }
    """
    config = get_config()
    max_projects     = config.get("max_projects", 4)
    max_experiences  = config.get("max_experiences", 3)

    projects    = master_data.get("projects", [])
    experiences = master_data.get("experiences", [])

    # Score and sort
    scored_projects    = sorted(projects,    key=lambda p: _score_item(p, jd_data), reverse=True)
    scored_experiences = sorted(experiences, key=lambda e: _score_item(e, jd_data), reverse=True)

    return {
        "projects":    scored_projects[:max_projects],
        "experiences": scored_experiences[:max_experiences],
    }
