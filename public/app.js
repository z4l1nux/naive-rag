/* ── TurboQuant ──────────────────────────────────────────────────────
 * State, config, DOM refs and chart rendering for the TQ KV Cache panel.
 * ──────────────────────────────────────────────────────────────────── */

/* ── Reranker ──────────────────────────────────────────────────────────
 * State, config, DOM refs and metric rendering for the Reranker panel.
 * ──────────────────────────────────────────────────────────────────── */

let rrConfig = { enabled: false, top_n: 10, top_k: 3 };
let rrSaving = false;

let rrHeaderBtn, rrBody, rrChevron, rrBadge, rrLastHint;
let rrToggleBtn, rrTopN, rrTopK, rrApplyBtn, rrSavingEl;
let rrCards;
let rrValLatency, rrSubLatency, rrValCandidates, rrSubCandidates;
let rrValImprovement, rrSubImprovement;

function updateRrBadgeStyle() {
  rrBadge.textContent  = rrConfig.enabled ? "ON" : "OFF";
  rrBadge.className    = rrConfig.enabled ? "rr-badge rr-badge--on" : "rr-badge";
  rrToggleBtn.textContent = rrConfig.enabled ? "Habilitado" : "Desabilitado";
  rrToggleBtn.className   = rrConfig.enabled
    ? "rr-toggle-btn rr-toggle-btn--on"
    : "rr-toggle-btn";
  rrTopN.value = rrConfig.top_n;
  rrTopK.value = rrConfig.top_k;
}

async function applyRrConfig(enabled, top_n, top_k) {
  if (rrSaving) return;
  rrSaving = true;
  rrSavingEl.classList.remove("hidden");
  try {
    const res = await fetch("/api/reranker/config", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ enabled, top_n: Number(top_n), top_k: Number(top_k) }),
    });
    if (!res.ok) {
      const err = await res.json();
      console.error("Reranker config error:", err.detail);
      return;
    }
    rrConfig = await res.json();
    updateRrBadgeStyle();
  } catch (e) {
    console.error("Reranker config error:", e);
  } finally {
    rrSaving = false;
    rrSavingEl.classList.add("hidden");
  }
}

function renderRrMetrics(record, summary) {
  rrCards.classList.remove("hidden");

  rrValLatency.textContent    = fmtMs(record.latency_ms);
  rrSubLatency.textContent    = `${record.n_candidates} pares avaliados`;
  rrValCandidates.textContent = `${record.n_candidates}→${record.n_selected}`;
  rrSubCandidates.textContent = `top-N → top-K`;

  const imp = summary.avg_rank_improvement ?? 0;
  rrValImprovement.textContent = imp > 0 ? `+${imp}` : imp === 0 ? "—" : `${imp}`;
  rrSubImprovement.textContent = "posições médias ↑";
  rrLastHint.textContent = `${fmtMs(record.latency_ms)} · ${record.n_candidates}→${record.n_selected}`;
}

function annotateSourcesWithRanks(sourcesEl, rankChanges) {
  if (!sourcesEl || !rankChanges?.length) return;
  const items = sourcesEl.querySelectorAll(".source-item");
  items.forEach((item, toIdx) => {
    const rc = rankChanges.find(r => r.to === toIdx);
    if (!rc || rc.from < 0) return;
    const delta = rc.from - rc.to;
    const badge = document.createElement("span");
    if (delta > 0) {
      badge.className   = "source-rank-delta source-rank-delta--up";
      badge.textContent = `↑${delta}`;
      badge.title       = `Subiu ${delta} posição(ões) após reranking`;
    } else if (delta < 0) {
      badge.className   = "source-rank-delta source-rank-delta--down";
      badge.textContent = `↓${Math.abs(delta)}`;
      badge.title       = `Desceu ${Math.abs(delta)} posição(ões) após reranking`;
    } else {
      badge.className   = "source-rank-delta source-rank-delta--same";
      badge.textContent = "=";
      badge.title       = "Posição mantida após reranking";
    }
    item.insertBefore(badge, item.firstChild);
  });
}

