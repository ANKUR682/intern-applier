"""app.py — Flask web UI for the InternApplier Resume Builder."""

import os
import sys
import json
import queue
import threading
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context

# Add Resume_Builder root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.build_resume import build_resume_pipeline
from scripts.utils import load_prompts

app = Flask(__name__)

# ─── In-memory build state ────────────────────────────────────────────────────
_build_queues: dict[str, queue.Queue] = {}
_build_results: dict[str, dict]       = {}


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/prompts")
def get_prompts():
    """Return all available tailoring prompts."""
    prompts = load_prompts()
    return jsonify(prompts)


@app.route("/api/build", methods=["POST"])
def build():
    data          = request.get_json(force=True)
    jd_text       = data.get("jd_text", "").strip()
    company       = data.get("company", "").strip()
    prompt_id     = data.get("prompt_id", "star_metrics").strip()
    custom_prompt = data.get("custom_prompt", "").strip()

    if not jd_text:
        return jsonify({"error": "Job description cannot be empty."}), 400

    build_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    q = queue.Queue()
    _build_queues[build_id] = q

    def progress(step: int, msg: str):
        q.put({"type": "progress", "step": step, "message": msg})

    def run():
        try:
            result = build_resume_pipeline(
                jd_text=jd_text,
                company=company,
                prompt_id=prompt_id,
                custom_prompt=custom_prompt,
                progress_callback=progress,
            )
            _build_results[build_id] = result
            q.put({
                "type":        "done",
                "folder_name": result["folder_name"],
                "pdf_path":    str(result["pdf_path"]),
                "ats_report":  result.get("ats_report", {}),
            })
        except Exception as exc:
            q.put({"type": "error", "message": str(exc)})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"build_id": build_id})


@app.route("/api/stream/<build_id>")
def stream(build_id: str):
    q = _build_queues.get(build_id)
    if q is None:
        return jsonify({"error": "Unknown build ID"}), 404

    def generate():
        while True:
            try:
                msg = q.get(timeout=45)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg["type"] in ("done", "error"):
                    break
            except queue.Empty:
                yield "data: {\"type\":\"ping\"}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/download/<build_id>")
def download(build_id: str):
    result = _build_results.get(build_id)
    if not result:
        return jsonify({"error": "Build not found or still running."}), 404
    pdf_path = Path(result["pdf_path"])
    if not pdf_path.exists():
        return jsonify({"error": "PDF file not found on disk."}), 404
    return send_file(str(pdf_path), as_attachment=True, download_name="resume.pdf")


# ─── Cold Outreach & Company Intelligence Routes ─────────────────────────────

# Add ColdMailingAgent to path
COLD_AGENT_DIR = Path(__file__).parent.parent.parent / "ColdMailingAgent"
if str(COLD_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(COLD_AGENT_DIR))

import config as cold_config
from werkzeug.utils import secure_filename

# Active spreadsheet state
_spreadsheet_state = {
    "active_path": str(cold_config.EXCEL_PATH),
    "filename": Path(cold_config.EXCEL_PATH).name,
    "target_sheets": ["ALL"],
    "is_custom": False,
}

# Auto-Pilot Batch State
_batch_lock = threading.Lock()
_batch_state = {
    "running": False,
    "batch_id": None,
    "total": 0,
    "processed": 0,
    "sent": 0,
    "failed": 0,
    "current_target": None,
    "current_step": "idle",
    "stop_requested": False,
    "dry_run": False,
    "logs": [],
    "results": [],
}


