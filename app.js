"use strict";

const $ = (id) => document.getElementById(id);

const els = {
  settingsBtn: $("settingsBtn"),
  settingsCard: $("settingsCard"),
  settingsApiKey: $("settingsApiKey"),
  searchProvider: $("searchProvider"),
  searchKeyField: $("searchKeyField"),
  settingsSearchKey: $("settingsSearchKey"),
  settingsModel: $("settingsModel"),
  saveSettingsBtn: $("saveSettingsBtn"),
  closeSettingsBtn: $("closeSettingsBtn"),
  settingsStatus: $("settingsStatus"),

  levelSeg: $("levelSeg"),
  schoolFields: $("schoolFields"),
  uniFields: $("uniFields"),
  board: $("board"),
  classLevel: $("classLevel"),
  subject: $("subject"),
  university: $("university"),
  course: $("course"),
  semester: $("semester"),
  uniSubject: $("uniSubject"),

  notes: $("notes"),
  webSearchToggle: $("webSearchToggle"),
  analyzeBtn: $("analyzeBtn"),
  uploadBtn: $("uploadBtn"),
  clearBtn: $("clearBtn"),
  fileInput: $("fileInput"),
  uploadStatus: $("uploadStatus"),
  errorBox: $("errorBox"),
  inputCard: $("inputCard"),

  loading: $("loading"),
  loadingText: $("loadingText"),
  results: $("results"),
  downloadBtn: $("downloadBtn"),
  downloadDocxBtn: $("downloadDocxBtn"),
  downloadPdfBtn: $("downloadPdfBtn"),

  summaryCard: $("summaryCard"),
  summaryText: $("summaryText"),
  keyPointsList: $("keyPointsList"),
  topicsList: $("topicsList"),
  questionsList: $("questionsList"),
  pyqList: $("pyqList"),
  webCard: $("webCard"),
  webTrend: $("webTrend"),
  webTopics: $("webTopics"),
  webQuestions: $("webQuestions"),
  webSources: $("webSources"),
  webNote: $("webNote"),
  metaNote: $("metaNote"),
};

let lastResult = null;
let currentLevel = "school";

const settings = {
  apiKey: "",
  model: "openai/gpt-oss-120b",
  searchProvider: "duckduckgo",
  searchKey: "",
};

const LOADING_MESSAGES = [
  "Analysing your notes…",
  "Extracting key points…",
  "Finding high-yield topics…",
  "Generating important questions…",
  "Searching the web for repeated PYQs…",
];

function showError(msg) {
  els.errorBox.textContent = msg;
  els.errorBox.hidden = !msg;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function domainOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch (_) { return ""; }
}

function weightPill(weightage) {
  const w = (weightage || "").toLowerCase();
  return w.includes("high") ? "pill-high" : w.includes("medium") ? "pill-medium" : "pill-low";
}

function freqPill(f) {
  const v = (f || "").toLowerCase();
  if (v.includes("very")) return "pill-vf";
  if (v.includes("moderate")) return "pill-mod";
  return "pill-freq";
}

/* ---------------- Settings ---------------- */
function loadSettings() {
  try {
    Object.assign(settings, JSON.parse(localStorage.getItem("examprep_settings") || "{}"));
  } catch (_) {}
  els.settingsApiKey.value = settings.apiKey || "";
  els.settingsModel.value = settings.model || "openai/gpt-oss-120b";
  els.searchProvider.value = settings.searchProvider || "duckduckgo";
  els.settingsSearchKey.value = settings.searchKey || "";
  updateSearchKeyField();
}

function saveSettings() {
  settings.apiKey = els.settingsApiKey.value.trim();
  settings.model = els.settingsModel.value;
  settings.searchProvider = els.searchProvider.value;
  settings.searchKey = els.settingsSearchKey.value.trim();
  localStorage.setItem("examprep_settings", JSON.stringify(settings));
  els.settingsStatus.hidden = false;
  els.settingsStatus.textContent = "✅ Settings saved.";
  setTimeout(() => { els.settingsStatus.hidden = true; }, 2200);
}

function updateSearchKeyField() {
  els.searchKeyField.hidden = els.searchProvider.value === "duckduckgo";
}

/* ---------------- Level toggle ---------------- */
function setLevel(level) {
  currentLevel = level;
  els.levelSeg.querySelectorAll("button[data-level]").forEach((b) => {
    b.classList.toggle("active", b.dataset.level === level);
  });
  els.schoolFields.hidden = level !== "school";
  els.uniFields.hidden = level !== "university";
}

