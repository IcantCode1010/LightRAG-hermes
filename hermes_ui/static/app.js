const state = {
  documents: [],
  pending: Object.create(null),
};

const elements = {
  status: document.querySelector("#status"),
  documents: document.querySelector("#documents"),
  documentCount: document.querySelector("#document-count"),
  messages: document.querySelector("#messages"),
  refresh: document.querySelector("#refresh"),
  chatForm: document.querySelector("#chat-form"),
  chatMessage: document.querySelector("#chat-message"),
  ingestForm: document.querySelector("#ingest-form"),
  snapshotForm: document.querySelector("#snapshot-form"),
  versionLabel: document.querySelector("#version-label"),
  snapshotId: document.querySelector("#snapshot-id"),
};

elements.refresh.addEventListener("click", () => {
  refresh().catch((error) => addMessage("system", formatError(error)));
});
elements.chatForm.addEventListener("submit", sendChat);
elements.ingestForm.addEventListener("submit", ingestDocument);
elements.snapshotForm.addEventListener("submit", buildSnapshot);

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => selectTab(tab.dataset.tab));
}

elements.versionLabel.value = `v${datePart()}.001`;
elements.snapshotId.value = `snapshot-${datePart()}.001`;

renderStatus();
renderDocuments();
addMessage("system", "Ready. Status and document registry are loading.");
refresh().catch((error) => addMessage("system", formatError(error)));

async function refresh() {
  return withPending("refresh", [elements.refresh], async () => {
    const [status, docs] = await Promise.all([
      api("/api/status"),
      api("/api/documents"),
    ]);
    renderStatus(status);
    state.documents = Array.isArray(docs.documents) ? docs.documents : [];
    renderDocuments();
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
    try {
      const response = await api("/api/chat", {
        method: "POST",
        body: { message },
      });
      addMessage("agent", responseText(response, "Hermes returned an empty response."));
    } catch (error) {
      addMessage("system", formatError(error));
    }
  });
}

async function ingestDocument(event) {
  event.preventDefault();
  const body = {
    document_key: formValue(elements.ingestForm, "document_key"),
    version_label: formValue(elements.ingestForm, "version_label"),
    title: formValue(elements.ingestForm, "title"),
    text: elements.ingestForm.elements.text.value,
  };

  await withPending("ingest", [elements.ingestForm.querySelector("button")], async () => {
    try {
      const response = await api("/api/ingest", { method: "POST", body });
      addMessage("agent", responseText(response, "Ingest request completed."));
      elements.versionLabel.value = nextPatchLabel(body.version_label);
      await refresh();
    } catch (error) {
      addMessage("system", formatError(error));
    }
  });
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
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function selectTab(tabName) {
  for (const tab of document.querySelectorAll(".tab")) {
    const active = tab.dataset.tab === tabName;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  }

  document.querySelector("#documents-tab").hidden = tabName !== "documents";
  document.querySelector("#snapshot-tab").hidden = tabName !== "snapshot";
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

function datePart() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}.${month}.${day}`;
}

function nextPatchLabel(label) {
  const match = /^v(\d{4}\.\d{2}\.\d{2})\.(\d{3})$/.exec(label);
  if (!match) {
    return `v${datePart()}.001`;
  }

  const next = String(Number(match[2]) + 1).padStart(3, "0");
  return `v${match[1]}.${next}`;
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
