/* script.js — Resume Builder Web UI logic (1-Page ATS & Prompt Selection) */

let currentEventSource = null;
let currentBuildId     = null;
let cachedPrompts      = {};

// ── Step helpers ──────────────────────────────────────────────

function setStepState(step, state, msg = null) {
  const el  = document.getElementById(`step-${step}`);
  const msgEl = document.getElementById(`step-${step}-msg`);
  if (!el) return;
  el.classList.remove("running", "done", "error");
  if (state) el.classList.add(state);
  if (msg && msgEl) msgEl.textContent = msg;
}

function resetSteps() {
  for (let i = 1; i <= 6; i++) {
    setStepState(i, null, "Waiting...");
  }
}

// ── Log helpers ───────────────────────────────────────────────

function appendLog(msg, type = "default") {
  const box = document.getElementById("logBox");
  const placeholder = box.querySelector(".log-placeholder");
  if (placeholder) placeholder.remove();

  const line = document.createElement("span");
  line.className = `log-entry${type !== "default" ? " " + type : ""}`;
  const now = new Date().toLocaleTimeString("en-US", { hour12: false });
  line.textContent = `[${now}]  ${msg}`;
  box.appendChild(line);
  box.appendChild(document.createTextNode("\n"));
  box.scrollTop = box.scrollHeight;
}

function clearLog() {
  const box = document.getElementById("logBox");
  box.innerHTML = '<span class="log-placeholder">Log output will appear here during the build...</span>';
}

// ── Header status ─────────────────────────────────────────────

function setHeaderStatus(state, text) {
  const dot  = document.querySelector(".status-dot");
  const label = document.querySelector(".status-text");
  dot.className  = "status-dot " + state;
  label.textContent = text;
}

// ── Prompt Strategy Management ────────────────────────────────

async function loadPrompts() {
  try {
    const res = await fetch("/api/prompts");
    const data = await res.json();
    cachedPrompts = data;

    const selector = document.getElementById("promptSelector");
    selector.innerHTML = "";

    for (const [key, item] of Object.entries(data)) {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = item.name;
      selector.appendChild(opt);
    }

    onPromptChange();
  } catch (err) {
    console.error("Failed to load prompt presets:", err);
    document.getElementById("promptDesc").textContent = "Using default STAR & Impact metric prompt.";
  }
}

function onPromptChange() {
  const selector = document.getElementById("promptSelector");
  const key = selector.value;
  const item = cachedPrompts[key];
  if (!item) return;

  document.getElementById("promptDesc").textContent = item.description || "";
  document.getElementById("customPromptInput").value = item.template || "";
}

function toggleCustomPrompt() {
  const wrapper = document.getElementById("customPromptWrapper");
  const icon = document.getElementById("togglePromptIcon");
  if (wrapper.style.display === "none") {
    wrapper.style.display = "flex";
    icon.textContent = "▾";
  } else {
    wrapper.style.display = "none";
    icon.textContent = "▸";
  }
}

function resetPromptToDefault() {
  const selector = document.getElementById("promptSelector");
  const key = selector.value;
  const item = cachedPrompts[key];
  if (item) {
    document.getElementById("customPromptInput").value = item.template || "";
  }
}

// ── Main build function ───────────────────────────────────────

