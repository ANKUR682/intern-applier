"""
mail_agent.py — Intelligent Cold Mailing Agent & Automated Daily Outreach Scheduler.

Features:
  1. Universal Generic Recruiter DB Parser (Unicorns, Soonicorns, and any Excel sheet)
  2. Automatic Deep Company Research & Problem Discovery
  3. Anti-AI Human Cold Email Writer (<110 words, genuine tone)
  4. Tailored 1-Page Resume Auto-Compiler & Attachment Bridge
  5. 7:00 AM – 9:00 AM Daily Outreach Window with Randomized Contact Shuffling
  6. Automated Scheduler Daemon & Anti-Spam Jitter (3-7 min intervals, 15-20 daily limit)

Usage:
    python mail_agent.py                   Send today's random batch (during 7-9 AM window)
    python mail_agent.py --now             Send today's batch immediately (bypass 7-9 AM window)
    python mail_agent.py --schedule        Run continuous daily scheduler (auto-sends 7-9 AM daily)
    python mail_agent.py --dry-run         Preview random company hooks & email drafts (no sends)
    python mail_agent.py --test EMAIL      Send a live test package (email + tailored PDF) to yourself
    python mail_agent.py --company "Zepto" --poc-name "Karthik" --poc-email "karthik@zepto.com"
    python mail_agent.py --stats           Show campaign metrics and recruiter breakdown
"""

import os
import sys
import csv
import ssl
import time
import random
import smtplib
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from pathlib import Path

from colorama import init, Fore, Style

# Windows unicode handling
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import config
from email_parser import parse_excel, get_stats, Recruiter
from company_researcher import research_company
from email_generator import generate_cold_email, generate_subject
from resume_attacher import get_tailored_resume_for_company

init(autoreset=True)


# ─── Logging & Persistence ───────────────────────────────────────────

def ensure_log_file():
    """Ensure logs directory, email_log.csv, and emails.log exist."""
    os.makedirs(config.LOG_DIR, exist_ok=True)
    if not os.path.exists(config.LOG_FILE):
        with open(config.LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'name', 'email', 'company', 'status', 'matched_project', 'resume_path', 'error'])
            f.flush()
            os.fsync(f.fileno())

    if not os.path.exists(config.EMAILS_LOG_FILE):
        with open(config.EMAILS_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write("# Email Dispatch Audit Log\n")
            f.flush()
            os.fsync(f.fileno())


def log_result(name: str, email: str, company: str, status: str, matched_project: str = "", resume_path: str = "", error: str = "", subject: str = ""):
    """
    Record an email outreach event to CSV and persistent emails.log in real-time.
    Flushes and fsyncs immediately so headless runners (e.g. GitHub Actions)
    and external log tails reflect the dispatch instantly.
    """
    ensure_log_file()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 1. Update email_log.csv immediately
    with open(config.LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            now_str,
            name, email, company, status, matched_project, resume_path, error
        ])
        f.flush()
        os.fsync(f.fileno())

    # 2. Append formatted line to emails.log:
    # Format: [Timestamp] | [Recipient Email] | [Company Name] | [Target Role: SDE] | [Status: SENT/FAILED] | [Subject Line]
    status_tag = status.upper()
    role_tag = "Target Role: SDE"
    subject_clean = subject.replace('\n', ' ').strip() if subject else "N/A"
    log_line = f"[{now_str}] | [{email}] | [{company}] | [{role_tag}] | [Status: {status_tag}] | [{subject_clean}]"
    if error:
        log_line += f" | [Error: {error}]"
    log_line += "\n"

    with open(config.EMAILS_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line)
        f.flush()
        os.fsync(f.fileno())


