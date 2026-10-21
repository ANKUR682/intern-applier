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


@app.route("/api/cold_email/stats")
def cold_stats():
    try:
        from mail_agent import get_sent_emails, parse_excel
        import config as cold_config
        sent = get_sent_emails()
        recruiters = parse_excel(cold_config.EXCEL_PATH, cold_config.TARGET_SHEETS)
        return jsonify({
            "total_contacts": len(recruiters),
            "sent_count": len(sent),
            "pending_count": max(0, len(recruiters) - len(sent)),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cold_email/recruiters")
def cold_recruiters():
    try:
        from mail_agent import get_sent_emails, parse_excel
        import config as cold_config
        
        query = request.args.get("q", "").strip().lower()
        sheet_filter = request.args.get("sheet", "").strip()

        sent = get_sent_emails()
        recruiters = parse_excel(cold_config.EXCEL_PATH, cold_config.TARGET_SHEETS)
        
        results = []
        for r in recruiters:
            if sheet_filter and sheet_filter.lower() not in r.sheet.lower():
                continue
            if query and (query not in r.name.lower() and query not in r.company.lower() and query not in r.email.lower()):
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
        
        return jsonify({"recruiters": results[:100], "total": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cold_email/draft", methods=["POST"])
def cold_draft():
    try:
        data        = request.get_json(force=True)
        company     = data.get("company", "").strip()
        name        = data.get("name", "Hiring Manager").strip()
        designation = data.get("designation", "Engineering / Data Lead").strip()

        if not company:
            return jsonify({"error": "Company name is required."}), 400

        from company_researcher import research_company
        from email_generator import generate_cold_email
        from resume_attacher import get_tailored_resume_for_company

        # Step 1: Research Company
        research = research_company(company, designation)

        # Step 2: Check/Prepare Tailored 1-Page Resume first to sync projects
        resume_pdf, selected_projects = get_tailored_resume_for_company(company, research.get("domain"))

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