async function startBuild() {
  const jdText       = document.getElementById("jdInput").value.trim();
  const company      = document.getElementById("companyInput").value.trim();
  const promptId     = document.getElementById("promptSelector").value;
  const customPrompt = document.getElementById("customPromptInput").value.trim();

  if (!jdText) {
    const el = document.getElementById("jdInput");
    el.focus();
    el.style.borderColor = "var(--error)";
    setTimeout(() => { el.style.borderColor = ""; }, 1500);
    return;
  }

  // Reset UI
  resetSteps();
  clearLog();
  document.getElementById("outputCard").style.display = "none";
  document.getElementById("errorCard").style.display  = "none";

  // Disable button
  const btn     = document.getElementById("buildBtn");
  const btnText = document.getElementById("buildBtnText");
  btn.disabled  = true;
  btnText.textContent = "Building 1-Page Resume...";
  setHeaderStatus("running", "Building 1-Page Resume...");

  if (currentEventSource) { currentEventSource.close(); }

  // POST to /api/build
  let buildId;
  try {
    const res  = await fetch("/api/build", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        jd_text: jdText,
        company: company,
        prompt_id: promptId,
        custom_prompt: customPrompt,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Server error");
    buildId = data.build_id;
    currentBuildId = buildId;
  } catch (err) {
    showError(err.message);
    resetBtn();
    return;
  }

  // Open SSE stream
  const es = new EventSource(`/api/stream/${buildId}`);
  currentEventSource = es;
  let activeStep = 0;

  es.onmessage = (event) => {
    const msg = JSON.parse(event.data);

    if (msg.type === "ping") return;

    if (msg.type === "progress") {
      const step = msg.step;

      // Mark previous step done
      if (activeStep && activeStep !== step) {
        setStepState(activeStep, "done");
      }

      // If same step gets another message, update it
      if (activeStep !== step) {
        setStepState(step, "running", msg.message);
        activeStep = step;
      } else {
        const msgEl = document.getElementById(`step-${step}-msg`);
        if (msgEl) msgEl.textContent = msg.message;
      }

      appendLog(msg.message);
    }

    if (msg.type === "done") {
      setStepState(activeStep, "done");
      for (let i = 1; i <= 6; i++) setStepState(i, "done");

      const folderName = msg.folder_name;
      document.getElementById("outputFolderName").textContent =
        `Resume_Output / ${folderName} / resume.pdf`;
      document.getElementById("downloadBtn").href = `/api/download/${buildId}`;
      document.getElementById("outputCard").style.display = "";

      // ── Populate ATS Dashboard ──
      const ats = msg.ats_report || {};
      if (ats.overall_score) {
        document.getElementById("atsCompositeScore").textContent = ats.overall_score;
        document.getElementById("atsGradeBadge").textContent = ats.grade || "Passing";

        // Render 3 Scanner Engines
        const grid = document.getElementById("atsEnginesGrid");
        grid.innerHTML = "";

        (ats.engines || []).forEach(eng => {
          const card = document.createElement("div");
          card.className = "ats-engine-card";
          card.innerHTML = `
            <div class="ats-engine-name">${eng.engine_name}</div>
            <div class="ats-engine-score">${eng.score}<span style="font-size:0.65rem;font-weight:400;color:var(--text-faint)">/100</span></div>
          `;
          grid.appendChild(card);
        });

        // Keywords
        const eng1 = (ats.engines || [])[0] || {};
        const matched = eng1.matched_keywords || [];
        const missing = eng1.missing_keywords || [];

        if (matched.length > 0 || missing.length > 0) {
          const tagsSection = document.getElementById("atsTagsSection");
          tagsSection.style.display = "flex";

          const mContainer = document.getElementById("atsMatchedKeywords");
          mContainer.innerHTML = matched.map(k => `<span class="ats-tag matched">✓ ${k}</span>`).join(" ");

          const missContainer = document.getElementById("atsMissingKeywords");
          missContainer.innerHTML = missing.length > 0
            ? missing.map(k => `<span class="ats-tag missing">+ ${k}</span>`).join(" ")
            : `<span style="font-size:0.68rem;color:var(--text-faint)">All target keywords covered!</span>`;
        }
      }

      appendLog(`Done! 1-Page Resume & ATS Audit saved to Resume_Output/${folderName}/`, "success");
      setHeaderStatus("done", `Done · ATS ${ats.overall_score || '--'}/100`);
      resetBtn("Build Another Resume");
      es.close();
    }

    if (msg.type === "error") {
      setStepState(activeStep, "error", msg.message);
      showError(msg.message);
      appendLog("Error: " + msg.message, "error");
      setHeaderStatus("error", "Failed");
      resetBtn();
      es.close();
    }
  };

  es.onerror = () => {
    showError("Connection to server lost. Is the Flask app running?");
    setHeaderStatus("error", "Disconnected");
    resetBtn();
    es.close();
  };
}

function showError(msg) {
  document.getElementById("errorMsg").textContent = msg;
  document.getElementById("errorCard").style.display = "";
}

function resetBtn(label = "Build 1-Page Resume") {
  const btn     = document.getElementById("buildBtn");
  const btnText = document.getElementById("buildBtnText");
  btn.disabled  = false;
  btnText.textContent = label;
}

// ── Tab Switcher ────────────────────────────────────────────

function switchTab(tab) {
  const resumeBtn = document.getElementById("tabResumeBtn");
  const coldBtn   = document.getElementById("tabColdEmailBtn");
  const resumeTab = document.getElementById("tabResumeContent");
  const coldTab   = document.getElementById("tabColdEmailContent");

  if (tab === "resume") {
    resumeBtn.classList.add("active");
    coldBtn.classList.remove("active");
    resumeTab.style.display = "";
    coldTab.style.display = "none";
  } else {
    coldBtn.classList.add("active");
    resumeBtn.classList.remove("active");
    coldTab.style.display = "";
    resumeTab.style.display = "none";
    loadActiveSheetInfo();
    if (!recruiterCache.length) {
      loadRecruiters();
    }
  }
}

// ── Cold Outreach & Auto-Pilot Engine ───────────────────────

let recruiterCache = [];
let activeRecruiter = null;
let currentDraftData = null;
let batchPollTimer = null;
let lastLogCount = 0;

async function loadActiveSheetInfo() {
  try {
    const res = await fetch("/api/cold_email/active_sheet");
    const data = await res.json();
    if (res.ok) {
      const nameEl = document.getElementById("activeSheetName");
      const metaEl = document.getElementById("activeSheetMeta");
      const resetBtn = document.getElementById("resetSheetBtn");

      if (nameEl) nameEl.textContent = data.filename || "No sheet selected";
      if (metaEl) {
        metaEl.textContent = `${(data.total_contacts || 0).toLocaleString()} contacts · ${data.sent_count || 0} sent · ${data.pending_count || 0} pending`;
      }
      if (resetBtn) resetBtn.style.display = data.is_custom ? "" : "none";
    }
  } catch (e) {
    console.error("Failed to load active sheet info:", e);
  }
}

async function handleSheetUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  const metaEl = document.getElementById("activeSheetMeta");
  const origMeta = metaEl.textContent;
  metaEl.textContent = `⏳ Uploading and extracting contacts from ${file.name}...`;

  try {
    const res = await fetch("/api/cold_email/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");

    alert(`✓ Successfully loaded "${data.filename}"!\nDetected ${data.total_contacts} contacts (${data.pending_count} pending outreach).`);
    await loadActiveSheetInfo();
    await loadRecruiters("");
  } catch (err) {
    alert("Upload Error: " + err.message);
    metaEl.textContent = origMeta;
  } finally {
    event.target.value = "";
  }
}

