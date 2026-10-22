"""renderer.py — Generate LaTeX resume and compile to PDF (strictly 1 page, professional typography)."""

import os
import subprocess
import shutil
import tempfile
import yaml
from pathlib import Path
from datetime import datetime
from scripts.utils import escape_latex, make_output_folder, get_config, load_yaml, BASE_DIR, DATA_DIR


# ─── Robust, Battle-Tested 1-Page LaTeX Preamble ──────────────────────────────

PREAMBLE = r"""\documentclass[letterpaper,10.5pt]{article}
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
\usepackage[margin=0.45in, top=0.55in, bottom=0.55in]{geometry}
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
  \vspace{4pt plus 2pt minus 1pt}\scshape\raggedright\large\bfseries
}{}{0em}{}[\color{black}\titlerule \vspace{2pt plus 1pt}]

\pdfgentounicode=1

% Robust Subheading commands (NO overlap, clean alignment)
\newcommand{\resumeSubheading}[4]{
  \item
  \begin{tabular*}{1.0\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} & \textbf{\small #2} \\
    \textit{\small #3} & \textit{\small #4} \\
  \end{tabular*}\vspace{-2pt}
}

\newcommand{\resumeProjectHeading}[2]{
  \item
  \begin{tabular*}{1.0\textwidth}{l@{\extracolsep{\fill}}r}
    #1 & \textbf{\small #2} \\
  \end{tabular*}\vspace{-2pt}
}

\newcommand{\resumeItem}[1]{
  \item\small{{#1 \vspace{-1pt}}}
}

\renewcommand\labelitemi{$\vcenter{\hbox{\tiny$\bullet$}}$}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.0in, label={}, itemsep=3.5pt plus 1pt minus 0.5pt, topsep=3.5pt plus 1pt minus 0.5pt, parsep=0pt]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}\vspace{-3pt}}

\newcommand{\resumeItemListStart}{\begin{itemize}[leftmargin=0.15in, itemsep=2pt plus 1pt, topsep=1.5pt plus 1pt, parsep=0pt]}
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
    {{\LARGE \scshape \textbf{{{name}}}}} \\ \vspace{{3pt}}
    \small {links_str}
    \vspace{{-6pt}}
\end{{center}}
"""


def _education(education_list: list) -> str:
    if not education_list:
        return ""
    lines = [r"\section{Education}", r"\resumeSubHeadingListStart"]
    for edu in education_list:
        institution = escape_latex(edu.get("institution", ""))
        degree      = escape_latex(edu.get("degree", ""))
        duration    = escape_latex(edu.get("duration", ""))
        location    = escape_latex(edu.get("location", ""))
        gpa         = edu.get("gpa", "")
        score       = edu.get("score", "")

        # If it's a school entry with just a score (Class X/XII), format compactly
        if score and not gpa:
            degree_with_score = rf"{degree} \ $|$ \ \textbf{{Score:}} {escape_latex(score)}"
            lines.append(rf"\resumeSubheading{{{institution}}}{{{location}}}{{{degree_with_score}}}{{{duration}}}")
        else:
            lines.append(rf"\resumeSubheading{{{institution}}}{{{location}}}{{{degree}}}{{{duration}}}")
            extras = []
            if gpa:
                extras.append(rf"\textbf{{Cumulative CGPA:}} {escape_latex(gpa)}")
            courses = edu.get("relevant_courses", [])
            if courses:
                courses_str = ", ".join(escape_latex(c) for c in courses)
                extras.append(rf"\textbf{{Relevant Coursework:}} {courses_str}")
            if extras:
                lines.append(r"\resumeItemListStart")
                for ex in extras:
                    lines.append(rf"\resumeItem{{{ex}}}")
                lines.append(r"\resumeItemListEnd")

    lines.append(r"\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _skills(skills_dict: dict) -> str:
    if not skills_dict:
        return ""
    lines = [
        r"\section{Technical Skills}",
        r"\begin{itemize}[leftmargin=0.0in, label={}, itemsep=1.5pt, topsep=1pt, parsep=0pt]",
        r"\small{\item{",
    ]
    for category, items in skills_dict.items():
        category_label = category.replace("_", " ").title()
        items_str = ", ".join(escape_latex(str(i)) for i in items)
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
        bullets    = proj.get("bullet_points", [])

        # Rule: If Code link or Live Demo link exists, the project name MUST NOT have a link.
        # Only link project name if no separate code/live links are provided.
        has_explicit_links = bool(github or live)

        if has_explicit_links:
            project_title = rf"\textbf{{{name_esc}}}"
        else:
            project_title = rf"\textbf{{{name_esc}}}"

        # Clean, un-cluttered link list
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

        # Clean tech stack subtitle
        if tech_stack:
            tech_str = escape_latex(", ".join(tech_stack))
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


def _experience(experiences: list) -> str:
    if not experiences:
        return ""
    lines = [r"\section{Experience \& Leadership}", r"\resumeSubHeadingListStart"]
    for exp in experiences:
        company  = escape_latex(exp.get("company", ""))
        role     = escape_latex(exp.get("role", ""))
        duration = escape_latex(exp.get("duration", ""))
        location = escape_latex(exp.get("location", ""))
        bullets  = exp.get("bullet_points", [])

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
    lines = [r"\section{Extracurricular \& Achievements}", r"\resumeItemListStart"]
    for ach in achievements:
        lines.append(rf"\resumeItem{{{escape_latex(ach)}}}")
    lines.append(r"\resumeItemListEnd")
    return "\n".join(lines)


# ─── Main render function ─────────────────────────────────────────────────────

def render_resume(tailored: dict, jd_data: dict, company_override: str = "", prompt_id: str = "") -> dict:
    """
    Generate LaTeX, compile to PDF, save to Resume_Output (strictly 1-page design).

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

    # Build LaTeX document
    body = "\n\n".join(filter(None, [
        _header(profile),
        _education(education),
        _skills(skills),
        _projects(tailored.get("projects", [])),
        _experience(tailored.get("experiences", [])),
        _achievements(achievements_raw),
    ]))

    full_latex = PREAMBLE + "\n\\begin{document}\n" + body + "\n\\end{document}\n"

    # Determine output folder
    output_dir = make_output_folder(role, company)
    folder_name = output_dir.name

    # Write .tex file
    tex_path = output_dir / "resume.tex"
    tex_path.write_text(full_latex, encoding="utf-8")

def _get_latex_executable(configured_name: str = "pdflatex") -> str:
    """Find the full path to pdflatex/xelatex or fall back to configured name."""
    found = shutil.which(configured_name)
    if found:
        return found

    # Known common installation paths on Windows
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

    # Build LaTeX document
    body = "\n\n".join(filter(None, [
        _header(profile),
        _education(education),
        _skills(skills),
        _projects(tailored.get("projects", [])),
        _experience(tailored.get("experiences", [])),
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
        "experiences_included": [e.get("company") for e in tailored.get("experiences", [])],
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