def get_sent_emails() -> set:
    """
    Return set of already-emailed addresses from active campaign log (email_log.csv)
    to avoid duplicate outreach across runs.
    """
    sent = set()
    if not os.path.exists(config.LOG_FILE):
        return sent
    try:
        with open(config.LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('status') == 'sent':
                    email = row.get('email', '').strip().lower()
                    if email:
                        sent.add(email)
    except Exception as e:
        print(f"Warning: could not read {config.LOG_FILE}: {e}")
    return sent


# ─── Timing & Window Verification ────────────────────────────────────

def is_in_send_window() -> bool:
    """Check if current time is within the allowed daily window (e.g. 7:00 AM - 9:00 AM)."""
    now = datetime.now()
    return config.SEND_WINDOW_START <= now.hour < config.SEND_WINDOW_END


def get_seconds_until_next_window() -> int:
    """Calculate seconds until the next 7:00 AM window starts."""
    now = datetime.now()
    target = now.replace(hour=config.SEND_WINDOW_START, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return int((target - now).total_seconds())


# ─── Email Message Assembly & SMTP ────────────────────────────────────

def create_email_message(
    to_email: str,
    subject: str,
    body: str,
    resume_path: str = "",
) -> MIMEMultipart:
    """Build MIME email with optional tailored 1-page resume attachment."""
    msg = MIMEMultipart()
    msg['From'] = f"{config.YOUR_NAME} <{config.EMAIL_ADDRESS}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    
    # Body
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    # Resume Attachment
    if resume_path and os.path.exists(resume_path):
        with open(resume_path, 'rb') as f:
            part = MIMEBase('application', 'pdf')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        filename = f"{config.YOUR_NAME.replace(' ', '_')}_Resume.pdf"
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(part)
    
    return msg


def send_email(to_email: str, subject: str, body: str, resume_path: str = "") -> tuple[bool, str]:
    """Send cold email via Gmail SMTP with robust SSL (Port 465) & STARTTLS (Port 587) fallback."""
    email_addr = (config.EMAIL_ADDRESS or "").strip()
    app_pwd = (config.EMAIL_APP_PASSWORD or "").strip()

    if not email_addr or not app_pwd:
        return False, "Gmail credentials missing — set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in .env"

    msg = create_email_message(to_email, subject, body, resume_path)
    last_err = ""

    # Strategy: Try direct SSL (Port 465) first, then fallback to STARTTLS (Port 587).
    # Port 465 is more resilient against ISP/firewall/middlebox connection drops.
    endpoints = [
        (465, True),
        (587, False),
    ]

    for port, use_ssl in endpoints:
        try:
            if use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(config.SMTP_SERVER, port, context=context, timeout=30) as server:
                    server.login(email_addr, app_pwd)
                    server.sendmail(email_addr, to_email, msg.as_string())
                return True, ""
            else:
                context = ssl.create_default_context()
                with smtplib.SMTP(config.SMTP_SERVER, port, timeout=30) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(email_addr, app_pwd)
                    server.sendmail(email_addr, to_email, msg.as_string())
                return True, ""
        except smtplib.SMTPAuthenticationError:
            # If app password contained spaces, retry with stripped password
            if " " in app_pwd:
                try:
                    clean_pwd = app_pwd.replace(" ", "")
                    if use_ssl:
                        with smtplib.SMTP_SSL(config.SMTP_SERVER, port, context=ssl.create_default_context(), timeout=30) as server:
                            server.login(email_addr, clean_pwd)
                            server.sendmail(email_addr, to_email, msg.as_string())
                        return True, ""
                    else:
                        with smtplib.SMTP(config.SMTP_SERVER, port, timeout=30) as server:
                            server.ehlo()
                            server.starttls(context=ssl.create_default_context())
                            server.ehlo()
                            server.login(email_addr, clean_pwd)
                            server.sendmail(email_addr, to_email, msg.as_string())
                        return True, ""
                except Exception:
                    pass
            return False, "Authentication failed — verify EMAIL_ADDRESS and EMAIL_APP_PASSWORD in .env"
        except smtplib.SMTPRecipientsRefused:
            return False, f"Recipient refused: {to_email}"
        except Exception as e:
            last_err = str(e)
            continue

    return False, f"SMTP error: {last_err}"


# ─── Commands ────────────────────────────────────────────────────────

def cmd_dry_run(limit: int = 5):
    """Preview company research, email drafts, and resume pairing with randomized selection."""
    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"  🔍  DRY RUN — Randomized Company Outreach Preview")
    print(f"{'='*65}{Style.RESET_ALL}\n")

    recruiters = parse_excel(config.EXCEL_PATH, config.TARGET_SHEETS)
    sent = get_sent_emails()
    pending = [r for r in recruiters if r.email.lower() not in sent]

    if config.RANDOMIZE_OUTREACH:
        random.shuffle(pending)

    print(f"Total contacts extracted: {len(recruiters)} | Unsent pool: {len(pending)}\n")

    for i, r in enumerate(pending[:limit], start=1):
        print(f"{Fore.YELLOW}───────────────────────────────────────────────────────────────")
        print(f"  [{i}/{limit}] Target: {r.name} ({r.designation}) @ {r.company}")
        print(f"  Email: {r.email}  |  Source Sheet: {r.sheet}")
        print(f"───────────────────────────────────────────────────────────────{Style.RESET_ALL}")

        # 1. Research
        print(f"  🧠 Researching {r.company}...")
        res = research_company(r.company, r.designation)
        print(f"  • Domain: {Fore.CYAN}{res.get('domain')}{Style.RESET_ALL}")
        print(f"  • Focus:  {res.get('engineering_focus')}")
        print(f"  • Hook:   {Fore.GREEN}{res.get('personal_hook')}{Style.RESET_ALL}")

        # 2. Compile Tailored Resume first to sync projects
        resume_pdf, selected_projects = get_tailored_resume_for_company(r.company, res.get('domain'))

        # 3. Email Draft (passing selected_projects)
        print(f"  ✍️  Drafting Human Cold Email...")
        email_data = generate_cold_email(r.name, r.designation, r.company, res, selected_projects)
        print(f"  • Subject: {Fore.WHITE}{Style.BRIGHT}{email_data['subject']}{Style.RESET_ALL}")
        print(f"\n{email_data['body']}\n")
        print(f"  📎 Tailored 1-Page Resume: {Fore.GREEN}{os.path.basename(resume_pdf) if resume_pdf else 'Base Resume'}{Style.RESET_ALL}\n")
        
        # Rate limit delay for free tier
        if i < limit:
            time.sleep(3.0)

    print(f"{Fore.GREEN}✓ Dry run complete. {min(limit, len(pending))} random targets previewed.{Style.RESET_ALL}\n")


def cmd_send_campaign(bypass_window: bool = False):
    """
    Run daily batch outreach of 15-20 emails.
    Enforces 7:00 AM – 9:00 AM window unless bypass_window=True.
    """
    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"  🚀  COLD OUTREACH CAMPAIGN — Daily Batch ({config.DAILY_LIMIT} max)")
    print(f"{'='*65}{Style.RESET_ALL}\n")

    if not bypass_window and not is_in_send_window():
        now_str = datetime.now().strftime("%I:%M %p")
        secs = get_seconds_until_next_window()
        hours = secs // 3600
        mins = (secs % 3600) // 60
        print(f"{Fore.YELLOW}⏸ Outside 7:00 AM – 9:00 AM sending window (current time: {now_str}).")
        print(f"Next window starts in {hours}h {mins}m.")
        print(f"To send immediately anyway, run with: python mail_agent.py --now{Style.RESET_ALL}\n")
        return

    recruiters = parse_excel(config.EXCEL_PATH, config.TARGET_SHEETS)
    sent = get_sent_emails()
    pending = [r for r in recruiters if r.email.lower() not in sent]

    if not pending:
        print(f"{Fore.GREEN}All recruiter contacts have already been emailed! 🎉{Style.RESET_ALL}\n")
        return

    # Randomize order so every daily batch is a diverse mix
    if config.RANDOMIZE_OUTREACH:
        random.shuffle(pending)

    print(f"Unsent contacts available: {len(pending)} | Today's Target: {config.DAILY_LIMIT} emails\n")

    sent_today = 0
    for r in pending:
        if sent_today >= config.DAILY_LIMIT:
            print(f"\n{Fore.GREEN}✅ Completed daily quota of {config.DAILY_LIMIT} emails! Stopping for today.{Style.RESET_ALL}\n")
            break

        # Stop if sending window closes and not in bypass mode
        if not bypass_window and not is_in_send_window():
            print(f"\n{Fore.YELLOW}⏰ Reached end of 7:00 AM – 9:00 AM window. Sent {sent_today} emails today.{Style.RESET_ALL}\n")
            break

        print(f"{Fore.WHITE}{Style.BRIGHT}[{sent_today+1}/{config.DAILY_LIMIT}] Processing {r.name} @ {r.company} ({r.email})...{Style.RESET_ALL}")

        # 1. Research Company
        res = research_company(r.company, r.designation)

        # 2. Get/Compile Tailored 1-Page Resume First to sync projects
        resume_path, selected_projects = get_tailored_resume_for_company(r.company, res.get("domain"))

        # 3. Draft Anti-AI Human Cold Email
        email_data = generate_cold_email(r.name, r.designation, r.company, res, selected_projects)

        # 4. Send Email
        success, err = send_email(r.email, email_data["subject"], email_data["body"], resume_path)

        if success:
            log_result(r.name, r.email, r.company, "sent", email_data["matched_project"], resume_path, subject=email_data["subject"])
            print(f"  {Fore.GREEN}✓ Sent successfully ({email_data['subject']}){Style.RESET_ALL}")
            sent_today += 1

            # Jitter delay between emails
            if sent_today < config.DAILY_LIMIT:
                delay = random.randint(config.DELAY_MIN, config.DELAY_MAX)
                print(f"  ⏳ Waiting {delay//60}m {delay%60}s before next outreach...\n")
                time.sleep(delay)
        else:
            log_result(r.name, r.email, r.company, "failed", email_data.get("matched_project", ""), resume_path, error=err, subject=email_data.get("subject", ""))
            print(f"  {Fore.RED}✗ Failed to send to {r.email}: {err}{Style.RESET_ALL}\n")

    print(f"\n{Fore.GREEN}Outreach batch complete. Total sent today: {sent_today}{Style.RESET_ALL}\n")


