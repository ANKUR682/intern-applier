"""build_resume.py — Main pipeline orchestrator for the Resume Builder."""

import sys
import os
from pathlib import Path
from typing import Callable, Optional

# Ensure the Resume_Builder root is on sys.path when running directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import (
    get_config,
    load_yaml,
    load_all_experiences,
    load_all_projects,
    DATA_DIR,
)
from scripts.jd_parser    import parse_jd
from scripts.resume_selector import select_content
from scripts.llm_tailor   import tailor_resume
from scripts.renderer     import render_resume
from scripts.ats_scorer   import evaluate_ats_scores
import yaml


def load_master_data() -> dict:
    """Load all master resume data from the data/ directory."""
    return {
        "profile":      load_yaml(DATA_DIR / "profile.yaml"),
        "education":    load_yaml(DATA_DIR / "education.yaml").get("education", []),
        "skills":       load_yaml(DATA_DIR / "skills.yaml").get("skills", {}),
        "achievements": load_yaml(DATA_DIR / "achievements.yaml").get("achievements", []),
        "experiences":  load_all_experiences(),
        "projects":     load_all_projects(),
    }


def build_resume_pipeline(
    jd_text: str,
    company: str = "",
    prompt_id: str = "star_metrics",
    custom_prompt: str = "",
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> dict:
    """
    Run the full resume building pipeline including Multi-Engine ATS Scoring.

    Args:
        jd_text:           Raw job description text
        company:           Optional company name override
        prompt_id:         Prompt preset key from data/prompts.yaml
        custom_prompt:     Custom prompt template string (overrides prompt_id if provided)
        progress_callback: fn(step: int, message: str) for real-time UI updates

    Returns:
        {
            "folder_name": str,
            "output_dir":  Path,
            "pdf_path":    Path,
            "tex_path":    Path,
            "ats_report":  dict,
        }
    """
    def log(step: int, msg: str):
        if progress_callback:
            progress_callback(step, msg)
        else:
            print(f"[Step {step}] {msg}")

    # ── Step 1: Parse JD ─────────────────────────────────────────────────────
    log(1, "Parsing job description with Gemini...")
    jd_data = parse_jd(jd_text)
    log(1, f"Role detected: {jd_data['role']}"
          + (f" @ {jd_data['company']}" if jd_data.get("company") else "")
          + f" | Domain: {jd_data['domain']}")

    # ── Step 2: Load master data ──────────────────────────────────────────────
    log(2, "Loading master resume data...")
    master_data = load_master_data()
    log(2, f"Loaded {len(master_data['projects'])} projects, "
          f"{len(master_data['experiences'])} experiences")

    # ── Step 3: Select best content ───────────────────────────────────────────
    log(3, "Selecting best matching projects and experiences...")
    selected = select_content(master_data, jd_data)
    log(3, f"Selected {len(selected['projects'])} projects, "
          f"{len(selected['experiences'])} experiences for this role")

    # ── Step 4: Tailor with Gemini ────────────────────────────────────────────
    prompt_label = "Custom Prompt" if custom_prompt.strip() else prompt_id
    log(4, f"Tailoring resume content with Gemini using prompt strategy: [{prompt_label}]...")
    tailored = tailor_resume(
        selected=selected,
        jd_data=jd_data,
        master_data=master_data,
        prompt_id=prompt_id,
        custom_prompt=custom_prompt,
    )
    log(4, "Resume content tailored successfully!")

    # ── Step 5: Render LaTeX → PDF (1-page) ───────────────────────────────────
    log(5, "Compiling 1-page LaTeX to PDF...")
    result = render_resume(
        tailored=tailored,
        jd_data=jd_data,
        company_override=company,
        prompt_id=prompt_label,
    )
    log(5, f"1-page Resume compiled -> {result['pdf_path'].name}")

    # ── Step 6: Multi-Engine ATS Scoring ──────────────────────────────────────
    log(6, "Evaluating ATS Scores across 3 Scanner Engines (Greenhouse, Workday, iCIMS models)...")
    ats_report = evaluate_ats_scores(
        master_data=master_data,
        tailored=tailored,
        jd_data=jd_data,
        jd_text=jd_text,
    )

    # Save ats_score.yaml in output directory
    ats_file = result["output_dir"] / "ats_score.yaml"
    ats_file.write_text(yaml.dump(ats_report, default_flow_style=False), encoding="utf-8")

    log(6, f"ATS Analysis Complete: Overall Score {ats_report['overall_score']}/100 [{ats_report['grade']}]")

    result["ats_report"] = ats_report
    result["selected_projects"] = [p.get("name", "") for p in tailored.get("projects", [])]
    return result


# ─── CLI entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    from scripts.utils import load_prompts

    available_prompts = load_prompts()
    prompt_keys = list(available_prompts.keys())

    parser = argparse.ArgumentParser(description="InternApplier Resume Builder CLI")
    parser.add_argument("--jd",      required=True, help="Path to job description .txt file")
    parser.add_argument("--company", default="",    help="Company name (optional override)")
    parser.add_argument("--prompt",  default="star_metrics", choices=prompt_keys, help="Prompt strategy preset")
    args = parser.parse_args()

    jd_path = Path(args.jd)
    if not jd_path.exists():
        print(f"Error: file not found — {jd_path}")
        sys.exit(1)

    jd_text = jd_path.read_text(encoding="utf-8")
    result  = build_resume_pipeline(
        jd_text=jd_text,
        company=args.company,
        prompt_id=args.prompt,
    )
    
    ats = result.get("ats_report", {})
    print(f"\n========================================================")
    print(f"  🎯 ATS COMPOSITE SCORE: {ats.get('overall_score')}/100 — {ats.get('grade')}")
    print(f"========================================================")
    for idx, eng in enumerate(ats.get("engines", []), start=1):
        print(f"  [Scanner {idx}] {eng.get('engine_name')}: {eng.get('score')}/100")
    print(f"========================================================")
    print(f"✅ 1-Page PDF: {result['pdf_path']}")
    print(f"📊 ATS Score Card: {result['output_dir'] / 'ats_score.yaml'}\n")