@app.route("/api/cold_email/upload", methods=["POST"])
def cold_upload_sheet():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded."}), 400
        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "No file selected."}), 400

        filename = secure_filename(file.filename)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ["xlsx", "xls", "csv"]:
            return jsonify({"error": "Invalid format. Please upload an Excel (.xlsx, .xls) or CSV (.csv) file."}), 400

        upload_dir = COLD_AGENT_DIR / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_path = upload_dir / filename
        file.save(str(saved_path))

        from mail_agent import parse_excel, get_sent_emails
        recruiters = parse_excel(str(saved_path), ["ALL"])
        if not recruiters:
            return jsonify({"error": "No valid contacts or email columns could be detected in this sheet."}), 400

        _spreadsheet_state["active_path"] = str(saved_path)
        _spreadsheet_state["filename"] = file.filename
        _spreadsheet_state["target_sheets"] = ["ALL"]
        _spreadsheet_state["is_custom"] = True

        sent = get_sent_emails()
        pending_count = sum(1 for r in recruiters if r.email.lower() not in sent)

        sample = [{
            "name": r.name,
            "company": r.company,
            "designation": r.designation,
            "email": r.email,
            "linkedin": r.linkedin,
        } for r in recruiters[:5]]

        return jsonify({
            "success": True,
            "filename": file.filename,
            "total_contacts": len(recruiters),
            "pending_count": pending_count,
            "sample": sample,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cold_email/active_sheet")
def cold_active_sheet():
    try:
        from mail_agent import parse_excel, get_sent_emails
        recruiters = parse_excel(_spreadsheet_state["active_path"], _spreadsheet_state["target_sheets"])
        sent = get_sent_emails()
        pending = sum(1 for r in recruiters if r.email.lower() not in sent)
        return jsonify({
            "filename": _spreadsheet_state["filename"],
            "is_custom": _spreadsheet_state["is_custom"],
            "total_contacts": len(recruiters),
            "sent_count": len(sent),
            "pending_count": pending,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cold_email/reset_sheet", methods=["POST"])
def cold_reset_sheet():
    _spreadsheet_state["active_path"] = str(cold_config.EXCEL_PATH)
    _spreadsheet_state["filename"] = Path(cold_config.EXCEL_PATH).name
    _spreadsheet_state["target_sheets"] = ["ALL"]
    _spreadsheet_state["is_custom"] = False
    return jsonify({"success": True, "filename": _spreadsheet_state["filename"]})


@app.route("/api/cold_email/stats")
def cold_stats():
    try:
        from mail_agent import get_sent_emails, parse_excel
        sent = get_sent_emails()
        recruiters = parse_excel(_spreadsheet_state["active_path"], _spreadsheet_state["target_sheets"])
        return jsonify({
            "total_contacts": len(recruiters),
            "sent_count": len(sent),
            "pending_count": max(0, len(recruiters) - len(sent)),
            "active_sheet": _spreadsheet_state["filename"],
            "is_custom": _spreadsheet_state["is_custom"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cold_email/recruiters")
def cold_recruiters():
    try:
        from mail_agent import get_sent_emails, parse_excel

        query = request.args.get("q", "").strip().lower()
        sheet_filter = request.args.get("sheet", "").strip()

        sent = get_sent_emails()
        recruiters = parse_excel(_spreadsheet_state["active_path"], _spreadsheet_state["target_sheets"])

        results = []
        for r in recruiters:
            if sheet_filter and sheet_filter.lower() not in r.sheet.lower():
                continue
            if query and (query not in r.name.lower() and query not in r.company.lower() and query not in r.email.lower() and query not in r.designation.lower()):
                continue

            results.append({
                "name": r.name,
                "designation": r.designation,
                "company": r.company,
                "email": r.email,
                "linkedin": r.linkedin,
                "sheet": r.sheet,
                "is_sent": r.email.lower() in sent,
            })

        return jsonify({
            "recruiters": results[:100],
            "total": len(results),
            "active_sheet": _spreadsheet_state["filename"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cold_email/draft", methods=["POST"])
def cold_draft():
    try:
        data        = request.get_json(force=True)
        company     = data.get("company", "").strip()
        name        = data.get("name", "Hiring Manager").strip()
        designation = data.get("designation", "Engineering / Data Lead").strip()
        prompt_id   = data.get("prompt_id", "google_xyz_surgeon").strip()

        if not company:
            return jsonify({"error": "Company name is required."}), 400

        from company_researcher import research_company
        from email_generator import generate_cold_email
        from resume_attacher import get_tailored_resume_for_company

        # Step 1: Research Company
        research = research_company(company, designation)

        # Step 2: Check/Prepare Tailored 1-Page Resume first to sync projects
        resume_pdf, selected_projects = get_tailored_resume_for_company(
            company,
            domain=research.get("domain", "Technology"),
            prompt_id=prompt_id,
        )

        # Step 3: Draft Anti-AI Human Cold Email (synced with resume)
        email_data = generate_cold_email(name, designation, company, research, selected_projects)

        return jsonify({
            "subject": email_data["subject"],
            "body": email_data["body"],
            "research": research,
            "resume_path": resume_pdf,
            "resume_filename": os.path.basename(resume_pdf) if resume_pdf else "",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cold_email/send", methods=["POST"])
def cold_send():
    try:
        data        = request.get_json(force=True)
        to_email    = data.get("to_email", "").strip()
        subject     = data.get("subject", "").strip()
        body        = data.get("body", "").strip()
        resume_path = data.get("resume_path", "").strip()
        name        = data.get("name", "").strip()
        company     = data.get("company", "").strip()

        if not to_email or not subject or not body:
            return jsonify({"error": "Recipient email, subject, and body are required."}), 400

        from mail_agent import send_email, log_result

        success, err = send_email(to_email, subject, body, resume_path)
        if success:
            log_result(name, to_email, company, "sent", "", resume_path)
            return jsonify({"success": True, "message": f"Email successfully delivered to {to_email}"})
        else:
            log_result(name, to_email, company, "failed", "", resume_path, err)
            return jsonify({"success": False, "error": err}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Automated 1-by-1 Batch Outreach Engine ──────────────────────────────────

def _auto_batch_worker(limit: int, delay_seconds: int, dry_run: bool, filter_query: str, prompt_id: str):
    global _batch_state
    try:
        from mail_agent import get_sent_emails, parse_excel, send_email, log_result
        from company_researcher import research_company
        from email_generator import generate_cold_email
        from resume_attacher import get_tailored_resume_for_company

        active_path = _spreadsheet_state["active_path"]
        active_sheets = _spreadsheet_state["target_sheets"]

        all_recruiters = parse_excel(active_path, active_sheets)
        sent = get_sent_emails()
        pending = [r for r in all_recruiters if r.email.lower() not in sent]

        if filter_query:
            fq = filter_query.lower()
            pending = [r for r in pending if fq in r.company.lower() or fq in r.name.lower() or fq in r.designation.lower() or fq in r.email.lower()]

        targets = pending[:limit] if limit > 0 else pending

        with _batch_lock:
            _batch_state["total"] = len(targets)
            _batch_state["processed"] = 0
            _batch_state["sent"] = 0
            _batch_state["failed"] = 0
            _batch_state["running"] = True
            _batch_state["stop_requested"] = False
            _batch_state["dry_run"] = dry_run
            _batch_state["logs"].append(f"Starting Auto-Pilot batch for {len(targets)} contacts (Delay: {delay_seconds}s | Mode: {'Dry Run' if dry_run else 'Live Send'}).")

        for idx, r in enumerate(targets, start=1):
            if _batch_state.get("stop_requested"):
                _batch_state["logs"].append("Auto-Pilot stopped by user.")
                break

            with _batch_lock:
                _batch_state["current_target"] = {
                    "index": idx,
                    "total": len(targets),
                    "name": r.name,
                    "company": r.company,
                    "email": r.email,
                    "designation": r.designation,
                }
                _batch_state["current_step"] = "researching"
                _batch_state["logs"].append(f"[{idx}/{len(targets)}] 🧠 Researching {r.company} with Gemini...")

            # 1. Company Research
            try:
                research = research_company(r.company, r.designation)
            except Exception as re_err:
                research = {
                    "company": r.company,
                    "domain": "Technology & Data",
                    "core_product": f"Core platforms at {r.company}",
                    "engineering_focus": "Data analytics, machine learning, and scalable systems",
                    "personal_hook": f"I really admire how {r.company} scales engineering solutions.",
                }

            if _batch_state.get("stop_requested"):
                break

            # 2. Tailor 1-page CV & compile to PDF
            with _batch_lock:
                _batch_state["current_step"] = "tailoring_cv"
                _batch_state["logs"].append(f"[{idx}/{len(targets)}] 📄 Compiling tailored 1-page CV for {r.company} ({research.get('domain', 'Tech')})...")

            try:
                resume_pdf, selected_projects = get_tailored_resume_for_company(
                    r.company,
                    domain=research.get("domain", "Data Science & Machine Learning"),
                    prompt_id=prompt_id or "google_xyz_surgeon",
                )
            except Exception as cv_err:
                resume_pdf, selected_projects = "", ["FraudSentinel: Anomaly Detection", "Financial Time Series Engine"]
                _batch_state["logs"].append(f"[{idx}/{len(targets)}] ⚠ Note on CV: {cv_err}")

            if _batch_state.get("stop_requested"):
                break

            # 3. Draft Cold Email
            with _batch_lock:
                _batch_state["current_step"] = "drafting_email"
                _batch_state["logs"].append(f"[{idx}/{len(targets)}] ✍️ Drafting personalized cold email...")

            try:
                email_data = generate_cold_email(r.name, r.designation, r.company, research, selected_projects)
            except Exception as em_err:
                email_data = {
                    "subject": f"Question regarding {r.company}'s data engineering / intern query",
                    "body": f"Hi {r.name.split()[0] if r.name else 'Hiring Lead'},\n\nI saw what {r.company} is building in {research.get('domain', 'tech')} and would love to contribute to your data/ML pipelines.",
                    "matched_project": "FraudSentinel",
                }

            if _batch_state.get("stop_requested"):
                break

            # 4. Send Email (or dry run)
            with _batch_lock:
                _batch_state["current_step"] = "sending"

            if dry_run:
                success = True
                err = ""
                with _batch_lock:
                    _batch_state["logs"].append(f"[{idx}/{len(targets)}] 🔍 [Dry Run] Ready to send to {r.email} with '{os.path.basename(resume_pdf) if resume_pdf else 'Base Resume'}'")
            else:
                with _batch_lock:
                    _batch_state["logs"].append(f"[{idx}/{len(targets)}] 📤 Sending email to {r.email} via Gmail SMTP...")
                success, err = send_email(r.email, email_data["subject"], email_data["body"], resume_pdf)

            # 5. Log & record result
            result_item = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "name": r.name,
                "company": r.company,
                "email": r.email,
                "subject": email_data.get("subject", ""),
                "body": email_data.get("body", ""),
                "resume_pdf": resume_pdf,
                "resume_name": os.path.basename(resume_pdf) if resume_pdf else "",
                "status": "sent" if success else "failed",
                "error": err,
                "dry_run": dry_run,
            }

            with _batch_lock:
                _batch_state["results"].append(result_item)
                _batch_state["processed"] += 1
                if success:
                    _batch_state["sent"] += 1
                    if not dry_run:
                        log_result(r.name, r.email, r.company, "sent", email_data.get("matched_project", ""), resume_pdf)
                    _batch_state["logs"].append(f"[{idx}/{len(targets)}] ✓ Successfully processed {r.name} @ {r.company}!")
                else:
                    _batch_state["failed"] += 1
                    if not dry_run:
                        log_result(r.name, r.email, r.company, "failed", email_data.get("matched_project", ""), resume_pdf, err)
                    _batch_state["logs"].append(f"[{idx}/{len(targets)}] ✗ Failed for {r.email}: {err}")

            # 6. Delay interval
            if idx < len(targets) and not _batch_state.get("stop_requested"):
                with _batch_lock:
                    _batch_state["current_step"] = "waiting"
                    _batch_state["logs"].append(f"⏳ Waiting {delay_seconds}s before next outreach...")
                for _ in range(delay_seconds):
                    if _batch_state.get("stop_requested"):
                        break
                    time.sleep(1)

        with _batch_lock:
            _batch_state["current_step"] = "completed"
            _batch_state["logs"].append(f"🎉 Auto-Pilot batch complete! Sent: {_batch_state['sent']}, Failed: {_batch_state['failed']}.")

    except Exception as exc:
        with _batch_lock:
            _batch_state["logs"].append(f"❌ Batch error: {str(exc)}")
            _batch_state["current_step"] = "error"
    finally:
        with _batch_lock:
            _batch_state["running"] = False


@app.route("/api/cold_email/batch_start", methods=["POST"])
def cold_batch_start():
    global _batch_state
    if _batch_state.get("running"):
        return jsonify({"error": "An outreach batch is already currently running."}), 400

    data          = request.get_json(force=True) or {}
    limit         = int(data.get("limit", 10))
    delay_seconds = int(data.get("delay_seconds", 15))
    dry_run       = bool(data.get("dry_run", False))
    filter_query  = str(data.get("filter_query", "")).strip()
    prompt_id     = str(data.get("prompt_id", "google_xyz_surgeon")).strip()

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    with _batch_lock:
        _batch_state = {
            "running": True,
            "batch_id": batch_id,
            "total": 0,
            "processed": 0,
            "sent": 0,
            "failed": 0,
            "current_target": None,
            "current_step": "initializing",
            "stop_requested": False,
            "dry_run": dry_run,
            "logs": [],
            "results": [],
        }

    threading.Thread(
        target=_auto_batch_worker,
        args=(limit, delay_seconds, dry_run, filter_query, prompt_id),
        daemon=True,
    ).start()

    return jsonify({"success": True, "batch_id": batch_id})


@app.route("/api/cold_email/batch_status")
def cold_batch_status():
    with _batch_lock:
        return jsonify(dict(_batch_state))


@app.route("/api/cold_email/batch_stop", methods=["POST"])
def cold_batch_stop():
    with _batch_lock:
        if _batch_state.get("running"):
            _batch_state["stop_requested"] = True
            _batch_state["logs"].append("🛑 Stop request received. Finishing current action and stopping...")
            return jsonify({"success": True, "message": "Stopping batch outreach."})
        return jsonify({"success": False, "message": "No active batch is currently running."})


@app.route("/api/cold_email/download_resume")
def cold_download_resume():
    path = request.args.get("path", "").strip()
    if not path:
        return jsonify({"error": "Path required"}), 400
    pdf_path = Path(path)
    if not pdf_path.exists():
        return jsonify({"error": "PDF file not found"}), 404
    return send_file(str(pdf_path), as_attachment=True, download_name=pdf_path.name)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from scripts.utils import get_config
    cfg = get_config()
    print("\n  InternApplier Resume Builder")
    print(f"  Running at http://{cfg['web_host']}:{cfg['web_port']}\n")
    app.run(
        host=cfg.get("web_host", "127.0.0.1"),
        port=cfg.get("web_port", 5000),
        debug=cfg.get("debug", True),
        threaded=True,
    )
