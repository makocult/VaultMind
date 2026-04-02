const elements = {
  agentSelect: document.querySelector("#agent-select"),
  apiKeyRow: document.querySelector("#api-key-row"),
  apiKeyInput: document.querySelector("#api-key-input"),
  authHint: document.querySelector("#auth-hint"),
  connectionDot: document.querySelector("#connection-dot"),
  readySummary: document.querySelector("#ready-summary"),
  metricService: document.querySelector("#metric-service"),
  metricDefaultAgent: document.querySelector("#metric-default-agent"),
  metricMemories: document.querySelector("#metric-memories"),
  metricDataRoot: document.querySelector("#metric-data-root"),
  memoryQuery: document.querySelector("#memory-query"),
  memoryTypeFilter: document.querySelector("#memory-type-filter"),
  memoryList: document.querySelector("#memory-list"),
  memoryCount: document.querySelector("#memory-count"),
  memoryDetail: document.querySelector("#memory-detail"),
  editorTitle: document.querySelector("#editor-title"),
  editorStatus: document.querySelector("#editor-status"),
  form: document.querySelector("#memory-form"),
  formSummary: document.querySelector("#form-summary"),
  formBody: document.querySelector("#form-body"),
  formMemoryType: document.querySelector("#form-memory-type"),
  formSessionId: document.querySelector("#form-session-id"),
  formTimestamp: document.querySelector("#form-timestamp"),
  formSourceType: document.querySelector("#form-source-type"),
  formTags: document.querySelector("#form-tags"),
  formEntities: document.querySelector("#form-entities"),
  deleteMemory: document.querySelector("#delete-memory"),
  toast: document.querySelector("#toast"),
};

const STORAGE_KEY = "vaultmind-console-connection";
const state = {
  authMode: "agent_header",
  currentMemoryId: null,
};

function loadConnection() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveConnection() {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      agent: elements.agentSelect.value,
      apiKey: elements.apiKeyInput.value.trim(),
    }),
  );
}

function parseCsv(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function toast(message, isError = false) {
  elements.toast.hidden = false;
  elements.toast.textContent = message;
  elements.toast.style.background = isError ? "rgba(178, 67, 53, 0.96)" : "rgba(25, 35, 34, 0.94)";
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    elements.toast.hidden = true;
  }, 2600);
}

function setConnectionReady(ready) {
  elements.connectionDot.classList.toggle("is-ready", Boolean(ready));
}

function renderPills(items = []) {
  if (!items.length) {
    return "";
  }
  return `<div class="meta-line">${items.map((item) => `<span class="meta-pill">${escapeHtml(item)}</span>`).join("")}</div>`;
}

function toDatetimeLocal(value) {
  if (!value) {
    return "";
  }
  const normalized = String(value).trim();
  if (normalized.endsWith("Z")) {
    return normalized.slice(0, 16);
  }
  const match = normalized.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})/);
  return match ? match[1] : normalized;
}

function currentHeaders() {
  const headers = { "Content-Type": "application/json" };
  const agent = elements.agentSelect.value.trim();
  const apiKey = elements.apiKeyInput.value.trim();

  if (!agent) {
    throw new Error("请选择一个 Agent。");
  }
  headers["X-Agent-Id"] = agent;

  if (apiKey) {
    headers["X-Api-Key"] = apiKey;
  } else if (state.authMode === "api_key") {
    throw new Error("当前服务要求 API key。");
  }

  return headers;
}

async function fetchJson(url, options = {}, requiresAuth = false) {
  const merged = { ...options, headers: { ...(options.headers || {}) } };
  if (requiresAuth) {
    merged.headers = { ...merged.headers, ...currentHeaders() };
  }
  const response = await fetch(url, merged);
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    const detail = typeof payload === "object" && payload ? payload.detail || payload.error : payload;
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return payload;
}

function formPayload() {
  return {
    session_id: elements.formSessionId.value.trim() || "manual-console",
    memory_type: elements.formMemoryType.value,
    timestamp: elements.formTimestamp.value || null,
    source_type: elements.formSourceType.value.trim() || "console-import",
    summary: elements.formSummary.value.trim(),
    body: elements.formBody.value.trim(),
    tags: parseCsv(elements.formTags.value),
    entities: parseCsv(elements.formEntities.value),
  };
}

