const state = {
  documents: [],
  archives: [],
  pending: Object.create(null),
  selectedFile: null,
  snapshotCanBuild: false,
  chatActivityStartedAt: null,
  chatActivityTimer: null,
};

const elements = {
  status: document.querySelector("#status"),
  documents: document.querySelector("#documents"),
  documentCount: document.querySelector("#document-count"),
  snapshotArchives: document.querySelector("#snapshot-archives"),
  archiveCount: document.querySelector("#archive-count"),
  messages: document.querySelector("#messages"),
  chatActivity: document.querySelector("#chat-activity"),
  chatActivityText: document.querySelector("#chat-activity-text"),
  refresh: document.querySelector("#refresh"),
  chatForm: document.querySelector("#chat-form"),
  chatMessage: document.querySelector("#chat-message"),
  ingestForm: document.querySelector("#ingest-form"),
  documentFile: document.querySelector("#document-file"),
  snapshotForm: document.querySelector("#snapshot-form"),
  snapshotStatus: document.querySelector("#snapshot-status"),
  versionLabel: document.querySelector("#version-label"),
  snapshotId: document.querySelector("#snapshot-id"),
};

elements.refresh.addEventListener("click", () => {
  refresh().catch((error) => addMessage("system", formatError(error)));
});
elements.chatForm.addEventListener("submit", sendChat);
elements.ingestForm.addEventListener("submit", ingestDocument);
elements.documentFile.addEventListener("change", loadDocumentFile);
elements.snapshotForm.addEventListener("submit", buildSnapshot);

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => selectTab(tab.dataset.tab));
}

elements.versionLabel.value = `${datePart()}-001`;
elements.snapshotId.value = `snapshot-${datePart()}.001`;

renderStatus();
renderDocuments();
renderSnapshotArchives();
renderSnapshotStatus();
addMessage("system", "Ready. Status and document registry are loading.");
refresh().catch((error) => addMessage("system", formatError(error)));

async function refresh() {
  return withPending("refresh", [elements.refresh], async () => {
    const [status, docs, snapshot, archives] = await Promise.all([
      api("/api/status"),
      api("/api/documents"),
      api("/api/snapshots/status"),
      api("/api/maintenance/snapshot-archives"),
    ]);
    renderStatus(status);
    renderSnapshotStatus(snapshot);
    state.documents = Array.isArray(docs.documents) ? docs.documents : [];
    state.archives = Array.isArray(archives.archives) ? archives.archives : [];
    renderDocuments();
    renderSnapshotArchives();
  });
}

async function sendChat(event) {
  event.preventDefault();
  if (state.pending.chat) {
    return;
  }

  const message = elements.chatMessage.value.trim();
  if (!message) {
    return;
  }

  elements.chatMessage.value = "";
  addMessage("user", message);

  await withPending("chat", [elements.chatForm.querySelector("button")], async () => {
    setChatActivity(true);
    try {
      const response = await api("/api/chat", {
        method: "POST",
        body: { message },
      });
      addMessage("agent", responseText(response, "Hermes returned an empty response."));
    } catch (error) {
      addMessage("system", formatError(error));
    } finally {
      setChatActivity(false);
    }
  });
}

async function ingestDocument(event) {
  event.preventDefault();
  const body = {
    document_key: formValue(elements.ingestForm, "document_key"),
    version_label: formValue(elements.ingestForm, "version_label"),
    title: formValue(elements.ingestForm, "title"),
    text: elements.ingestForm.elements.text.value.trim(),
  };

  await withPending("ingest", [elements.ingestForm.querySelector("button")], async () => {
    try {
      const response = state.selectedFile
        ? await ingestSelectedFile(body)
        : await api("/api/ingest", { method: "POST", body });
      addMessage("agent", responseText(response, "Ingest request completed."));
      elements.versionLabel.value = nextPatchLabel(body.version_label);
      clearSelectedFile();
      await refresh();
    } catch (error) {
      addMessage("system", formatError(error));
    }
  });
}