async function resetSheet() {
  try {
    const res = await fetch("/api/cold_email/reset_sheet", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      await loadActiveSheetInfo();
      await loadRecruiters("");
    }
  } catch (err) {
    console.error("Reset error:", err);
  }
}

async function startBatchOutreach() {
  const limit = parseInt(document.getElementById("batchLimitSelect").value, 10);
  const delay = parseInt(document.getElementById("batchDelaySelect").value, 10);
  const mode = document.getElementById("batchModeSelect").value;
  const isDryRun = mode === "dry_run";
  const query = document.getElementById("recruiterSearchInput").value.trim();

  const promptSelector = document.getElementById("promptSelector");
  const promptId = promptSelector ? promptSelector.value : "google_xyz_surgeon";

  const confirmMsg = isDryRun
    ? `Start DRY RUN for ${limit === 0 ? 'ALL' : limit} contacts?\n(Generates tailored 1-page CVs and email drafts without sending live emails)`
    : `Start LIVE Auto-Pilot outreach for ${limit === 0 ? 'ALL' : limit} contacts?\nEach contact will receive a freshly compiled 1-page PDF CV and personalized cold email with a ${delay}s interval.`;

  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetch("/api/cold_email/batch_start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        limit: limit,
        delay_seconds: delay,
        dry_run: isDryRun,
        filter_query: query,
        prompt_id: promptId,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to start batch");

    document.getElementById("autopilotMonitorCard").style.display = "";
    document.getElementById("startBatchBtn").style.display = "none";
    document.getElementById("stopBatchBtn").style.display = "";
    const placeholder = document.getElementById("coldPlaceholderCard");
    if (placeholder) placeholder.style.display = "none";

    clearInterval(batchPollTimer);
    batchPollTimer = setInterval(pollBatchStatus, 1500);
    pollBatchStatus();

  } catch (err) {
    alert("Failed to start Auto-Pilot: " + err.message);
  }
}