function fillForm(memory = null) {
  if (!memory) {
    state.currentMemoryId = null;
    elements.editorTitle.textContent = "手动导入";
    elements.editorStatus.textContent = "新建";
    elements.formSummary.value = "";
    elements.formBody.value = "";
    elements.formMemoryType.value = "semantic";
    elements.formSessionId.value = "";
    elements.formTimestamp.value = "";
    elements.formSourceType.value = "console-import";
    elements.formTags.value = "";
    elements.formEntities.value = "";
    elements.deleteMemory.disabled = true;
    elements.memoryDetail.innerHTML = `<p class="detail-empty">选择左侧记忆后，这里会显示它的时间、类型、标签和正文概览。</p>`;
    document.querySelectorAll(".list-card").forEach((card) => card.classList.remove("is-active"));
    return;
  }

  state.currentMemoryId = memory.id;
  elements.editorTitle.textContent = "编辑记忆";
  elements.editorStatus.textContent = memory.id;
  elements.formSummary.value = memory.summary || "";
  elements.formBody.value = memory.body || "";
  elements.formMemoryType.value = memory.memory_type;
  elements.formSessionId.value = memory.session_id || "";
  elements.formTimestamp.value = toDatetimeLocal(memory.timestamp);
  elements.formSourceType.value = memory.source_type || "console-import";
  elements.formTags.value = (memory.tags || []).join(", ");
  elements.formEntities.value = (memory.entities || []).join(", ");
  elements.deleteMemory.disabled = false;
  renderMemoryDetail(memory);
}

function renderMemoryDetail(memory) {
  elements.memoryDetail.innerHTML = `
    <div class="detail-grid">
      <div class="detail-row">
        <span>摘要</span>
        <strong>${escapeHtml(memory.summary)}</strong>
      </div>
      <div class="detail-row">
        <span>时间</span>
        <strong>${escapeHtml(memory.timestamp)}</strong>
      </div>
      <div class="detail-row">
        <span>会话</span>
        <strong>${escapeHtml(memory.session_id)}</strong>
      </div>
      <div class="detail-row">
        <span>正文</span>
        <p>${escapeHtml(memory.body || "无正文")}</p>
      </div>
      ${renderPills([memory.memory_type, ...(memory.tags || []), ...(memory.entities || []).map((item) => `entity:${item}`)])}
    </div>
  `;
}

async function loadReadyState() {
  const ready = await fetchJson("/readyz");
  state.authMode = ready.auth_mode || "agent_header";

  const options = ready.agents
    .map((agent) => `<option value="${escapeHtml(agent)}">${escapeHtml(agent)}</option>`)
    .join("");
  elements.agentSelect.innerHTML = options;

  const stored = loadConnection();
  const fallbackAgent = ready.default_agent || ready.agents[0] || "";
  elements.agentSelect.value = ready.agents.includes(stored.agent) ? stored.agent : fallbackAgent;
  elements.apiKeyInput.value = stored.apiKey || "";

  const requiresKey = state.authMode === "api_key";
  elements.apiKeyRow.classList.toggle("hidden", !requiresKey);
  elements.authHint.textContent = requiresKey
    ? "当前服务处于严格模式，需要输入 API key。"
    : "当前服务处于内网信任模式，只需切换 Agent 即可。";

  elements.readySummary.textContent = `当前共有 ${ready.agents.length} 个 Agent，默认 Agent 为 ${ready.default_agent}。`;
  elements.metricService.textContent = ready.status;
  elements.metricDefaultAgent.textContent = ready.default_agent;
  elements.metricDataRoot.textContent = ready.data_root;

  saveConnection();
  return ready;
}

async function refreshOverview() {
  try {
    const ready = await loadReadyState();
    const stats = await fetchJson("/api/v1/maintenance/stats", {}, true);
    setConnectionReady(true);
    elements.metricService.textContent = ready.status;
    elements.metricDefaultAgent.textContent = ready.default_agent;
    elements.metricMemories.textContent = String(stats.committed_memories);
  } catch (error) {
    setConnectionReady(false);
    toast(error.message, true);
  }
}