def cmd_schedule():
    """
    Run an automated continuous daemon.
    Automatically sleeps until 7:00 AM daily, executes 15-20 random emails, and repeats every day!
    """
    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"  ⏰  DAILY AUTOMATED SCHEDULER DAEMON (7:00 AM – 9:00 AM)")
    print(f"{'='*65}{Style.RESET_ALL}\n")
    print("Scheduler is active. It will automatically trigger daily outreach at 7:00 AM.\n")

    while True:
        if is_in_send_window():
            print(f"{Fore.GREEN}[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] In 7:00 AM – 9:00 AM window! Starting daily campaign...{Style.RESET_ALL}")
            cmd_send_campaign(bypass_window=False)

        secs = get_seconds_until_next_window()
        next_run = datetime.now() + timedelta(seconds=secs)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Sleeping until next window at {next_run.strftime('%Y-%m-%d %I:%M %p')} ({secs//3600}h {(secs%3600)//60}m)...")
        time.sleep(min(secs, 3600))  # Sleep up to 1 hour, then re-check


def cmd_test(to_email: str, company: str = "Example Tech"):
    """Send a test email with tailored resume to yourself."""
    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"  🧪  TEST EMAIL SEND — Testing Delivery to {to_email}")
    print(f"{'='*65}{Style.RESET_ALL}\n")

    print(f"  1. Researching sample company: {company}...")
    res = research_company(company, "Engineering Manager")

    print(f"  2. Generating tailored 1-page PDF resume for {company}...")
    resume_path, selected_projects = get_tailored_resume_for_company(company, res.get("domain"))

    print(f"  3. Drafting personalized email...")
    email_data = generate_cold_email(config.YOUR_FIRST_NAME, "Engineering Lead", company, res, selected_projects)

    print(f"\n{Fore.YELLOW}Previewing Outgoing Test Email:{Style.RESET_ALL}")
    print(f"Subject: {email_data['subject']}")
    print(f"Attachment: {resume_path}")
    print(f"{'─'*50}")
    print(email_data['body'])
    print(f"{'─'*50}\n")

    print(f"  4. Sending via Gmail SMTP to {to_email}...")
    success, err = send_email(to_email, email_data['subject'], email_data['body'], resume_path)

    if success:
        print(f"\n{Fore.GREEN}✅ Test email delivered successfully! Check your inbox.{Style.RESET_ALL}\n")
    else:
        print(f"\n{Fore.RED}❌ Test send failed: {err}{Style.RESET_ALL}\n")


def cmd_single_target(company: str, name: str, email: str, send_now: bool = False):
    """Target a specific company and recruiter directly."""
    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"  🎯 TARGETED OUTREACH: {name} @ {company} ({email})")
    print(f"{'='*65}{Style.RESET_ALL}\n")

    res = research_company(company)
    resume_path, selected_projects = get_tailored_resume_for_company(company, res.get('domain'))
    email_data = generate_cold_email(name, "Hiring Lead", company, res, selected_projects)

    print(f"Subject: {email_data['subject']}")
    print(f"Resume:  {os.path.basename(resume_path) if resume_path else 'None'}")
    print(f"{'─'*50}")
    print(email_data['body'])
    print(f"{'─'*50}\n")

    if send_now:
        print(f"  Sending to {email}...")
        ok, err = send_email(email, email_data['subject'], email_data['body'], resume_path)
        if ok:
            log_result(name, email, company, "sent", email_data["matched_project"], resume_path, subject=email_data["subject"])
            print(f"{Fore.GREEN}✅ Sent successfully!{Style.RESET_ALL}\n")
        else:
            log_result(name, email, company, "failed", email_data["matched_project"], resume_path, error=err, subject=email_data["subject"])
            print(f"{Fore.RED}❌ Send failed: {err}{Style.RESET_ALL}\n")