async function stopBatchOutreach() {
  const stopBtn = document.getElementById("stopBatchBtn");
  stopBtn.disabled = true;
  stopBtn.textContent = "Stopping...";

  try {
    await fetch("/api/cold_email/batch_stop", { method: "POST" });
  } catch (err) {
    console.error(err);
  } finally {
    setTimeout(() => {
      stopBtn.disabled = false;
      stopBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="6" y="6" width="12" height="12"/></svg> Stop Auto-Pilot`;
    }, 1500);
  }
}

async function pollBatchStatus() {
  try {
    const res = await fetch("/api/cold_email/batch_status");
    const data = await res.json();

    const progressBar = document.getElementById("monitorProgressBar");
    const counterEl   = document.getElementById("monitorCounter");
    const statusText  = document.getElementById("monitorStatusText");
    const pulse       = document.getElementById("monitorPulse");
    const targetName  = document.getElementById("currentTargetName");
    const targetComp  = document.getElementById("currentTargetCompany");
    const terminal    = document.getElementById("autopilotTerminal");

    const total = data.total || 0;
    const processed = data.processed || 0;
    const pct = total > 0 ? Math.round((processed / total) * 100) : (data.running ? 10 : 0);
    if (progressBar) progressBar.style.width = `${pct}%`;

    if (counterEl) {
      counterEl.textContent = `${processed} / ${total} Processed · ${data.sent} Sent · ${data.failed} Failed`;
    }

    if (data.running) {
      if (statusText) statusText.textContent = data.dry_run ? "Auto-Pilot Preview Active (Dry Run)" : "Auto-Pilot Active (Live Send)";
      if (pulse) pulse.style.background = "#3b82f6";
      document.getElementById("startBatchBtn").style.display = "none";
      document.getElementById("stopBatchBtn").style.display = "";
    } else {
      if (statusText) statusText.textContent = data.current_step === "completed" ? "Auto-Pilot Complete 🎉" : "Auto-Pilot Stopped / Idle";
      if (pulse) pulse.style.background = data.current_step === "completed" ? "#10b981" : "#94a3b8";
      document.getElementById("startBatchBtn").style.display = "";
      document.getElementById("stopBatchBtn").style.display = "none";
      clearInterval(batchPollTimer);
    }

    // Active Target Display
    if (data.current_target) {
      if (targetName) targetName.textContent = `${data.current_target.name} (${data.current_target.designation || 'Lead'})`;
      if (targetComp) targetComp.textContent = `@ ${data.current_target.company} [${data.current_target.index}/${data.current_target.total}]`;
    }

    // Step Flow Highlighting
    const pills = {
      "researching": "pill-research",
      "tailoring_cv": "pill-cv",
      "drafting_email": "pill-draft",
      "sending": "pill-send",
    };
    ["pill-research", "pill-cv", "pill-draft", "pill-send"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.classList.remove("active");
    });
    if (pills[data.current_step]) {
      const activeEl = document.getElementById(pills[data.current_step]);
      if (activeEl) activeEl.classList.add("active");
    }

    // Terminal Logs
    if (data.logs && data.logs.length !== lastLogCount && terminal) {
      lastLogCount = data.logs.length;
      terminal.innerHTML = "";
      data.logs.slice(-25).forEach(line => {
        const div = document.createElement("div");
        div.className = "terminal-line";
        div.textContent = line;
        terminal.appendChild(div);
      });
      terminal.scrollTop = terminal.scrollHeight;
    }

    // Results Table
    if (data.results && data.results.length > 0) {
      const tableWrap = document.getElementById("resultsTableWrap");
      if (tableWrap) tableWrap.style.display = "";
      const tbody = document.getElementById("batchResultsBody");
      if (tbody) {
        tbody.innerHTML = "";
        data.results.slice().reverse().forEach(r => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><strong>${r.name}</strong></td>
            <td>${r.company}</td>
            <td><code>${r.email}</code></td>
            <td><span class="status-tag ${r.status}">${r.status.toUpperCase()}${r.dry_run ? ' (DRY)' : ''}</span></td>
            <td>
              ${r.resume_pdf
                ? `<a href="/api/cold_email/download_resume?path=${encodeURIComponent(r.resume_pdf)}" target="_blank" class="resume-download-link">📄 ${r.resume_name || 'Download CV'}</a>`
                : '<span style="color:var(--text-faint)">Base</span>'}
            </td>
          `;
          tbody.appendChild(tr);
        });
      }
    }

  } catch (err) {
    console.error("Batch poll error:", err);
  }
}

