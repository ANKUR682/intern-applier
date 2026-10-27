"""
Configuration for Cold Mailing Agent.
Synchronized with Resume Builder profile and outreach settings.
"""

import os
import sys
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

BASE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = BASE_DIR.parent.resolve()
RESUME_BUILDER_DIR = PROJECT_ROOT / "Resume_Builder"

# ─── Load Resume Builder Master Profile ──────────────────────────────
_profile_path = RESUME_BUILDER_DIR / "data" / "profile.yaml"
_profile = {}
if _profile_path.exists():
    with open(_profile_path, "r", encoding="utf-8") as f:
        _profile = yaml.safe_load(f) or {}

# ─── Load Gemini Config ──────────────────────────────────────────────
_rb_config_path = RESUME_BUILDER_DIR / "config.yaml"
_rb_config = {}
if _rb_config_path.exists():
    with open(_rb_config_path, "r", encoding="utf-8") as f:
        _rb_config = yaml.safe_load(f) or {}

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or _rb_config.get("gemini_api_key", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or _rb_config.get("gemini_model", "gemini-3.1-flash-lite")

# ─── Gmail Credentials ───────────────────────────────────────────────
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "") or _profile.get("email", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ─── Candidate Profile ───────────────────────────────────────────────
YOUR_NAME = os.getenv("YOUR_NAME") or _profile.get("name", "Ankur Singh")
YOUR_FIRST_NAME = YOUR_NAME.split()[0] if YOUR_NAME else "Ankur"
YOUR_EMAIL = os.getenv("YOUR_EMAIL") or _profile.get("email", "ankursingh31052006@gmail.com")
YOUR_PHONE = os.getenv("YOUR_PHONE") or _profile.get("phone", "+91 7355951342")
YOUR_LINKEDIN = os.getenv("YOUR_LINKEDIN") or _profile.get("linkedin", "https://www.linkedin.com/in/ankur-singh-ba54692a9/")
YOUR_GITHUB = os.getenv("YOUR_GITHUB") or _profile.get("github", "https://github.com/ANKUR682")
YOUR_COLLEGE = os.getenv("YOUR_COLLEGE") or _profile.get("college", "IIT Kharagpur")
YOUR_YEAR_AND_DEGREE = os.getenv("YOUR_YEAR_AND_DEGREE") or _profile.get("degree_status") or _profile.get("year_and_degree", "3rd-year undergraduate at IIT Kharagpur")
YOUR_TARGET_ROLE = os.getenv("YOUR_TARGET_ROLE") or _profile.get("target_role", "remote/onsite software intern")

# ─── Resume Attachment Strategy ──────────────────────────────────────
AUTO_GENERATE_TAILORED_RESUME = True
STATIC_RESUME_PATH = str(BASE_DIR / "Ankur_Resume.pdf")

# ─── Generic Excel Configuration ─────────────────────────────────────
EXCEL_PATH = str(BASE_DIR / "Copy of GES 2026 Mastersheet.xlsx")

# Target sheets to extract from. Matches case-insensitively.
# Set to ["ALL"] to parse every sheet in the workbook, or list specific keywords.
TARGET_SHEETS = [
    "Unicorn",
    "Soonicorn",
]

# ─── Daily Sending & Timing Rules ────────────────────────────────────
# Daily limit: 15 to 20 emails daily
DAILY_LIMIT = 18

# Delay between consecutive emails (3 to 7 minutes jitter)
DELAY_MIN = 180     # 3 minutes
DELAY_MAX = 420     # 7 minutes

# Sending window: strictly 7:00 AM to 9:00 AM (24hr format)
SEND_WINDOW_START = 7   # 7:00 AM
SEND_WINDOW_END = 9     # 9:00 AM

# Pick randomly from the pool of unsent contacts (no repetitive row-order)
RANDOMIZE_OUTREACH = True

# ─── Logging & Persistence ───────────────────────────────────────────
LOG_DIR = str(BASE_DIR / "logs")
LOG_FILE = os.path.join(LOG_DIR, "email_log.csv")
RESEARCH_CACHE_FILE = os.path.join(LOG_DIR, "company_research_cache.json")