def cmd_stats():
    """Display comprehensive recruiter metrics across all sheets."""
    ensure_log_file()
    recruiters = parse_excel(config.EXCEL_PATH, config.TARGET_SHEETS)
    sent_emails = get_sent_emails()
    
    unique_cos = len(set(r.company for r in recruiters if r.company))
    pending_count = len([r for r in recruiters if r.email.lower() not in sent_emails])

    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"  📊  COLD OUTREACH CAMPAIGN METRICS")
    print(f"{'='*55}{Style.RESET_ALL}")
    print(f"  • Total Extracted Contacts: {Fore.WHITE}{Style.BRIGHT}{len(recruiters)}{Style.RESET_ALL}")
    print(f"  • Unique Companies:         {Fore.WHITE}{Style.BRIGHT}{unique_cos}{Style.RESET_ALL}")
    print(f"  • Target Sheets Parsed:     {Fore.CYAN}{', '.join(config.TARGET_SHEETS)}{Style.RESET_ALL}")
    print(f"  • Total Successfully Sent:  {Fore.GREEN}{len(sent_emails)}{Style.RESET_ALL}")
    print(f"  • Pending Unsent Contacts:  {Fore.YELLOW}{pending_count}{Style.RESET_ALL}")
    print(f"  • Daily Sending Window:     7:00 AM – 9:00 AM ({config.DAILY_LIMIT} emails/day)")
    print(f"  • Log File:                 {config.LOG_FILE}\n")


