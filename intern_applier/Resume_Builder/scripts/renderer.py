"""renderer.py — Generate LaTeX resume and compile to PDF (strictly 1 page, professional typography)."""

import os
import subprocess
import shutil
import tempfile
import yaml
from pathlib import Path
from datetime import datetime
from scripts.utils import escape_latex, make_output_folder, get_config, load_yaml, BASE_DIR, DATA_DIR
from scripts.resume_selector import is_position_of_responsibility


# ─── Robust, Battle-Tested 1-Page LaTeX Preamble ──────────────────────────────

PREAMBLE = r"""\documentclass[letterpaper,10pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage[margin=0.35in, top=0.35in, bottom=0.35in]{geometry}
\input{glyphtounicode}

\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

% Clean section dividers with dynamic stretch
\titleformat{\section}{
  \vspace{1.5pt plus 0.5pt minus 0.5pt}\scshape\raggedright\large\bfseries
}{}{0em}{}[\color{black}\titlerule \vspace{1pt}]

\pdfgentounicode=1

% Robust Subheading commands (NO overlap, clean alignment)
\newcommand{\resumeSubheading}[4]{
  \item
  \begin{tabular*}{1.0\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} & \textbf{\small #2} \\
    \textit{\small #3} & \textit{\small #4} \\
  \end{tabular*}\vspace{-2.5pt}
}

\newcommand{\resumeProjectHeading}[2]{
  \item
  \begin{tabular*}{1.0\textwidth}{l@{\extracolsep{\fill}}r}
    #1 & \textbf{\small #2} \\
  \end{tabular*}\vspace{-2pt}
}

\newcommand{\resumeItem}[1]{
  \item\small{{#1 \vspace{-1.5pt}}}
}

\renewcommand\labelitemi{$\vcenter{\hbox{\tiny$\bullet$}}$}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.0in, label={}, itemsep=1pt, topsep=1pt, parsep=0pt]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}\vspace{-3pt}}

\newcommand{\resumeItemListStart}{\begin{itemize}[leftmargin=0.15in, itemsep=0.8pt, topsep=0.8pt, parsep=0pt]}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-2pt}}
"""


# ─── Section generators ───────────────────────────────────────────────────────

def _header(profile: dict) -> str:
    name     = escape_latex(profile.get("name", "Your Name"))
    email    = escape_latex(profile.get("email", ""))
    phone    = escape_latex(profile.get("phone", ""))
    linkedin = profile.get("linkedin", "")
    github   = profile.get("github", "")
    website  = profile.get("website", "")
    location = escape_latex(profile.get("location", ""))

    links = []
    if email:
        links.append(rf"\href{{mailto:{email}}}{{\underline{{{escape_latex(email)}}}}}")
    if phone:
        links.append(rf"{phone}")
    if linkedin:
        links.append(rf"\href{{{linkedin}}}{{\underline{{LinkedIn}}}}")
    if github:
        links.append(rf"\href{{{github}}}{{\underline{{GitHub}}}}")
    if website:
        links.append(rf"\href{{{website}}}{{\underline{{Portfolio}}}}")
    if location:
        links.append(rf"{location}")

    links_str = r" \ $|$ \ ".join(links)

    return rf"""
\begin{{center}}
    {{\LARGE \scshape \textbf{{{name}}}}} \\ \vspace{{2pt}}
    \small {links_str}
    \vspace{{-6pt}}
\end{{center}}
"""