function initReranker() {
  rrHeaderBtn     = document.getElementById("rr-header-btn");
  rrBody          = document.getElementById("rr-body");
  rrChevron       = document.getElementById("rr-chevron");
  rrBadge         = document.getElementById("rr-badge");
  rrLastHint      = document.getElementById("rr-last-hint");
  rrToggleBtn     = document.getElementById("rr-toggle-btn");
  rrTopN          = document.getElementById("rr-top-n");
  rrTopK          = document.getElementById("rr-top-k");
  rrApplyBtn      = document.getElementById("rr-apply-btn");
  rrSavingEl      = document.getElementById("rr-saving");
  rrCards         = document.getElementById("rr-cards");
  rrValLatency    = document.getElementById("rr-val-latency");
  rrSubLatency    = document.getElementById("rr-sub-latency");
  rrValCandidates = document.getElementById("rr-val-candidates");
  rrSubCandidates = document.getElementById("rr-sub-candidates");
  rrValImprovement  = document.getElementById("rr-val-improvement");
  rrSubImprovement  = document.getElementById("rr-sub-improvement");

  rrHeaderBtn.addEventListener("click", () => {
    const isHidden = rrBody.classList.toggle("hidden");
    rrChevron.textContent = isHidden ? "▼" : "▲";
  });

  rrToggleBtn.addEventListener("click", () => {
    applyRrConfig(!rrConfig.enabled, rrTopN.value, rrTopK.value);
  });

  rrApplyBtn.addEventListener("click", () => {
    applyRrConfig(rrConfig.enabled, rrTopN.value, rrTopK.value);
  });

  fetch("/api/reranker/config")
    .then(r => r.json())
    .then(data => { rrConfig = data; updateRrBadgeStyle(); })
    .catch(() => {});
}

/* ── TurboQuant ──────────────────────────────────────────────────────
 * State, config, DOM refs and chart rendering for the TQ KV Cache panel.
 * ──────────────────────────────────────────────────────────────────── */

const TQ_COLORS = {
  "TQ OFF":     "#6b7280",
  "Standard":   "#22d3ee",
  "TurboQuant": "#a78bfa",
};

let tqConfig      = { enabled: false, mode: "off" };
let tqSaving      = false;
let backendConfig = { backend: "ollama" };

// DOM refs — resolved after DOMContentLoaded (called in init block at bottom)
let backendOllamaBtn, backendLlamacppBtn, backendNote, llamacppInfo;
let tqHeaderBtn, tqBody, tqChevron, tqBadge, tqLastHint;
let tqToggleBtn, tqSavingEl;
let tqModeStandard, tqModeAggressive;
let tqCards;
let tqChartTitle, tqInferenceCount, tqCharts;
let tqValLatency, tqSubLatency, tqValTps, tqSubTps;
let tqValPrompt, tqSubPrompt, tqValMem, tqSubMem;
let tqChartLatency, tqChartTps, tqChartMem;

function fmtMs(ms) {
  if (ms === null || ms === undefined || ms === 0) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
}

function fmtBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  if (bytes < 1024)        return `${bytes} B`;
  if (bytes < 1024 ** 2)   return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3)   return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function buildBarChart(container, series) {
  container.innerHTML = "";
  const values = series.map(s => s.value || 0);
  const maxVal = Math.max(...values, 1);

  for (const { label, value, unit } of series) {
    const hasData = value !== null && value !== undefined;
    const pct   = Math.max(((hasData ? value : 0) / maxVal) * 100, 2);
    const color = TQ_COLORS[label] ?? "#22d3ee";

    const col = document.createElement("div");
    col.className = "tq-bar-col";

    const valEl = document.createElement("span");
    valEl.className = "tq-bar-val";
    valEl.textContent = hasData ? `${value}${unit ?? ""}` : "—";

    const bar = document.createElement("div");
    bar.className = "tq-bar";
    bar.style.height = `${pct}%`;
    bar.style.background = color;

    const labelEl = document.createElement("span");
    labelEl.className = "tq-bar-label";
    labelEl.textContent = label;

    col.appendChild(valEl);
    col.appendChild(bar);
    col.appendChild(labelEl);
    container.appendChild(col);
  }
}