function memoryCard(memory) {
  return `
    <article class="list-card" data-memory-id="${memory.id}">
      <h3>${escapeHtml(memory.summary)}</h3>
      <p>${escapeHtml(memory.memory_type)} · ${escapeHtml(memory.timestamp)}</p>
      ${renderPills(memory.tags || [])}
    </article>
  `;
}

async function loadMemories() {
  try {
    const selectedId = state.currentMemoryId;
    const memoryTypes = elements.memoryTypeFilter.value ? [elements.memoryTypeFilter.value] : [];
    const memories = await fetchJson(
      "/api/v1/memory/list",
      {
        method: "POST",
        body: JSON.stringify({
          limit: 50,
          query: elements.memoryQuery.value.trim() || null,
          memory_types: memoryTypes,
          tags: [],
          entities: [],
        }),
      },
      true,
    );

    elements.memoryCount.textContent = `${memories.length} 条`;
    elements.memoryList.innerHTML = memories.length
      ? memories.map(memoryCard).join("")
      : `<div class="empty-state">当前筛选条件下没有记忆。</div>`;

    elements.memoryList.querySelectorAll("[data-memory-id]").forEach((card) => {
      card.addEventListener("click", () => loadMemoryDetail(card.dataset.memoryId, card));
    });

    if (selectedId) {
      const activeCard = elements.memoryList.querySelector(`[data-memory-id="${CSS.escape(selectedId)}"]`);
      if (activeCard) {
        await loadMemoryDetail(selectedId, activeCard, false);
      }
    }
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadMemoryDetail(memoryId, activeCard = null, notify = false) {
  try {
    const memory = await fetchJson(`/api/v1/memory/${memoryId}?include_body=true`, {}, true);
    fillForm(memory);
    document.querySelectorAll(".list-card").forEach((card) => card.classList.remove("is-active"));
    activeCard?.classList.add("is-active");
    if (notify) {
      toast("记忆已载入编辑器");
    }
  } catch (error) {
    toast(error.message, true);
  }
}

async function saveMemory(event) {
  event.preventDefault();
  try {
    const payload = formPayload();
    if (!payload.summary) {
      throw new Error("摘要不能为空。");
    }

    let memory = null;
    if (state.currentMemoryId) {
      memory = await fetchJson(
        `/api/v1/memory/${state.currentMemoryId}`,
        {
          method: "PATCH",
          body: JSON.stringify(payload),
        },
        true,
      );
      toast("记忆已更新");
    } else {
      memory = await fetchJson(
        "/api/v1/memory/create",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
        true,
      );
      toast("记忆已导入");
    }

    fillForm(memory);
    await loadMemories();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteMemory() {
  if (!state.currentMemoryId) {
    return;
  }
  try {
    const confirmed = window.confirm("确定删除这条记忆吗？");
    if (!confirmed) {
      return;
    }
    await fetchJson(`/api/v1/memory/${state.currentMemoryId}`, { method: "DELETE" }, true);
    fillForm(null);
    await loadMemories();
    toast("记忆已删除");
  } catch (error) {
    toast(error.message, true);
  }
}

function clearFilters() {
  elements.memoryQuery.value = "";
  elements.memoryTypeFilter.value = "";
  loadMemories();
}

function bindEvents() {
  document.querySelector("#refresh-overview").addEventListener("click", async () => {
    await refreshOverview();
    await loadMemories();
  });
  document.querySelector("#new-memory").addEventListener("click", () => fillForm(null));
  document.querySelector("#list-memories").addEventListener("click", loadMemories);
  document.querySelector("#clear-filters").addEventListener("click", clearFilters);
  document.querySelector("#reset-editor").addEventListener("click", () => fillForm(null));
  elements.deleteMemory.addEventListener("click", deleteMemory);
  elements.form.addEventListener("submit", saveMemory);

  elements.agentSelect.addEventListener("change", async () => {
    saveConnection();
    fillForm(null);
    await refreshOverview();
    await loadMemories();
  });

  elements.apiKeyInput.addEventListener("change", () => {
    saveConnection();
    refreshOverview();
  });

  elements.memoryQuery.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadMemories();
    }
  });
}

async function bootstrap() {
  bindEvents();
  fillForm(null);
  await refreshOverview();
  await loadMemories();
}

bootstrap().catch((error) => {
  setConnectionReady(false);
  toast(error.message, true);
});