def _education(education_list: list) -> str:
    if not education_list:
        return ""
    lines = [r"\section{Education}", r"\resumeSubHeadingListStart"]

    college = next((e for e in education_list if "kharagpur" in e.get("institution", "").lower() or "b.tech" in e.get("degree", "").lower()), None)
    schools = [e for e in education_list if e != college]

    if college:
        inst = escape_latex(college.get("institution", ""))
        deg  = escape_latex(college.get("degree", ""))
        dur  = escape_latex(college.get("duration", ""))
        loc  = escape_latex(college.get("location", ""))
        gpa  = college.get("gpa", "")
        courses = college.get("relevant_courses", [])

        lines.append(rf"\resumeSubheading{{{inst}}}{{{loc}}}{{{deg}}}{{{dur}}}")
        extras = []
        if gpa:
            extras.append(rf"\textbf{{Cumulative CGPA:}} {escape_latex(gpa)}")
        if courses:
            courses_str = ", ".join(escape_latex(c) for c in courses[:6])
            extras.append(rf"\textbf{{Key Coursework:}} {courses_str}")
        if extras:
            extras_line = r" \ $|$ \ ".join(extras)
            lines.append(r"\resumeItemListStart")
            lines.append(rf"\resumeItem{{{extras_line}}}")
            lines.append(r"\resumeItemListEnd")

    if schools:
        school_parts = []
        durations = []
        inst_name = escape_latex(schools[0].get("institution", "School"))
        loc = escape_latex(schools[0].get("location", "India"))
        for s in schools:
            deg = escape_latex(s.get("degree", ""))
            sc = s.get("score", "")
            if sc:
                school_parts.append(rf"{deg} ({escape_latex(sc)})")
            else:
                school_parts.append(deg)
            if s.get("duration"):
                durations.append(escape_latex(s.get("duration")))

        school_str = r" \ $|$ \ ".join(school_parts)
        dur_str = r" \ $|$ \ ".join(durations) if durations else ""
        lines.append(rf"\resumeSubheading{{{inst_name}}}{{{loc}}}{{{school_str}}}{{{dur_str}}}")

    lines.append(r"\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _skills(skills_dict: dict) -> str:
    if not skills_dict:
        return ""
    lines = [
        r"\section{Technical Skills}",
        r"\begin{itemize}[leftmargin=0.0in, label={}, itemsep=1pt, topsep=1pt, parsep=0pt]",
        r"\small{\item{",
    ]
    for category, items in list(skills_dict.items())[:4]:
        category_label = category.replace("_", " ").title().replace(" And ", " & ")
        items_str = ", ".join(escape_latex(str(i)) for i in items[:10])
        lines.append(rf"\textbf{{{escape_latex(category_label)}}}{{: {items_str}}} \\")
    lines += ["}}", r"\end{itemize}\vspace{-3pt}"]
    return "\n".join(lines)


def _projects(projects: list) -> str:
    if not projects:
        return ""
    lines = [r"\section{Projects}", r"\resumeSubHeadingListStart"]
    for proj in projects:
        raw_name   = proj.get("name", "Project")
        name_esc   = escape_latex(raw_name)
        tech_stack = proj.get("tech_stack", [])
        github     = proj.get("github_link", "").strip()
        live       = proj.get("live_link", "").strip()
        duration   = escape_latex(proj.get("duration", ""))
        bullets    = proj.get("bullet_points", [])[:3]

        project_title = rf"\textbf{{{name_esc}}}"

        link_parts = []
        if github:
            link_parts.append(rf"\href{{{github}}}{{\underline{{GitHub}}}}")
        if live:
            link_parts.append(rf"\href{{{live}}}{{\underline{{Live Demo}}}}")

        links_str = " $|$ ".join(link_parts)
        if links_str:
            title_and_links = rf"{project_title} \ $|$ \ \small{{{links_str}}}"
        else:
            title_and_links = project_title

        if tech_stack:
            tech_str = escape_latex(", ".join(tech_stack[:8]))
            subtitle = rf"Technologies: {tech_str}"
        else:
            subtitle = ""

        lines.append(rf"\resumeSubheading{{{title_and_links}}}{{{duration}}}{{{subtitle}}}{{}}")
        if bullets:
            lines.append(r"\resumeItemListStart")
            for b in bullets:
                lines.append(rf"\resumeItem{{{escape_latex(b)}}}")
            lines.append(r"\resumeItemListEnd")

    lines.append(r"\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _work_experience(work_experiences: list) -> str:
    if not work_experiences:
        return ""
    lines = [r"\section{Work Experience}", r"\resumeSubHeadingListStart"]
    for exp in work_experiences:
        company  = escape_latex(exp.get("company", ""))
        role     = escape_latex(exp.get("role", ""))
        duration = escape_latex(exp.get("duration", ""))
        location = escape_latex(exp.get("location", ""))
        bullets  = exp.get("bullet_points", [])[:2]

        lines.append(rf"\resumeSubheading{{{company}}}{{{location}}}{{{role}}}{{{duration}}}")
        if bullets:
            lines.append(r"\resumeItemListStart")
            for b in bullets:
                lines.append(rf"\resumeItem{{{escape_latex(b)}}}")
            lines.append(r"\resumeItemListEnd")

    lines.append(r"\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _positions_of_responsibility(por_list: list) -> str:
    if not por_list:
        return ""
    lines = [r"\section{Positions of Responsibility}", r"\resumeSubHeadingListStart"]
    for exp in por_list:
        company  = escape_latex(exp.get("company", ""))
        role     = escape_latex(exp.get("role", ""))
        duration = escape_latex(exp.get("duration", ""))
        location = escape_latex(exp.get("location", ""))
        bullets  = exp.get("bullet_points", [])[:2]

        lines.append(rf"\resumeSubheading{{{company}}}{{{location}}}{{{role}}}{{{duration}}}")
        if bullets:
            lines.append(r"\resumeItemListStart")
            for b in bullets:
                lines.append(rf"\resumeItem{{{escape_latex(b)}}}")
            lines.append(r"\resumeItemListEnd")

    lines.append(r"\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _achievements(achievements: list) -> str:
    if not achievements:
        return ""
    seen = set()
    deduped = []
    for ach in achievements:
        clean = str(ach).strip()
        if clean and clean not in seen:
            seen.add(clean)
            deduped.append(clean)

    lines = [r"\section{Extracurricular \& Achievements}", r"\resumeItemListStart"]
    for ach in deduped[:4]:
        lines.append(rf"\resumeItem{{{escape_latex(ach)}}}")
    lines.append(r"\resumeItemListEnd")
    return "\n".join(lines)


def _get_latex_executable(configured_name: str = "pdflatex") -> str:
    """Find the full path to pdflatex/xelatex or fall back to configured name."""
    found = shutil.which(configured_name)
    if found:
        return found

    candidates = [
        Path(r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe"),
        Path(r"C:\Program Files (x86)\MiKTeX\miktex\bin\pdflatex.exe"),
        Path(os.path.expanduser(r"~\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe")),
        Path(r"C:\texlive\2026\bin\windows\pdflatex.exe"),
        Path(r"C:\texlive\2025\bin\windows\pdflatex.exe"),
        Path(r"C:\texlive\2024\bin\windows\pdflatex.exe"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)

    return configured_name


# ─── Main render function ─────────────────────────────────────────────────────

def render_resume(tailored: dict, jd_data: dict, company_override: str = "", prompt_id: str = "") -> dict:
    """
    Generate LaTeX, compile to PDF, save to Resume_Output (strictly 1-page design).
    Guarantees that Positions of Responsibility (PoR) is ALWAYS present in the resume.

    Returns:
        {
            "folder_name": str,
            "output_dir":  Path,
            "pdf_path":    Path,
            "tex_path":    Path,
        }
    """
    # Load master data
    profile    = load_yaml(DATA_DIR / "profile.yaml")
    education  = load_yaml(DATA_DIR / "education.yaml").get("education", [])
    skills     = load_yaml(DATA_DIR / "skills.yaml").get("skills", {})
    achievements_raw = load_yaml(DATA_DIR / "achievements.yaml").get("achievements", [])

    role    = jd_data.get("role", "Role")
    company = company_override.strip() or jd_data.get("company", "")

    # Partition experiences into Work Experience and Positions of Responsibility
    all_experiences = tailored.get("experiences", [])
    work_exps = [e for e in all_experiences if not e.get("is_por", False) and not is_position_of_responsibility(e)]
    por_exps  = [e for e in all_experiences if e.get("is_por", False) or is_position_of_responsibility(e)]

    # GUARANTEED: If no PoR was passed, fall back to loading secy.yaml (Secretary, Sports & Games)
    if not por_exps:
        secy_path = DATA_DIR / "experiences" / "secy.yaml"
        if secy_path.exists():
            data = load_yaml(secy_path)
            por_exps = data if isinstance(data, list) else [data]

    # Build LaTeX document
    body = "\n\n".join(filter(None, [
        _header(profile),
        _education(education),
        _skills(skills),
        _projects(tailored.get("projects", [])),
        _work_experience(work_exps),
        _positions_of_responsibility(por_exps),
        _achievements(achievements_raw),
    ]))

    full_latex = PREAMBLE + "\n\\begin{document}\n" + body + "\n\\end{document}\n"

    # Determine output folder
    output_dir = make_output_folder(role, company)
    folder_name = output_dir.name

    # Write .tex file
    tex_path = output_dir / "resume.tex"
    tex_path.write_text(full_latex, encoding="utf-8")

    # Compile LaTeX → PDF
    config   = get_config()
    compiler_name = config.get("latex_compiler", "pdflatex")
    compiler = _get_latex_executable(compiler_name)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_tex = Path(tmp) / "resume.tex"
        tmp_tex.write_text(full_latex, encoding="utf-8")

        try:
            result = subprocess.run(
                [compiler, "-interaction=nonstopmode", "-output-directory", tmp, str(tmp_tex)],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"'{compiler}' was not found on your system.\n\n"
                "Please install MiKTeX to compile LaTeX → PDF:\n"
                "  → https://miktex.org/download\n\n"
                "During install, select 'Install missing packages on-the-fly: Yes'.\n"
                "Then restart your terminal and try again."
            )

        tmp_pdf = Path(tmp) / "resume.pdf"
        if not tmp_pdf.exists():
            log_content = result.stdout + result.stderr
            raise RuntimeError(
                f"LaTeX compilation failed. Log:\n{log_content[-2000:]}"
            )

        pdf_path = output_dir / "resume.pdf"
        shutil.copy(tmp_pdf, pdf_path)

    # Save metadata
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "role": role,
        "company": company,
        "prompt_used": prompt_id,
        "jd_keywords": jd_data.get("keywords", []),
        "jd_tech_stack": jd_data.get("tech_stack", []),
        "projects_included": [p.get("name") for p in tailored.get("projects", [])],
        "work_experience_included": [e.get("company") for e in work_exps],
        "positions_of_responsibility_included": [f"{e.get('role')} at {e.get('company')}" for e in por_exps],
    }
    (output_dir / "metadata.yaml").write_text(
        yaml.dump(metadata, default_flow_style=False), encoding="utf-8"
    )

    return {
        "folder_name": folder_name,
        "output_dir":  output_dir,
        "pdf_path":    pdf_path,
        "tex_path":    tex_path,
    }