async function loadDocumentFile(event) {
  const [file] = event.target.files || [];
  if (!file) {
    clearSelectedFile();
    return;
  }

  try {
    state.selectedFile = file;
    if (!formValue(elements.ingestForm, "document_key")) {
      elements.ingestForm.elements.document_key.value = documentKeyFromFilename(file.name);
    }
    if (!formValue(elements.ingestForm, "title")) {
      elements.ingestForm.elements.title.value = titleFromFilename(file.name);
    }
    if (isTextLikeFile(file)) {
      elements.ingestForm.elements.text.value = await readTextFile(file);
    } else {
      elements.ingestForm.elements.text.value = `Attached file: ${file.name}`;
    }
    addMessage("system", `Selected ${file.name}. Review the fields, then ingest this version.`);
  } catch (error) {
    clearSelectedFile();
    addMessage("system", formatError(error));
  }
}

async function ingestSelectedFile(body) {
  if (!state.selectedFile) {
    throw new Error("No file selected.");
  }

  const formData = new FormData();
  formData.append("document_key", body.document_key);
  formData.append("version_label", body.version_label);
  formData.append("file", state.selectedFile, state.selectedFile.name);
  return apiForm("/api/ingest-file", formData);
}

async function buildSnapshot(event) {
  event.preventDefault();
  const snapshotId = formValue(elements.snapshotForm, "snapshot_id");

  await withPending("snapshot", [elements.snapshotForm.querySelector("button")], async () => {
    try {
      const response = await api("/api/snapshots/build", {
        method: "POST",
        body: { snapshot_id: snapshotId },
      });
      addMessage("agent", responseText(response, "Snapshot build request completed."));
      await refresh();
    } catch (error) {
      addMessage("system", formatError(error));
    }
  });
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      method: options.method || "GET",
      headers: { "Content-Type": "application/json" },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch (error) {
    throw new Error(`Request failed for ${path}: ${error.message}`);
  }

  const text = await response.text();
  const payload = parseJson(text);

  if (!response.ok) {
    throw new Error(errorMessage(path, response.status, payload, text));
  }

  if (payload === null) {
    return {};
  }
  return payload;
}

async function apiForm(path, formData) {
  let response;
  try {
    response = await fetch(path, {
      method: "POST",
      body: formData,
    });
  } catch (error) {
    throw new Error(`Request failed for ${path}: ${error.message}`);
  }

  const text = await response.text();
  const payload = parseJson(text);

  if (!response.ok) {
    throw new Error(errorMessage(path, response.status, payload, text));
  }

  return payload === null ? {} : payload;
}

function renderStatus(status = null) {
  if (!status) {
    elements.status.replaceChildren(
      statusItem("MCP", "Loading", "warn"),
      statusItem("Pipeline", "Loading", "warn"),
      statusItem("Indexed docs", "Loading", "warn"),
    );
    return;
  }

  const mcp = isObject(status.mcp) ? status.mcp : {};
  const pipeline = isObject(status.pipeline) ? status.pipeline : {};
  const configured = status.hermes_configured !== false;

  const items = [
    statusItem("MCP", mcp.status || status.state || "unknown", status.state === "ok" ? "ok" : "warn"),
    statusItem("Pipeline", pipeline.busy ? "Busy" : "Idle", pipeline.busy ? "warn" : "ok"),
    statusItem("Indexed docs", String(pipeline.docs ?? 0), "ok"),
    statusItem("Hermes", configured ? "Configured" : "Needs configuration", configured ? "ok" : "error"),
  ];

  if (status.hermes_error) {
    items.push(statusItem("Configuration", status.hermes_error, "error"));
  }

  elements.status.replaceChildren(...items);
}

function renderDocuments() {
  const count = state.documents.length;
  elements.documentCount.textContent = `${count} ${count === 1 ? "document" : "documents"}`;

  if (count === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No document versions are registered yet.";
    elements.documents.replaceChildren(empty);
    return;
  }

  const rows = state.documents.map((documentRecord) => {
    const row = document.createElement("article");
    row.className = "doc-row";

    const header = document.createElement("div");
    header.className = "doc-row-header";

    const key = document.createElement("div");
    key.className = "doc-key";
    key.textContent = documentRecord.document_key || "untitled";

    const latest = document.createElement("span");
    latest.className = "pill ok";
    latest.textContent = `latest ${documentRecord.latest_version_label || "unknown"}`;

    header.append(key, latest);

    const versions = document.createElement("div");
    versions.className = "version-list";

    for (const version of normalizeVersions(documentRecord)) {
      const pill = document.createElement("span");
      pill.className = version.searchable ? "pill ok" : "pill";
      pill.textContent = version.searchable
        ? `${version.label} latest/searchable`
        : `${version.label} archived/non-searchable`;
      versions.append(pill);
    }

    row.append(header, versions);
    return row;
  });

  elements.documents.replaceChildren(...rows);
}