async function loadRecruiters(query = "") {
  const wrap = document.getElementById("recruiterListWrap");
  try {
    const url = `/api/cold_email/recruiters${query ? '?q=' + encodeURIComponent(query) : ''}`;
    const res = await fetch(url);
    const data = await res.json();
    recruiterCache = data.recruiters || [];
    renderRecruiters(recruiterCache);
  } catch (err) {
    wrap.innerHTML = `<div class="recruiter-list-loading" style="color:var(--error);">Failed to load Excel recruiter database: ${err.message}</div>`;
  }
}

function renderRecruiters(list) {
  const wrap = document.getElementById("recruiterListWrap");
  if (!list.length) {
    wrap.innerHTML = `<div class="recruiter-list-loading">No matching recruiters found.</div>`;
    return;
  }

  wrap.innerHTML = "";
  list.forEach((r, idx) => {
    const item = document.createElement("div");
    item.className = "recruiter-item";
    if (activeRecruiter && activeRecruiter.email === r.email) {
      item.classList.add("selected");
    }

    item.innerHTML = `
      <div class="recruiter-item-main">
        <div class="recruiter-item-name">${r.name}</div>
        <div class="recruiter-item-sub">${r.designation || 'Lead'} · <strong>${r.company}</strong></div>
      </div>
      <div class="recruiter-item-badge ${r.is_sent ? 'sent' : ''}">
        ${r.is_sent ? '✓ Sent' : r.sheet ? r.sheet.replace('Entrepreneurship ', '') : 'Pending'}
      </div>
    `;

    item.onclick = () => selectRecruiter(r, item);
    wrap.appendChild(item);
  });
}

function selectRecruiter(r, itemEl) {
  activeRecruiter = r;
  document.querySelectorAll(".recruiter-item").forEach(el => el.classList.remove("selected"));
  if (itemEl) itemEl.classList.add("selected");

  document.getElementById("targetCompany").value     = r.company || "";
  document.getElementById("targetName").value        = r.name || "";
  document.getElementById("targetEmail").value       = r.email || "";
  document.getElementById("targetDesignation").value = r.designation || "";
}

let searchDebounce = null;
function handleRecruiterSearch() {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    const q = document.getElementById("recruiterSearchInput").value.trim();
    loadRecruiters(q);
  }, 250);
}

function clearRecruiterSearch() {
  document.getElementById("recruiterSearchInput").value = "";
  loadRecruiters("");
}