function updateTqBadgeStyle() {
  tqBadge.textContent = tqConfig.enabled
    ? { standard: "Standard 8-bit", aggressive: "TurboQuant 3-bit" }[tqConfig.mode] ?? tqConfig.mode
    : "OFF";
  tqBadge.className = tqConfig.enabled ? "tq-badge tq-badge--on" : "tq-badge";
  tqToggleBtn.textContent   = tqConfig.enabled ? "Habilitado" : "Desabilitado";
  tqToggleBtn.className     = tqConfig.enabled
    ? "tq-toggle-btn tq-toggle-btn--on"
    : "tq-toggle-btn";
  tqModeStandard.className  = tqConfig.enabled && tqConfig.mode === "standard"
    ? "tq-mode-btn tq-mode-btn--active-cyan"
    : "tq-mode-btn";
  tqModeAggressive.className = tqConfig.enabled && tqConfig.mode === "aggressive"
    ? "tq-mode-btn tq-mode-btn--active-purple"
    : "tq-mode-btn";
}

async function applyTqConfig(enabled, mode) {
  if (tqSaving) return;
  tqSaving = true;
  tqSavingEl.classList.remove("hidden");
  try {
    const res  = await fetch("/api/turboquant/config", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ enabled, mode }),
    });
    tqConfig = await res.json();
    updateTqBadgeStyle();
  } catch (e) {
    console.error("TurboQuant config error:", e);
  } finally {
    tqSaving = false;
    tqSavingEl.classList.add("hidden");
  }
}

function renderTqMetrics(record, summary) {
  // Live metric cards
  tqCards.classList.remove("hidden");
  tqValLatency.textContent = fmtMs(record.total_ms);
  tqSubLatency.textContent = `eval: ${fmtMs(record.eval_ms)}`;
  tqValTps.textContent     = `${record.tokens_per_sec}`;
  tqSubTps.textContent     = `${record.gen_tokens} tokens gen`;
  tqValPrompt.textContent  = fmtMs(record.prompt_eval_ms);
  tqSubPrompt.textContent  = `${record.prompt_tokens} tokens`;
  tqValMem.textContent     = fmtBytes(record.kv_bytes);
  tqSubMem.textContent     = `${record.memory_reduction}% vs FP16`;

  // Update last hint in header
  tqLastHint.textContent = `${fmtMs(record.total_ms)} · ${record.tokens_per_sec} t/s`;

  // Comparison charts
  const total = Object.values(summary)
    .filter(Boolean)
    .reduce((acc, s) => acc + s.count, 0);
  tqInferenceCount.textContent = total;
  tqChartTitle.style.display = total > 0 ? "" : "none";

  if (total > 0) {
    tqCharts.classList.remove("hidden");

    buildBarChart(tqChartLatency, [
      { label: "TQ OFF",      value: summary.off?.avg_total_ms        ?? 0, unit: "ms" },
      { label: "Standard",    value: summary.standard?.avg_total_ms   ?? 0, unit: "ms" },
      { label: "TurboQuant",  value: summary.aggressive?.avg_total_ms ?? 0, unit: "ms" },
    ]);

    buildBarChart(tqChartTps, [
      { label: "TQ OFF",      value: summary.off?.avg_tokens_per_sec        ?? 0, unit: "t/s" },
      { label: "Standard",    value: summary.standard?.avg_tokens_per_sec   ?? 0, unit: "t/s" },
      { label: "TurboQuant",  value: summary.aggressive?.avg_tokens_per_sec ?? 0, unit: "t/s" },
    ]);

    buildBarChart(tqChartMem, [
      { label: "TQ OFF",     value: summary.off        != null ? Math.round((100 - summary.off.avg_memory_reduction)        * 10) / 10 : null, unit: "%" },
      { label: "Standard",   value: summary.standard   != null ? Math.round((100 - summary.standard.avg_memory_reduction)   * 10) / 10 : null, unit: "%" },
      { label: "TurboQuant", value: summary.aggressive != null ? Math.round((100 - summary.aggressive.avg_memory_reduction) * 10) / 10 : null, unit: "%" },
    ]);
  }
}