function renderSnapshotArchives() {
  if (!elements.snapshotArchives || !elements.archiveCount) {
    return;
  }

  const count = state.archives.length;
  elements.archiveCount.textContent = `${count} ${count === 1 ? "archive" : "archives"}`;

  if (count === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No archived snapshots are available for cleanup.";
    elements.snapshotArchives.replaceChildren(empty);
    return;
  }

  const rows = state.archives.map((archive) => {
    const row = document.createElement("article");
    row.className = "doc-row archive-row";

    const header = document.createElement("div");
    header.className = "doc-row-header";

    const name = document.createElement("div");
    name.className = "doc-key";
    name.textContent = archive.name || "unknown";

    const size = document.createElement("span");
    size.className = "pill";
    size.textContent = formatBytes(Number(archive.size_bytes || 0));

    header.append(name, size);

    const controls = document.createElement("div");
    controls.className = "archive-delete";

    const label = document.createElement("label");
    const labelText = document.createElement("span");
    labelText.textContent = "Type archive name to delete";
    const input = document.createElement("input");
    input.name = "confirmation";
    input.autocomplete = "off";
    input.placeholder = archive.name || "";
    label.append(labelText, input);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "danger-button";
    button.textContent = "Delete archive";
    button.disabled = true;

    input.addEventListener("input", () => {
      button.disabled = input.value.trim() !== archive.name;
    });
    button.addEventListener("click", () => {
      deleteSnapshotArchive(archive.name, input.value.trim()).catch((error) => {
        addMessage("system", formatError(error));
      });
    });

    controls.append(label, button);
    row.append(header, controls);
    return row;
  });

  elements.snapshotArchives.replaceChildren(...rows);
}

function renderSnapshotStatus(snapshot = null) {
  if (!elements.snapshotStatus) {
    return;
  }
  if (!snapshot) {
    elements.snapshotStatus.replaceChildren(statusItem("Snapshot target", "Loading", "warn"));
    return;
  }

  const targetTone = snapshot.can_build ? "ok" : "warn";
  const active = snapshot.active_snapshot;
  const activeLabel = active && active.snapshot_id ? active.snapshot_id : "None";
  state.snapshotCanBuild = Boolean(snapshot.can_build);
  elements.snapshotForm.querySelector("button").disabled = !state.snapshotCanBuild;
  elements.snapshotStatus.replaceChildren(
    statusItem("Snapshot target", snapshot.reason || snapshot.state || "unknown", targetTone),
    statusItem("Archived latest docs", String(snapshot.archived_document_count ?? 0), "ok"),
    statusItem("Target indexed docs", String(snapshot.target_document_count ?? 0), targetTone),
    statusItem("Active snapshot", activeLabel, active ? "ok" : "warn"),
  );
}

function statusItem(label, value, tone) {
  const item = document.createElement("div");
  item.className = "status-item";

  const labelEl = document.createElement("div");
  labelEl.className = "status-label";
  labelEl.textContent = label;

  const valueEl = document.createElement("div");
  valueEl.className = "status-value";

  const pill = document.createElement("span");
  pill.className = `pill ${tone || ""}`.trim();
  pill.textContent = value;
  valueEl.append(pill);

  item.append(labelEl, valueEl);
  return item;
}

function addMessage(role, text) {
  const node = document.createElement("div");
  node.className = `message ${role}`;

  const roleEl = document.createElement("div");
  roleEl.className = "message-role";
  roleEl.textContent = role;

  const textEl = document.createElement("div");
  textEl.textContent = text;

  node.append(roleEl, textEl);
  elements.messages.append(node);
  scrollMessagesToBottom();
}

function setChatActivity(isActive) {
  if (!elements.chatActivity) {
    return;
  }
  elements.chatActivity.hidden = !isActive;
  if (isActive) {
    if (state.chatActivityTimer) {
      window.clearInterval(state.chatActivityTimer);
    }
    state.chatActivityStartedAt = Date.now();
    updateChatActivityText();
    state.chatActivityTimer = window.setInterval(updateChatActivityText, 1000);
    scrollMessagesToBottom();
    return;
  }

  if (state.chatActivityTimer) {
    window.clearInterval(state.chatActivityTimer);
    state.chatActivityTimer = null;
  }
  state.chatActivityStartedAt = null;
  if (elements.chatActivityText) {
    elements.chatActivityText.textContent = "Hermes is thinking...";
  }
}

