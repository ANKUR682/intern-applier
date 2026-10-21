# InternApplier

An end-to-end AI-powered internship application ecosystem built by **Chirag Janbandhu** (IIT Kharagpur).

Automates the entire cold outreach pipeline: researches target companies, writes human-sounding cold emails, generates tailored 1-page ATS-optimized resumes, and delivers them on a daily schedule — all from a single command.

---

## Modules

| Module | Description | Status |
|:---|:---|:---|
| **[Resume_Builder](Resume_Builder/)** | AI-powered 1-page resume compiler with Gemini tailoring, LaTeX rendering, and 3-engine ATS scoring | ✅ Active |
| **[ColdMailingAgent](ColdMailingAgent/)** | Automated cold email outreach with company intelligence, anti-AI email writing, and daily scheduling (7–9 AM) | ✅ Active |
| **[LinkedIn_Optimizer](LinkedIn_Optimizer/)** | LinkedIn profile optimization agent | 🔜 Planned |
| **[Github_Optimizer](Github_Optimizer/)** | GitHub profile & README optimization agent | 🔜 Planned |
| **[Generic_Apply_Agent](Generic_Apply_Agent/)** | Automated job portal application agent | 🔜 Planned |

---

## Architecture

```
InternApplier/
├── Resume_Builder/          # 1-Page ATS Resume Engine
│   ├── data/                # Master profile, projects, experiences, prompts
│   ├── scripts/             # Pipeline: JD parsing → LLM tailoring → LaTeX → ATS scoring
│   ├── templates/           # LaTeX resume template
│   └── web_ui/              # Flask web dashboard
├── ColdMailingAgent/        # Automated Cold Outreach Engine
│   ├── mail_agent.py        # CLI orchestrator (--dry-run, --schedule, --now, --test, --stats)
│   ├── email_parser.py      # Universal Excel/CSV recruiter parser
│   ├── company_researcher.py# Gemini-powered company intelligence
│   ├── email_generator.py   # Anti-AI human email writer
│   └── resume_attacher.py   # Bridge to Resume Builder for tailored PDF
├── Resume_Output/           # Generated tailored resumes (per company)
├── InternApplier_CLI_Manual.pdf  # Full CLI reference (printable)
└── README.md                # This file
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- MiKTeX (LaTeX compiler) — [Download](https://miktex.org/download)
- Gemini API Key — [Get one](https://aistudio.google.com)
- Gmail App Password — [Create one](https://myaccount.google.com/apppasswords)

### 1. Install dependencies

```bash
cd Resume_Builder && pip install -r requirements.txt
cd ../ColdMailingAgent && pip install -r requirements.txt
```

### 2. Configure credentials

**Resume Builder** — edit `Resume_Builder/config.yaml`:
```yaml
gemini_api_key: "YOUR_GEMINI_API_KEY"
gemini_model: "gemini-2.5-flash"
```

**Cold Mailing Agent** — create `ColdMailingAgent/.env`:
```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
EMAIL_ADDRESS=your.email@gmail.com
EMAIL_APP_PASSWORD=your_app_password
```

### 3. Launch the Web UI

```bash
cd Resume_Builder
python web_ui/app.py
```
Open **http://127.0.0.1:5000** — two tabs: Resume Builder + Cold Outreach.

### 4. Run cold outreach

```bash
cd ColdMailingAgent

# Preview 5 random email drafts (no sending)
python mail_agent.py --dry-run

# Start automated daily scheduler (7:00 AM – 9:00 AM, 15-20 emails/day)
python mail_agent.py --schedule

# Send today's batch immediately
python mail_agent.py --now

# Send a test email to yourself
python mail_agent.py --test your.email@gmail.com

# View campaign stats
python mail_agent.py --stats
```

---

## Key Features

- **4-Stage Google XYZ Resume Tailoring** — Translates your profile, X-Rays ATS keywords, rewrites bullets using Google's XYZ formula, and preserves your authentic voice
- **3-Engine ATS Scoring** — Simulates Greenhouse, Workday, and iCIMS scanners with keyword vector, structure, and entity overlap analysis
- **Universal Excel Parser** — Drop any spreadsheet with company/name/email columns and it auto-detects headers
- **Anti-AI Cold Emails** — Concise (~85 words), zero clichés, connects your real projects to company challenges
- **Randomized Daily Scheduler** — Shuffles contacts daily, 3–7 min jitter between sends, strict deduplication
- **Tailored Resume Per Email** — Every outgoing email includes a freshly compiled 1-page PDF resume tailored to that specific company

---

## License

MIT