async function applyBackendConfig(backend) {
  try {
    const res = await fetch("/api/backend/config", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ backend }),
    });
    backendConfig = await res.json();
    updateBackendStyle();
  } catch (e) {
    console.error("Backend config error:", e);
  }
}

function updateBackendStyle() {
  const isLlama = backendConfig.backend === "llamacpp";
  backendOllamaBtn.className  = isLlama ? "tq-backend-btn" : "tq-backend-btn tq-backend-btn--active";
  backendLlamacppBtn.className = isLlama ? "tq-backend-btn tq-backend-btn--active" : "tq-backend-btn";
  llamacppInfo.classList.toggle("hidden", !isLlama);
  backendNote.textContent = isLlama
    ? `${backendConfig.llamacpp_host} · embeddings via Ollama`
    : "embeddings sempre via Ollama";
}

function initTurboQuant() {
  backendOllamaBtn   = document.getElementById("backend-ollama");
  backendLlamacppBtn = document.getElementById("backend-llamacpp");
  backendNote        = document.getElementById("backend-note");
  llamacppInfo       = document.getElementById("llamacpp-info");

  backendOllamaBtn.addEventListener("click",   () => applyBackendConfig("ollama"));
  backendLlamacppBtn.addEventListener("click", () => applyBackendConfig("llamacpp"));

  fetch("/api/backend/config")
    .then(r => r.json())
    .then(data => { backendConfig = data; updateBackendStyle(); })
    .catch(() => {});

  tqHeaderBtn      = document.getElementById("tq-header-btn");
  tqBody           = document.getElementById("tq-body");
  tqChevron        = document.getElementById("tq-chevron");
  tqBadge          = document.getElementById("tq-badge");
  tqLastHint       = document.getElementById("tq-last-hint");
  tqToggleBtn      = document.getElementById("tq-toggle-btn");
  tqSavingEl       = document.getElementById("tq-saving");
  tqModeStandard   = document.getElementById("tq-mode-standard");
  tqModeAggressive = document.getElementById("tq-mode-aggressive");
  tqCards          = document.getElementById("tq-cards");
  tqChartTitle     = document.getElementById("tq-chart-title");
  tqInferenceCount = document.getElementById("tq-inference-count");
  tqCharts         = document.getElementById("tq-charts");
  tqValLatency     = document.getElementById("tq-val-latency");
  tqSubLatency     = document.getElementById("tq-sub-latency");
  tqValTps         = document.getElementById("tq-val-tps");
  tqSubTps         = document.getElementById("tq-sub-tps");
  tqValPrompt      = document.getElementById("tq-val-prompt");
  tqSubPrompt      = document.getElementById("tq-sub-prompt");
  tqValMem         = document.getElementById("tq-val-mem");
  tqSubMem         = document.getElementById("tq-sub-mem");
  tqChartLatency   = document.getElementById("tq-chart-latency");
  tqChartTps       = document.getElementById("tq-chart-tps");
  tqChartMem       = document.getElementById("tq-chart-mem");

  // Expand/collapse
  tqHeaderBtn.addEventListener("click", () => {
    const isHidden = tqBody.classList.toggle("hidden");
    tqChevron.textContent = isHidden ? "▼" : "▲";
  });

  // Toggle enable/disable
  tqToggleBtn.addEventListener("click", () => {
    const next     = !tqConfig.enabled;
    const nextMode = next ? (tqConfig.mode === "off" ? "standard" : tqConfig.mode) : "off";
    applyTqConfig(next, nextMode);
  });

  // Mode buttons
  document.querySelectorAll(".tq-mode-btn").forEach(btn => {
    btn.addEventListener("click", () => applyTqConfig(true, btn.dataset.mode));
  });

  // Load saved config from server
  fetch("/api/turboquant/config")
    .then(r => r.json())
    .then(data => { tqConfig = data; updateTqBadgeStyle(); })
    .catch(() => {});
}

