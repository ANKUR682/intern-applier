"""
resume_attacher.py — Bridges Resume Builder with Cold Mailing Agent.

Dynamically compiles a tailored 1-page PDF resume specifically customized
for the target company, or provides the latest compiled resume.
"""

import sys
import os
from pathlib import Path
import config

# Add Resume_Builder to sys.path
RESUME_BUILDER_PATH = config.RESUME_BUILDER_DIR
if str(RESUME_BUILDER_PATH) not in sys.path:
    sys.path.insert(0, str(RESUME_BUILDER_PATH))


def get_tailored_resume_for_company(
    company: str,
    domain: str = "Data Science & Machine Learning",
    role: str = "Data Science Intern",
) -> tuple[str, list[str]]:
    """
    Generate or locate a tailored 1-page PDF resume for the given company.

    Returns:
        (pdf_path, selected_projects)
    """
    default_projects = ["FraudSentinel: Anomaly Detection Pipeline", "Financial Time Series Engine"]

    if not config.AUTO_GENERATE_TAILORED_RESUME:
        return config.STATIC_RESUME_PATH, default_projects

    try:
        from scripts.build_resume import build_resume_pipeline
        
        # Build synthetic JD targeted to the company & domain
        synthetic_jd = f"""
Company: {company}
Role: {role}
Domain: {domain}

About the Role:
We are looking for a Data Science / Machine Learning Intern to join our engineering and data teams.
You will work on predictive modeling, data pipelines, statistical analysis, feature engineering, and high-scale datasets.

Requirements:
- Strong proficiency in Python, SQL, Pandas, NumPy, and Scikit-learn.
- Experience with Deep Learning / ML frameworks (PyTorch, TensorFlow, XGBoost, GNNs, Time Series).
- Proven project work in anomaly detection, predictive forecasting, or quantitative modeling.
- Solid understanding of algorithms, statistics, and data visualization (Plotly, Matplotlib).
"""
        print(f"  📄 Auto-generating tailored 1-page resume for {company}...")
        result = build_resume_pipeline(
            jd_text=synthetic_jd,
            company=company,
            prompt_id="star_metrics",
        )
        pdf_path = str(result["pdf_path"])
        selected = result.get("selected_projects", default_projects)
        if os.path.exists(pdf_path):
            print(f"  ✓ Tailored resume ready: {os.path.basename(pdf_path)}")
            return pdf_path, selected

    except Exception as e:
        print(f"  ⚠ Note: Dynamic resume build skipped ({e}). Using base resume.")

    # Fallback 1: Static resume
    if os.path.exists(config.STATIC_RESUME_PATH):
        return config.STATIC_RESUME_PATH, default_projects

    # Fallback 2: Search in Resume_Output for any recent PDF
    output_dir = RESUME_BUILDER_PATH.parent / "Resume_Output"
    if output_dir.exists():
        pdfs = list(output_dir.glob("*/*.pdf"))
        if pdfs:
            latest_pdf = str(max(pdfs, key=os.path.getmtime))
            return latest_pdf, default_projects

    return "", default_projects
