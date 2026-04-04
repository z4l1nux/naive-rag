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
            body.appendChild(buildSources(event.sources));
          }
          scrollToBottom();
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