/* ── DOM refs ───────────────────────────────────────────────────────── */

const addForm      = document.getElementById("add-doc-form");
const docContent   = document.getElementById("doc-content");
const addBtn       = document.getElementById("add-btn");
const addLabel     = addBtn.querySelector(".btn-label");
const addSpinner   = addBtn.querySelector(".btn-spinner");

const uploadForm   = document.getElementById("upload-form");
const fileInput    = document.getElementById("file-input");
const fileDrop     = document.getElementById("file-drop");
const fileDropLabel = document.getElementById("file-drop-label");
const chunkSize    = document.getElementById("chunk-size");
const chunkOverlap = document.getElementById("chunk-overlap");
const uploadBtn    = document.getElementById("upload-btn");
const uploadLabel  = uploadBtn.querySelector(".btn-label");
const uploadSpinner = uploadBtn.querySelector(".btn-spinner");
const uploadProgress = document.getElementById("upload-progress");

const docList      = document.getElementById("doc-list");
const docEmpty     = document.getElementById("doc-empty");
const docCount     = document.getElementById("doc-count");

const queryForm    = document.getElementById("query-form");
const queryInput   = document.getElementById("query-input");
const sendBtn      = document.getElementById("send-btn");
const messages     = document.getElementById("messages");

const tabs         = document.querySelectorAll(".tab");
const panels       = document.querySelectorAll(".tab-panel");

/* ── State ──────────────────────────────────────────────────────────── */

let isQuerying = false;
let selectedFile = null;

/* ── Tabs ────────────────────────────────────────────────────────────── */

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.remove("tab--active"));
    panels.forEach((p) => p.classList.add("hidden"));
    tab.classList.add("tab--active");
    document.getElementById(`panel-${tab.dataset.tab}`).classList.remove("hidden");
  });
});

/* ── File drop ───────────────────────────────────────────────────────── */

fileDrop.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) selectFile(fileInput.files[0]);
});

fileDrop.addEventListener("dragover", (e) => {
  e.preventDefault();
  fileDrop.classList.add("drag-over");
});

fileDrop.addEventListener("dragleave", () => fileDrop.classList.remove("drag-over"));

fileDrop.addEventListener("drop", (e) => {
  e.preventDefault();
  fileDrop.classList.remove("drag-over");
  if (e.dataTransfer.files[0]) selectFile(e.dataTransfer.files[0]);
});

function selectFile(file) {
  selectedFile = file;
  fileDropLabel.textContent = file.name;
  fileDropLabel.classList.add("has-file");
  uploadBtn.disabled = false;
}

/* ── Upload ──────────────────────────────────────────────────────────── */

uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!selectedFile) return;

  setUploadLoading(true);
  uploadProgress.classList.add("hidden");

  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("chunkSize", chunkSize.value);
  formData.append("overlap", chunkOverlap.value);

  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      uploadProgress.textContent = data.error ?? "Erro ao importar arquivo.";
      uploadProgress.classList.remove("hidden");
      return;
    }

    uploadProgress.textContent = `Importado: ${data.source} — ${data.chunks} chunks gerados`;
    uploadProgress.classList.remove("hidden");

    selectedFile = null;
    fileInput.value = "";
    fileDropLabel.textContent = "Clique ou arraste um arquivo";
    fileDropLabel.classList.remove("has-file");
    uploadBtn.disabled = true;

    await loadKnowledgeBase();
  } catch {
    uploadProgress.textContent = "Falha na conexao com o servidor.";
    uploadProgress.classList.remove("hidden");
  } finally {
    setUploadLoading(false);
  }
});