/* ---------------- Render ---------------- */
function render(data) {
  lastResult = data;

  els.summaryCard.hidden = !data.summary;
  els.summaryText.textContent = data.summary || "";

  els.keyPointsList.innerHTML = "";
  (data.key_points || []).forEach((kp) => {
    const li = document.createElement("li");
    li.textContent = kp;
    els.keyPointsList.appendChild(li);
  });
  if (!(data.key_points || []).length) {
    els.keyPointsList.innerHTML = '<li class="muted">No key points generated.</li>';
  }

  els.topicsList.innerHTML = "";
  (data.important_topics || []).forEach((t) => {
    const div = document.createElement("div");
    div.className = "topic";
    div.innerHTML = `
      <h4>${escapeHtml(t.topic)}</h4>
      <div class="pills">
        <span class="pill ${weightPill(t.weightage)}">${escapeHtml(t.weightage || "Medium")}</span>
        <span class="pill pill-medium">${escapeHtml(t.exam_probability || "")}</span>
      </div>
      ${t.reason ? `<p class="reason">${escapeHtml(t.reason)}</p>` : ""}`;
    els.topicsList.appendChild(div);
  });
  if (!(data.important_topics || []).length) {
    els.topicsList.innerHTML = '<p class="muted">No topics identified.</p>';
  }

  els.questionsList.innerHTML = "";
  (data.important_questions || []).forEach((q, i) => {
    const div = document.createElement("div");
    div.className = "qitem";
    div.innerHTML = `
      <div class="qnum">${i + 1}</div>
      <div class="qbody">
        <p class="qtext">${escapeHtml(q.question)}</p>
        <div class="qmeta">
          ${q.marks ? `<span class="tag tag-marks">${q.marks} mark${q.marks > 1 ? "s" : ""}</span>` : ""}
          ${q.type ? `<span class="tag">${escapeHtml(q.type)}</span>` : ""}
          ${q.topic ? `<span class="tag">${escapeHtml(q.topic)}</span>` : ""}
        </div>
      </div>`;
    els.questionsList.appendChild(div);
  });
  if (!(data.important_questions || []).length) {
    els.questionsList.innerHTML = '<p class="muted">No questions generated.</p>';
  }

  els.pyqList.innerHTML = "";
  (data.pyqs || []).forEach((q) => {
    const div = document.createElement("div");
    div.className = "pyq";
    const hint = q.answer_hint
      ? `<p class="pyq-hint">💡 <strong>Answer hint:</strong> ${escapeHtml(q.answer_hint)}</p>`
      : "";
    div.innerHTML = `
      <div class="pyq-top">
        <span class="tag tag-year">${escapeHtml(q.year)}</span>
        <span class="tag">${escapeHtml(q.board || "")}</span>
        <span class="tag">${escapeHtml(q.subject || "")} · Class ${escapeHtml(q.class)}</span>
        ${q.marks ? `<span class="tag tag-marks">${q.marks} mark${q.marks > 1 ? "s" : ""}</span>` : ""}
      </div>
      <p class="pyq-q">${escapeHtml(q.question)}</p>
      ${hint}`;
    els.pyqList.appendChild(div);
  });
  if (!(data.pyqs || []).length) {
    els.pyqList.innerHTML = '<p class="muted">No matching questions in the local database.</p>';
  }

  renderWeb(data.web);

  els.metaNote.textContent = data.model
    ? `Generated with AI model “${data.model}”.`
    : "";

  els.results.hidden = false;
  els.results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderWeb(web) {
  if (!web || !web.enabled) {
    els.webCard.hidden = true;
    return;
  }
  els.webCard.hidden = false;

  if (web.trend) {
    els.webTrend.hidden = false;
    els.webTrend.textContent = web.trend;
  } else {
    els.webTrend.hidden = true;
  }

  els.webTopics.innerHTML = "";
  (web.repeated_topics || []).forEach((t) => {
    const div = document.createElement("div");
    div.className = "topic";
    div.innerHTML = `
      <h4>${escapeHtml(t.topic)}</h4>
      <div class="pills">
        <span class="pill ${freqPill(t.frequency)}">${escapeHtml(t.frequency || "Frequent")}</span>
        ${t.mentions ? `<span class="pill pill-mod">${t.mentions} source${t.mentions > 1 ? "s" : ""}</span>` : ""}
      </div>`;
    els.webTopics.appendChild(div);
  });

  els.webQuestions.innerHTML = "";
  (web.repeated_questions || []).forEach((q) => {
    const div = document.createElement("div");
    div.className = "web-q";
    const links = (q.source_urls || [])
      .map((u) => `<a href="${escapeHtml(u)}" target="_blank" rel="noopener">${escapeHtml(u)}</a>`)
      .join("");
    div.innerHTML = `
      <p class="pyq-q">${escapeHtml(q.question)}</p>
      <div class="pills">
        <span class="pill ${freqPill(q.frequency)}">${escapeHtml(q.frequency || "Frequent")}</span>
        ${q.type ? `<span class="tag">${escapeHtml(q.type)}</span>` : ""}
      </div>
      ${links ? `<div class="source-links">${links}</div>` : ""}`;
    els.webQuestions.appendChild(div);
  });

  els.webSources.innerHTML = "";
  (web.sources || []).forEach((s) => {
    const url = s.url || "";
    const title = s.title || url;
    const dom = domainOf(url);
    const div = document.createElement("div");
    div.className = "source-item";
    div.innerHTML = `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(title)}</a>${
      dom ? `<span class="source-domain">${escapeHtml(dom)}</span>` : ""
    }`;
    els.webSources.appendChild(div);
  });

  const n = (web.sources || []).length;
  if (web.error) {
    els.webNote.textContent = `⚠ ${web.error}`;
  } else if (n) {
    els.webNote.textContent = `Based on ${n} web source${n > 1 ? "s" : ""} (listed below).`;
  } else {
    els.webNote.textContent = "No web results found.";
  }
}

/* ---------------- Analyze ---------------- */
function currentContext() {
  if (currentLevel === "university") {
    return {
      level: "university",
      university: els.university.value.trim(),
      course: els.course.value.trim(),
      semester: els.semester.value,
      subject: els.uniSubject.value.trim(),
    };
  }
  return {
    level: "school",
    board: els.board.value,
    class_level: els.classLevel.value,
    subject: els.subject.value,
  };
}

async function analyze() {
  const notes = els.notes.value.trim();
  if (!notes) {
    showError("Please paste some notes before analysing.");
    els.notes.focus();
    return;
  }

  showError("");
  els.results.hidden = true;
  els.loading.hidden = false;
  els.analyzeBtn.disabled = true;

  let mi = 0;
  const msgTimer = setInterval(() => {
    mi = (mi + 1) % LOADING_MESSAGES.length;
    els.loadingText.textContent = LOADING_MESSAGES[mi];
  }, 1600);

  const payload = {
    notes,
    api_key: settings.apiKey,
    model: settings.model,
    web_search: els.webSearchToggle.checked,
    search_provider: settings.searchProvider,
    search_api_key: settings.searchKey,
    ...currentContext(),
  };

  try {
    const resp = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok || data.error) {
      showError(data.error || `Request failed (HTTP ${resp.status}).`);
      return;
    }
    render(data);
  } catch (err) {
    showError("Could not reach the server. Is it running? — " + err.message);
  } finally {
    clearInterval(msgTimer);
    els.loading.hidden = true;
    els.analyzeBtn.disabled = false;
  }
}