function scrollMessagesToBottom() {
  requestAnimationFrame(() => {
    elements.messages.scrollTop = elements.messages.scrollHeight;
  });
}

function updateChatActivityText() {
  if (!elements.chatActivityText || !state.chatActivityStartedAt) {
    return;
  }

  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - state.chatActivityStartedAt) / 1000));
  let label = "Hermes is thinking";
  if (elapsedSeconds >= 20) {
    label = "Hermes is still working";
  } else if (elapsedSeconds >= 8) {
    label = "Hermes is checking tools";
  }

  elements.chatActivityText.textContent = `${label} (${elapsedSeconds}s)`;
}

function selectTab(tabName) {
  for (const tab of document.querySelectorAll(".tab")) {
    const active = tab.dataset.tab === tabName;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  }

  document.querySelector("#documents-tab").hidden = tabName !== "documents";
  document.querySelector("#snapshot-tab").hidden = tabName !== "snapshot";
  document.querySelector("#maintenance-tab").hidden = tabName !== "maintenance";
}

async function deleteSnapshotArchive(archiveName, confirmation) {
  await withPending("archive-delete", [], async () => {
    const response = await api(
      `/api/maintenance/snapshot-archives/${encodeURIComponent(archiveName)}`,
      {
        method: "DELETE",
        body: { confirmation },
      },
    );
    addMessage("system", responseText(response, "Snapshot archive deleted."));
    await refresh();
  });
}

async function withPending(key, buttons, task) {
  if (state.pending[key]) {
    return;
  }

  state.pending[key] = true;
  for (const button of buttons) {
    button.disabled = true;
  }

  try {
    await task();
  } finally {
    state.pending[key] = false;
    for (const button of buttons) {
      button.disabled = false;
    }
  }
}

function normalizeVersions(documentRecord) {
  const versions = Array.isArray(documentRecord.versions) ? documentRecord.versions : [];
  return versions.map((version) => {
    if (isObject(version)) {
      return {
        label: String(version.label || "unknown"),
        searchable: Boolean(version.searchable),
      };
    }

    const label = String(version || "unknown");
    return {
      label,
      searchable: label === documentRecord.latest_version_label,
    };
  });
}

function responseText(response, fallback) {
  if (!isObject(response)) {
    return fallback;
  }
  return response.text || response.message || response.detail || fallback;
}

function formatError(error) {
  return error && error.message ? error.message : "Request failed.";
}

function errorMessage(path, status, payload, text) {
  if (isObject(payload)) {
    if (typeof payload.detail === "string") {
      return `${path} failed (${status}): ${payload.detail}`;
    }
    if (Array.isArray(payload.detail)) {
      return `${path} failed (${status}): ${payload.detail.map((item) => item.msg || "validation error").join("; ")}`;
    }
    if (typeof payload.message === "string") {
      return `${path} failed (${status}): ${payload.message}`;
    }
  }

  return `${path} failed (${status}): ${text || "no response body"}`;
}

function parseJson(text) {
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function formValue(form, name) {
  return form.elements[name].value.trim();
}

function readTextFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result || "")));
    reader.addEventListener("error", () => reject(new Error(`Could not read ${file.name}.`)));
    reader.readAsText(file);
  });
}

function clearSelectedFile() {
  state.selectedFile = null;
  elements.documentFile.value = "";
}

function isTextLikeFile(file) {
  const name = file.name.toLowerCase();
  if (file.type && file.type.startsWith("text/")) {
    return true;
  }
  return [".md", ".markdown", ".txt", ".csv", ".json", ".log"].some((ext) => name.endsWith(ext));
}

function documentKeyFromFilename(filename) {
  const stem = filename.replace(/\.[^.]+$/, "");
  const key = stem
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return key || "document";
}

function titleFromFilename(filename) {
  return filename.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").trim() || "Document";
}

function datePart() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function nextPatchLabel(label) {
  const match = /^(\d{4}-\d{2}-\d{2})-(\d{3})$/.exec(label);
  if (!match) {
    return `${datePart()}-001`;
  }

  const next = String(Number(match[2]) + 1).padStart(3, "0");
  return `${match[1]}-${next}`;
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