async function researchAndDraftEmail() {
  const company     = document.getElementById("targetCompany").value.trim();
  const name        = document.getElementById("targetName").value.trim();
  const email       = document.getElementById("targetEmail").value.trim();
  const designation = document.getElementById("targetDesignation").value.trim();

  if (!company) {
    alert("Please enter or select a Company Name.");
    return;
  }

  const btn = document.getElementById("researchDraftBtn");
  btn.disabled = true;
  btn.innerHTML = `<span class="spin">⏳</span> Researching ${company} & Drafting...`;

  try {
    const res = await fetch("/api/cold_email/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company, name, designation }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to generate outreach package");

    currentDraftData = data;

    // Show Intel Card
    const intel = data.research || {};
    document.getElementById("intelDomain").textContent    = intel.domain || "Technology";
    document.getElementById("intelProduct").textContent   = intel.core_product || `${company} core platform.`;
    document.getElementById("intelChallenge").textContent = intel.engineering_focus || "Data & scalable systems.";
    document.getElementById("intelHook").textContent      = intel.personal_hook || "High alignment with your applied ML projects.";
    document.getElementById("intelCard").style.display    = "";

    // Show Email Card
    document.getElementById("emailSubject").value = data.subject || "";
    document.getElementById("emailBody").value    = data.body || "";
    updateWordCount();

    if (data.resume_filename) {
      document.getElementById("attachmentName").textContent = data.resume_filename;
    }

    document.getElementById("coldPlaceholderCard").style.display = "none";
    document.getElementById("emailDraftCard").style.display      = "";

  } catch (err) {
    alert("Error: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg> Research Company & Draft Human Email`;
  }
}

function updateWordCount() {
  const body = document.getElementById("emailBody").value.trim();
  const words = body ? body.split(/\s+/).length : 0;
  const badge = document.getElementById("emailWordCount");
  badge.textContent = `~${words} words (${words <= 120 ? 'Crisp & High Open-Rate' : 'Slightly Long'})`;
}

async function sendOutreachEmail(isTest = false) {
  const toEmail    = isTest
    ? prompt("Enter test recipient email address:", "chiragjanbandhu81@gmail.com")
    : document.getElementById("targetEmail").value.trim();

  if (!toEmail) return;

  const subject     = document.getElementById("emailSubject").value.trim();
  const body        = document.getElementById("emailBody").value.trim();
  const name        = document.getElementById("targetName").value.trim();
  const company     = document.getElementById("targetCompany").value.trim();
  const resumePath  = currentDraftData ? currentDraftData.resume_path : "";

  const btn = isTest ? document.getElementById("sendTestBtn") : document.getElementById("sendEmailBtn");
  const origText = btn.innerHTML;
  btn.disabled = true;
  btn.textContent = isTest ? "Sending Test..." : "Sending...";

  const statusEl = document.getElementById("emailStatusMsg");
  statusEl.style.display = "none";

  try {
    const res = await fetch("/api/cold_email/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to_email: toEmail,
        subject: subject,
        body: body,
        name: name,
        company: company,
        resume_path: resumePath,
      }),
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || "Sending failed");
    }

    statusEl.className = "email-status-msg success";
    statusEl.textContent = `✓ ${isTest ? 'Test email' : 'Personalized cold email'} successfully sent to ${toEmail}! Tailored resume attached.`;
    statusEl.style.display = "";

    // Refresh recruiter list if sent live
    if (!isTest) {
      loadRecruiters(document.getElementById("recruiterSearchInput").value.trim());
    }

  } catch (err) {
    statusEl.className = "email-status-msg error";
    statusEl.textContent = `✗ Failed to send: ${err.message}`;
    statusEl.style.display = "";
  } finally {
    btn.disabled = false;
    btn.innerHTML = origText;
  }
}

// ── Initialization ──────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  loadPrompts();

  document.getElementById("jdInput").addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key === "Enter") startBuild();
  });
});