/* ---------------- Export ---------------- */
function buildMarkdown(data) {
  const lines = [];
  const ctx = data._context || {};
  lines.push("# 🎓 Study Pack");
  if (ctx.level === "university") {
    lines.push(`**${ctx.university || ""} · ${ctx.course || ""} · Semester ${ctx.semester || "—"} · ${ctx.subject || "—"}**`);
  } else {
    lines.push(`**${ctx.board || ""} · Class ${ctx.class_level || "—"} · ${ctx.subject || "—"}**`);
  }

  if (data.summary) lines.push("", "## 📌 Summary", data.summary);
  lines.push("", "## 🔑 Key Points");
  (data.key_points || []).forEach((kp, i) => lines.push(`${i + 1}. ${kp}`));

  lines.push("", "## 🎯 Important Topics");
  (data.important_topics || []).forEach((t) => {
    lines.push(`- **${t.topic}** — ${t.weightage} (${t.exam_probability})`);
    if (t.reason) lines.push(`  - ${t.reason}`);
  });

  lines.push("", "## ❓ Most Important Questions");
  (data.important_questions || []).forEach((q, i) => {
    lines.push(`${i + 1}. ${q.question}  _(${q.marks || "?"} marks, ${q.type || "Short"})_`);
  });

  lines.push("", "## 🗂 Previous Year Questions (local)");
  (data.pyqs || []).forEach((q) => {
    lines.push(`- **[${q.year}] ${q.question}**  _(${q.subject}, Class ${q.class}, ${q.marks} marks)_`);
  });

  const web = data.web;
  if (web && web.enabled) {
    lines.push("", "## 🌐 Most Repeated PYQs (from the web)");
    if (web.trend) lines.push(web.trend, "");
    (web.repeated_topics || []).forEach((t) => lines.push(`- **${t.topic}** — ${t.frequency}`));
    lines.push("");
    (web.repeated_questions || []).forEach((q) => {
      lines.push(`- ${q.question}  _(${q.frequency}${q.type ? ", " + q.type : ""})_`);
      (q.source_urls || []).forEach((u) => lines.push(`  - ${u}`));
    });
  }

  return lines.join("\n");
}

