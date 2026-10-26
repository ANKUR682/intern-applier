"""utils.py — shared helpers for the Resume Builder pipeline."""

import os
import re
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"


# ─── Config ───────────────────────────────────────────────────────────────────

def get_config() -> dict:
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
        load_dotenv(BASE_DIR.parent / ".env")
        load_dotenv(BASE_DIR.parent / "ColdMailingAgent" / ".env")
    except Exception:
        pass

    config_path = BASE_DIR / "config.yaml"
    data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}

    defaults = {
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        "max_projects": 2,
        "max_experiences": 1,
        "output_dir": "../Resume_Output",
        "latex_compiler": "pdflatex",
        "web_host": "127.0.0.1",
        "web_port": 5000,
        "debug": True,
    }

    cfg = {**defaults, **data}
    if os.getenv("GEMINI_API_KEY"):
        cfg["gemini_api_key"] = os.getenv("GEMINI_API_KEY")
    if os.getenv("GEMINI_MODEL"):
        cfg["gemini_model"] = os.getenv("GEMINI_MODEL")
    return cfg



# ─── YAML loaders ─────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_all_from_dir(directory: Path) -> list[dict]:
    """Load all YAML files from a directory into a list of dicts."""
    items = []
    for yaml_file in sorted(directory.glob("*.yaml")):
        data = load_yaml(yaml_file)
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    entry["_source_file"] = yaml_file.name
                    items.append(entry)
        elif isinstance(data, dict):
            data["_source_file"] = yaml_file.name
            items.append(data)
    return items


def load_all_experiences() -> list[dict]:
    return load_all_from_dir(DATA_DIR / "experiences")


def load_all_projects() -> list[dict]:
    return load_all_from_dir(DATA_DIR / "projects")


def load_prompts() -> dict:
    """Load all tailoring prompts from data/prompts.yaml."""
    prompts_path = DATA_DIR / "prompts.yaml"
    if prompts_path.exists():
        data = load_yaml(prompts_path)
        return data.get("prompts", {})
    return {}


# ─── LaTeX helpers ────────────────────────────────────────────────────────────

_LATEX_ESCAPE_MAP = {
    "&":  r"\&",
    "%":  r"\%",
    "$":  r"\$",
    "#":  r"\#",
    "_":  r"\_",
    "{":  r"\{",
    "}":  r"\}",
    "~":  r"\textasciitilde{}",
    "^":  r"\textasciicircum{}",
    "\\":  r"\textbackslash{}",
}

def escape_latex(text: str) -> str:
    """Escape all LaTeX special characters in a string."""
    if not text:
        return ""
    result = []
    for char in str(text):
        result.append(_LATEX_ESCAPE_MAP.get(char, char))
    return "".join(result)


# ─── Output path helpers ──────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert text to a clean, folder-safe slug."""
    text = re.sub(r"[^\w\s-]", "", text.strip())
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")


def make_output_folder(role: str, company: str) -> Path:
    """Create and return the output folder path for a resume run."""
    from datetime import datetime
    config = get_config()
    output_base = (BASE_DIR / config.get("output_dir", "../Resume_Output")).resolve()

    timestamp = datetime.now().strftime("%b%Y")
    company_part = slugify(company) if company.strip() else ""
    role_part = slugify(role) if role.strip() else "Role"

    if company_part:
        folder_name = f"{role_part}_{company_part}_{timestamp}"
    else:
        folder_name = f"{role_part}_{timestamp}"

    output_dir = output_base / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