# ─── Main CLI ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Intelligent Cold Mailing Agent with Universal Excel Parser & Scheduler")
    parser.add_argument("--dry-run",   action="store_true", help="Preview random company research & email drafts without sending")
    parser.add_argument("--now",       action="store_true", help="Send today's batch immediately (bypass 7-9 AM time window)")
    parser.add_argument("--schedule",  action="store_true", help="Run automated continuous scheduler daemon (7-9 AM daily)")
    parser.add_argument("--stats",     action="store_true", help="Display recruiter and campaign statistics")
    parser.add_argument("--test",      metavar="EMAIL",     help="Send a test email with tailored resume to yourself")
    parser.add_argument("--company",   metavar="NAME",      help="Target a specific company name")
    parser.add_argument("--poc-name",  metavar="NAME",      default="Hiring Manager", help="Recruiter/POC name")
    parser.add_argument("--poc-email", metavar="EMAIL",     help="Recruiter/POC email")
    parser.add_argument("--send",      action="store_true", help="Send email when using --company")
    
    args = parser.parse_args()

    if args.stats:
        cmd_stats()
    elif args.dry_run:
        cmd_dry_run()
    elif args.schedule:
        cmd_schedule()
    elif args.now:
        cmd_send_campaign(bypass_window=True)
    elif args.test:
        cmd_test(args.test)
    elif args.company and args.poc_email:
        cmd_single_target(args.company, args.poc_name, args.poc_email, send_now=args.send)
    else:
        # Default: run campaign according to 7-9 AM window
        cmd_send_campaign(bypass_window=False)