function setUploadLoading(loading) {
  uploadBtn.disabled = loading;
  uploadLabel.classList.toggle("hidden", loading);
  uploadSpinner.classList.toggle("hidden", !loading);
}

/* ── Knowledge base ──────────────────────────────────────────────────── */

async function loadKnowledgeBase() {
  const [docsRes, filesRes] = await Promise.all([
    fetch("/api/documents"),
    fetch("/api/documents/files"),
  ]);

  const docs  = await docsRes.json();
  const files = await filesRes.json();

  renderKnowledgeBase(docs, files);
}

function renderKnowledgeBase(docs, files) {
  docList.innerHTML = "";
  const total = docs.length + files.reduce((s, f) => s + f.chunk_count, 0);
  docCount.textContent = total;
  docEmpty.classList.toggle("hidden", total > 0);

  for (const file of files) {
    const li = document.createElement("li");
    li.className = "doc-item doc-item--file";

    const header = document.createElement("div");
    header.className = "doc-item-header";

    const name = document.createElement("span");
    name.className = "doc-filename";
    name.title = file.source_file;
    name.textContent = file.source_file;

    const chunks = document.createElement("span");
    chunks.className = "doc-chunks";
    chunks.textContent = `${file.chunk_count} chunks`;

    const del = document.createElement("button");
    del.className = "btn btn-delete";
    del.textContent = "Remover";
    del.addEventListener("click", () => removeFile(file.source_file, li));

    header.appendChild(name);
    header.appendChild(chunks);
    header.appendChild(del);
    li.appendChild(header);
    docList.appendChild(li);
  }

  for (const doc of docs) {
    const li = document.createElement("li");
    li.className = "doc-item";
    li.dataset.id = doc.id;

    const span = document.createElement("span");
    span.className = "doc-content";
    span.textContent = doc.content;

    const del = document.createElement("button");
    del.className = "btn btn-delete";
    del.textContent = "Remover";
    del.addEventListener("click", () => removeDocument(doc.id, li));

    li.appendChild(span);
    li.appendChild(del);
    docList.appendChild(li);
  }
}

async function removeDocument(id, el) {
  el.style.opacity = "0.4";
  const res = await fetch(`/api/documents/${id}`, { method: "DELETE" });
  if (res.ok) {
    await loadKnowledgeBase();
  } else {
    el.style.opacity = "";
  }
}

