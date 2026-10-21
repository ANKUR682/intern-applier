# Resume Builder — 1-Page ATS-Optimized Resume Engine

AI-powered resume tailoring tool. Paste any job description → select your tailoring strategy → get a strictly **1-page**, ATS-friendly PDF resume in seconds.

---

## Features

1. **Strict 1-Page Format** — Compact LaTeX geometry with tight line height ensuring everything fits cleanly on a single page.
2. **4-Stage Google XYZ Surgeon (Default)** — Translates your profile, X-Rays ATS keywords, rewrites bullets using `Accomplished [X], as measured by [Y], by doing [Z]`, and preserves your authentic voice.
3. **3-Engine ATS Scoring** — Simulates Greenhouse/Lever (keyword vector), Workday/Taleo (structure & impact), and iCIMS (technical entity overlap) scanners.
4. **Multiple Tailoring Strategies** — Choose from presets or write custom prompts:
   - 🏥 4-Stage ATS & Google XYZ Surgeon (Default)
   - ⭐ STAR & Impact Metrics
   - 🎯 Aggressive ATS Keyword Matching
   - ⚡ Crisp & Concise One-Liners
5. **Project Link Holders** — Project titles hyperlinked directly to GitHub and live demos.

---

## Quick Start

### 1. Install dependencies

```bash
cd Resume_Builder
pip install -r requirements.txt
```

### 2. Install MiKTeX (LaTeX compiler)

- Download: https://miktex.org/download
- Select: **"Install missing packages on-the-fly: Yes"**
- Restart your terminal after install.

### 3. Add your Gemini API Key

Edit `config.yaml`:
```yaml
gemini_api_key: "YOUR_KEY_FROM_AISTUDIO"
gemini_model: "gemini-2.5-flash"
```

### 4. Run the Web UI

```bash
python web_ui/app.py
```
Open **http://127.0.0.1:5000** in your browser.

---

## Project Structure

```
Resume_Builder/
├── config.yaml              # Gemini API key & model config
├── requirements.txt         # Python dependencies
├── data/
│   ├── profile.yaml         # Your name, email, phone, links
│   ├── education.yaml       # Education entries
│   ├── skills.yaml          # Technical skills
│   ├── achievements.yaml    # Awards & achievements
│   ├── prompts.yaml         # LLM tailoring prompt strategies
│   ├── projects/            # One YAML per project
│   └── experiences/         # One YAML per experience
├── scripts/
│   ├── build_resume.py      # Main pipeline orchestrator
│   ├── jd_parser.py         # Gemini JD parser
│   ├── resume_selector.py   # Project/experience matcher
│   ├── llm_tailor.py        # Gemini bullet rewriter
│   ├── renderer.py          # LaTeX template renderer
│   ├── ats_scorer.py        # 3-engine ATS scorer
│   └── utils.py             # Shared helpers
├── templates/
│   └── resume_template.tex  # LaTeX base template
└── web_ui/
    ├── app.py               # Flask server
    ├── templates/index.html  # Web dashboard
    └── static/              # CSS & JS
```

---

## Adding Custom Prompts

Edit `data/prompts.yaml` to add new prompt strategies. They automatically appear in both the Web UI dropdown and the CLI `--prompt` flag.

## Adding Projects

Create a new YAML file in `data/projects/`:

```yaml
name: "FraudSentinel: Anomaly Detection Pipeline"
tagline: "Graph-based fraud detection on Bitcoin networks"

bullet_points:
  - "Cleaned and analyzed 203K+ Bitcoin network transaction logs..."
  - "Discovered a 2.4x higher illicit-node concentration..."

tech_stack:
  - Python
  - PyTorch Geometric
  - XGBoost

github_link: "https://github.com/yourusername/FraudSentinel"
live_link: "https://fraudsentinel.streamlit.app"

duration: "Jul 2024 – Present"
tags: [ml, gnn, fraud-detection, python]
```
