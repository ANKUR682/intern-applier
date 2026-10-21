# Cold Mailing Agent

Automated cold email outreach engine with company intelligence, human-like email generation, and daily scheduling.

## Features

- **Universal Excel Parser** — Parses any spreadsheet with Company/Name/Email columns (currently: 661 contacts across Unicorns & Soonicorns)
- **Company Intelligence** — Gemini-powered research discovering domain, engineering focus, and personalized hooks
- **Anti-AI Email Writer** — Concise (~85 words), zero clichés, connects real IIT Kharagpur projects to company challenges
- **Resume Bridge** — Auto-generates tailored 1-page PDF via Resume Builder and attaches to every email
- **Daily Scheduler** — 7:00 AM – 9:00 AM window, 15-20 emails/day, randomized order, 3-7 min jitter
- **Strict Deduplication** — CSV log ensures no recruiter is ever contacted twice

## Usage

```bash
python mail_agent.py --dry-run      # Preview random drafts (no sends)
python mail_agent.py --schedule     # Daily daemon (7-9 AM auto)
python mail_agent.py --now          # Immediate batch send
python mail_agent.py --test EMAIL   # Test email to yourself
python mail_agent.py --stats        # Campaign metrics
python mail_agent.py --company "Razorpay" --poc-name "Name" --poc-email "email" --send
```

## Configuration

Edit `config.py` to change:
- `TARGET_SHEETS` — Which Excel sheets to parse (default: Unicorn, Soonicorn)
- `DAILY_LIMIT` — Emails per day (default: 18)
- `SEND_WINDOW_START/END` — Sending hours (default: 7 AM – 9 AM)
- `DELAY_MIN/MAX` — Seconds between emails (default: 180–420)

## Files

| File | Purpose |
|:---|:---|
| `mail_agent.py` | CLI orchestrator |
| `email_parser.py` | Universal Excel recruiter parser |
| `company_researcher.py` | Gemini company intelligence |
| `email_generator.py` | Human cold email writer |
| `resume_attacher.py` | Bridge to Resume Builder |
| `config.py` | All configuration |