async function removeFile(filename, el) {
  el.style.opacity = "0.4";
  const res = await fetch(`/api/documents/files/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
  if (res.ok) {
    await loadKnowledgeBase();
  } else {
    el.style.opacity = "";
  }
}

/* ── Add text document ───────────────────────────────────────────────── */

addForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const content = docContent.value.trim();
  if (!content) return;

  setAddLoading(true);

  try {
    const res = await fetch("/api/documents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });

    if (!res.ok) {
      const err = await res.json();
      showError(err.error ?? "Erro ao adicionar documento.");
      return;
    }

    docContent.value = "";
    await loadKnowledgeBase();
  } catch {
    showError("Falha na conexao com o servidor.");
  } finally {
    setAddLoading(false);
  }
});

function setAddLoading(loading) {
  addBtn.disabled = loading;
  addLabel.classList.toggle("hidden", loading);
  addSpinner.classList.toggle("hidden", !loading);
}

/* ── Chat ────────────────────────────────────────────────────────────── */

queryForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (isQuerying) return;

  const question = queryInput.value.trim();
  if (!question) return;

  queryInput.value = "";
  clearWelcome();
  appendUserMessage(question);
  await sendQuery(question);
});

function clearWelcome() {
  const welcome = messages.querySelector(".welcome");
  if (welcome) welcome.remove();
}

function appendUserMessage(text) {
  const el = createMessage("user");
  el.querySelector(".message-bubble").textContent = text;
  messages.appendChild(el);
  scrollToBottom();
}

function createMessage(role) {
  const msg = document.createElement("div");
  msg.className = `message message--${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "EU" : "IA";

  const body = document.createElement("div");
  body.className = "message-body";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  body.appendChild(bubble);
  msg.appendChild(avatar);
  msg.appendChild(body);
  return msg;
}

async function sendQuery(question) {
  isQuerying = true;
  sendBtn.disabled = true;
  queryInput.disabled = true;

  const msg = createMessage("assistant");
  const bubble = msg.querySelector(".message-bubble");
  const body   = msg.querySelector(".message-body");

  const cursor = document.createElement("span");
  cursor.className = "cursor";
  bubble.appendChild(cursor);
  messages.appendChild(msg);
  scrollToBottom();

  let accumulated = "";
  let lastSourcesEl = null;

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, topK: 3 }),
    });

    if (!res.ok || !res.body) {
      showError("Erro ao consultar o modelo.");
      msg.remove();
      return;
    }

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let event;
        try { event = JSON.parse(line.slice(6)); } catch { continue; }

        if (event.type === "token") {
          accumulated += event.content;
          bubble.textContent = accumulated;
          bubble.appendChild(cursor);
          scrollToBottom();
        }

        if (event.type === "sources") {
          cursor.remove();
          if (event.sources.length > 0) {
            lastSourcesEl = buildSources(event.sources);
            body.appendChild(lastSourcesEl);
          }
          scrollToBottom();
        }

        if (event.type === "reranker") {
          renderRrMetrics(event.record, event.summary);
          annotateSourcesWithRanks(lastSourcesEl, event.record.rank_changes);
        }

        if (event.type === "metrics") {
          renderTqMetrics(event.record, event.summary);
        }

        if (event.type === "error") {
          cursor.remove();
          bubble.textContent = event.message;
        }
      }
    }
  } catch {
    cursor.remove();
    bubble.textContent = "Erro de conexao com o servidor.";
  } finally {
    cursor.remove();
    isQuerying = false;
    sendBtn.disabled = false;
    queryInput.disabled = false;
    queryInput.focus();
  }
}

function buildSources(sources) {
  const wrapper = document.createElement("div");
  wrapper.className = "sources";

  const label = document.createElement("div");
  label.className = "sources-label";
  label.textContent = "Fontes consultadas";
  wrapper.appendChild(label);

  for (const src of sources) {
    const item = document.createElement("div");
    item.className = "source-item";

    const score = document.createElement("span");
    score.className = "source-score";
    score.textContent = `${(src.similarity * 100).toFixed(1)}%`;

    const right = document.createElement("div");
    right.style.display = "flex";
    right.style.flexDirection = "column";
    right.style.gap = "3px";
    right.style.overflow = "hidden";

    if (src.source_file) {
      const fileTag = document.createElement("span");
      fileTag.className = "source-file";
      fileTag.title = src.source_file;
      fileTag.textContent = src.source_file;
      right.appendChild(fileTag);
    }

    const text = document.createElement("span");
    text.className = "source-text";
    text.textContent = src.content;
    right.appendChild(text);

    item.appendChild(score);
    item.appendChild(right);
    wrapper.appendChild(item);
  }

  return wrapper;
}

/* ── Utilities ───────────────────────────────────────────────────────── */

function showError(message) {
  clearWelcome();
  const el = document.createElement("div");
  el.className = "message-error";
  el.textContent = message;
  messages.appendChild(el);
  scrollToBottom();
}

function scrollToBottom() {
  messages.scrollTop = messages.scrollHeight;
}

/* ── Init ────────────────────────────────────────────────────────────── */

loadKnowledgeBase();
initReranker();
initTurboQuant();