function downloadMarkdown() {
  if (!lastResult) return;
  lastResult._context = currentContext();
  const md = buildMarkdown(lastResult);
  const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "study-pack.md";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function exportFile(format) {
  if (!lastResult) return;
  const data = { ...lastResult, _context: currentContext() };
  try {
    const resp = await fetch("/api/export?format=" + encodeURIComponent(format), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data }),
    });
    if (!resp.ok) {
      let msg = `Export failed (HTTP ${resp.status}).`;
      try {
        const j = await resp.json();
        if (j.error) msg = j.error;
      } catch (_) {}
      showError(msg);
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = format === "docx" ? "study-pack.docx" : "study-pack.pdf";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    showError("Export failed: " + err.message);
  }
}

/* ---------------- Upload ---------------- */
async function uploadFile(file) {
  showError("");
  els.uploadStatus.textContent = `Extracting text from “${file.name}”…`;
  els.uploadBtn.disabled = true;
  try {
    const resp = await fetch("/api/extract", {
      method: "POST",
      headers: { "X-Filename": file.name, "Content-Type": "application/octet-stream" },
      body: file,
    });
    const data = await resp.json();
    if (!resp.ok || data.error) {
      showError(data.error || `Upload failed (HTTP ${resp.status}).`);
      els.uploadStatus.textContent = "";
      return;
    }
    els.notes.value = data.text;
    els.uploadStatus.textContent = `✅ Loaded “${file.name}” — ${data.text.length.toLocaleString()} characters. Review & edit before analysing.`;
  } catch (err) {
    showError("Could not reach the server. — " + err.message);
    els.uploadStatus.textContent = "";
  } finally {
    els.uploadBtn.disabled = false;
  }
}

/* ---------------- Events ---------------- */
els.analyzeBtn.addEventListener("click", analyze);
els.clearBtn.addEventListener("click", () => {
  els.notes.value = "";
  showError("");
  els.results.hidden = true;
  lastResult = null;
  els.notes.focus();
});
els.downloadBtn.addEventListener("click", downloadMarkdown);
els.downloadDocxBtn.addEventListener("click", () => exportFile("docx"));
els.downloadPdfBtn.addEventListener("click", () => exportFile("pdf"));

els.levelSeg.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-level]");
  if (btn) setLevel(btn.dataset.level);
});

els.settingsBtn.addEventListener("click", () => els.settingsCard.classList.toggle("open"));
els.closeSettingsBtn.addEventListener("click", () => els.settingsCard.classList.remove("open"));
els.saveSettingsBtn.addEventListener("click", saveSettings);
els.searchProvider.addEventListener("change", updateSearchKeyField);

els.uploadBtn.addEventListener("click", () => els.fileInput.click());
els.fileInput.addEventListener("change", () => {
  if (els.fileInput.files && els.fileInput.files[0]) uploadFile(els.fileInput.files[0]);
  els.fileInput.value = "";
});

["dragover", "dragenter"].forEach((ev) =>
  els.inputCard.addEventListener(ev, (e) => {
    e.preventDefault();
    els.inputCard.classList.add("drag-over");
  })
);
["dragleave", "drop"].forEach((ev) =>
  els.inputCard.addEventListener(ev, (e) => {
    e.preventDefault();
    els.inputCard.classList.remove("drag-over");
  })
);
els.inputCard.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files && e.dataTransfer.files[0];
  if (f) uploadFile(f);
});

els.notes.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    analyze();
  }
});

/* ---------------- Init ---------------- */
loadSettings();
setLevel("school");
