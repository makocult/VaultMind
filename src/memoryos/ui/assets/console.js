const elements = {
  agentSelect: document.querySelector("#agent-select"),
  apiKeyInput: document.querySelector("#api-key-input"),
  connectionDot: document.querySelector("#connection-dot"),
  readySummary: document.querySelector("#ready-summary"),
  metricService: document.querySelector("#metric-service"),
  metricDataRoot: document.querySelector("#metric-data-root"),
  metricPending: document.querySelector("#metric-pending"),
  metricMemories: document.querySelector("#metric-memories"),
  metricContexts: document.querySelector("#metric-contexts"),
  retrievalResults: document.querySelector("#retrieval-results"),
  memoryList: document.querySelector("#memory-list"),
  memoryDetail: document.querySelector("#memory-detail"),
  candidateList: document.querySelector("#candidate-list"),
  contextResult: document.querySelector("#context-result"),
  maintenanceResult: document.querySelector("#maintenance-result"),
  toast: document.querySelector("#toast"),
  retrieveQuery: document.querySelector("#retrieve-query"),
  retrieveMode: document.querySelector("#retrieve-mode"),
  retrieveLimit: document.querySelector("#retrieve-limit"),
  retrieveSession: document.querySelector("#retrieve-session"),
  retrieveTopic: document.querySelector("#retrieve-topic"),
  retrieveBody: document.querySelector("#retrieve-body"),
  memoryQuery: document.querySelector("#memory-query"),
  memoryTags: document.querySelector("#memory-tags"),
  memoryEntities: document.querySelector("#memory-entities"),
  memoryLimit: document.querySelector("#memory-limit"),
  contextSession: document.querySelector("#context-session"),
  contextTopic: document.querySelector("#context-topic"),
};

const STORAGE_KEY = "vaultmind-console-connection";

function loadConnection() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveConnection() {
  const payload = {
    agent: elements.agentSelect.value,
    apiKey: elements.apiKeyInput.value.trim(),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  toast("连接信息已保存");
}

function authHeaders() {
  const apiKey = elements.apiKeyInput.value.trim();
  const agent = elements.agentSelect.value;
  if (!apiKey || !agent) {
    throw new Error("请先选择 Agent 并输入对应 API Key。");
  }
  return {
    "X-Api-Key": apiKey,
    "X-Agent-Id": agent,
    "Content-Type": "application/json",
  };
}

async function fetchJson(url, options = {}, requiresAuth = false) {
  const merged = { ...options, headers: { ...(options.headers || {}) } };
  if (requiresAuth) {
    merged.headers = { ...merged.headers, ...authHeaders() };
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

function parseCsv(value) {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function checkedTypes() {
  return Array.from(document.querySelectorAll(".chip input[type='checkbox'][value]:checked")).map((node) => node.value);
}

function toast(message, isError = false) {
  elements.toast.hidden = false;
  elements.toast.textContent = message;
  elements.toast.style.background = isError ? "rgba(181, 61, 50, 0.96)" : "rgba(25, 35, 34, 0.94)";
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    elements.toast.hidden = true;
  }, 2800);
}

function setConnectionReady(ready) {
  elements.connectionDot.classList.toggle("is-ready", Boolean(ready));
}

function renderPills(values = []) {
  if (!values.length) {
    return "";
  }
  return `<div class="meta-line">${values.map((value) => `<span class="meta-pill">${escapeHtml(value)}</span>`).join("")}</div>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderJson(target, payload) {
  target.textContent = JSON.stringify(payload, null, 2);
}

async function loadReadyState() {
  const ready = await fetchJson("/readyz");
  const options = ready.agents
    .map((agent) => `<option value="${escapeHtml(agent)}">${escapeHtml(agent)}</option>`)
    .join("");
  elements.agentSelect.innerHTML = options;

  const stored = loadConnection();
  if (stored.agent && ready.agents.includes(stored.agent)) {
    elements.agentSelect.value = stored.agent;
  }
  if (stored.apiKey) {
    elements.apiKeyInput.value = stored.apiKey;
  }

  elements.readySummary.textContent = `服务已就绪，共管理 ${ready.agents.length} 个 Agent。当前数据根目录：${ready.data_root}`;
  elements.metricService.textContent = ready.status;
  elements.metricDataRoot.textContent = ready.data_root;
  return ready;
}

async function refreshOverview() {
  try {
    const ready = await loadReadyState();
    const stats = await fetchJson("/api/v1/maintenance/stats", {}, true);
    setConnectionReady(true);
    elements.metricService.textContent = ready.status;
    elements.metricPending.textContent = stats.pending_candidates;
    elements.metricMemories.textContent = stats.committed_memories;
    elements.metricContexts.textContent = stats.active_contexts;
  } catch (error) {
    setConnectionReady(false);
    toast(error.message, true);
  }
}

function resultCard(memory) {
  return `
    <article class="result-card">
      <h3>${escapeHtml(memory.summary || memory.id)}</h3>
      <p>${escapeHtml(memory.body || "")}</p>
      ${renderPills([memory.memory_type, ...(memory.tags || []), ...(memory.entities || []).map((item) => `entity:${item}`)])}
    </article>
  `;
}

async function runRetrieval() {
  try {
    const payload = {
      query: elements.retrieveQuery.value.trim(),
      mode: elements.retrieveMode.value,
      limit: Number(elements.retrieveLimit.value || 5),
      include_body: elements.retrieveBody.checked,
      session_id: elements.retrieveSession.value.trim() || null,
      current_topic: elements.retrieveTopic.value.trim() || null,
      memory_types: checkedTypes(),
    };
    if (!payload.query) {
      throw new Error("请输入检索查询。");
    }
    const result = await fetchJson("/api/v1/memory/retrieve", {
      method: "POST",
      body: JSON.stringify(payload),
    }, true);
    elements.retrievalResults.innerHTML = result.results.length
      ? result.results.map(resultCard).join("")
      : `<div class="empty-state">没有命中结果。</div>`;
    toast(`检索完成：${result.results.length} 条结果`);
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadMemories() {
  try {
    const payload = {
      limit: Number(elements.memoryLimit.value || 12),
      query: elements.memoryQuery.value.trim() || null,
      tags: parseCsv(elements.memoryTags.value),
      entities: parseCsv(elements.memoryEntities.value),
      memory_types: [],
    };
    const memories = await fetchJson("/api/v1/memory/list", {
      method: "POST",
      body: JSON.stringify(payload),
    }, true);
    elements.memoryList.innerHTML = memories.length
      ? memories
          .map(
            (memory) => `
              <article class="list-card" data-memory-id="${memory.id}">
                <h3>${escapeHtml(memory.summary)}</h3>
                <p>${escapeHtml(memory.memory_type)} · ${escapeHtml(memory.timestamp)}</p>
                ${renderPills(memory.tags || [])}
              </article>
            `,
          )
          .join("")
      : `<div class="empty-state">当前条件下没有记忆。</div>`;
    elements.memoryList.querySelectorAll("[data-memory-id]").forEach((card) => {
      card.addEventListener("click", () => loadMemoryDetail(card.dataset.memoryId, card));
    });
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadMemoryDetail(memoryId, activeCard = null) {
  try {
    const memory = await fetchJson(`/api/v1/memory/${memoryId}?include_body=true`, {}, true);
    elements.memoryDetail.innerHTML = `
      <h3>${escapeHtml(memory.summary)}</h3>
      <p>${escapeHtml(memory.body || "")}</p>
      ${renderPills([memory.memory_type, `session:${memory.session_id}`, ...(memory.tags || []), ...(memory.entities || []).map((entity) => `entity:${entity}`)])}
      <pre class="json-block">${escapeHtml(JSON.stringify(memory, null, 2))}</pre>
    `;
    document.querySelectorAll(".list-card").forEach((card) => card.classList.remove("is-active"));
    activeCard?.classList.add("is-active");
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadCandidates(status = null) {
  try {
    const query = new URLSearchParams({ limit: "30" });
    if (status) {
      query.set("status", status);
    }
    const candidates = await fetchJson(`/api/v1/candidate/list?${query.toString()}`, {}, true);
    elements.candidateList.innerHTML = candidates.length
      ? candidates
          .map(
            (candidate) => `
              <article class="result-card">
                <h3>${escapeHtml(candidate.summary)}</h3>
                <p>${escapeHtml(candidate.text)}</p>
                ${renderPills([candidate.status, `session:${candidate.session_id}`, ...(candidate.tags || [])])}
              </article>
            `,
          )
          .join("")
      : `<div class="empty-state">没有候选记录。</div>`;
  } catch (error) {
    toast(error.message, true);
  }
}

async function readContext() {
  try {
    const sessionId = elements.contextSession.value.trim();
    if (!sessionId) {
      throw new Error("请输入 session_id。");
    }
    const context = await fetchJson(`/api/v1/active-context?session_id=${encodeURIComponent(sessionId)}`, {}, true);
    renderJson(elements.contextResult, context);
  } catch (error) {
    toast(error.message, true);
  }
}

async function refreshContext() {
  try {
    const sessionId = elements.contextSession.value.trim();
    if (!sessionId) {
      throw new Error("请输入 session_id。");
    }
    const payload = {
      session_id: sessionId,
      current_topic: elements.contextTopic.value.trim() || null,
    };
    const context = await fetchJson("/api/v1/active-context/refresh", {
      method: "POST",
      body: JSON.stringify(payload),
    }, true);
    renderJson(elements.contextResult, context);
    toast("Active context 已刷新");
  } catch (error) {
    toast(error.message, true);
  }
}

async function resetContext() {
  try {
    const sessionId = elements.contextSession.value.trim();
    if (!sessionId) {
      throw new Error("请输入 session_id。");
    }
    const result = await fetchJson("/api/v1/active-context/reset", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    }, true);
    renderJson(elements.contextResult, result);
    toast("Active context 已重置");
  } catch (error) {
    toast(error.message, true);
  }
}

async function flushQueue() {
  try {
    const result = await fetchJson("/api/v1/maintenance/flush-queue", {
      method: "POST",
      body: JSON.stringify({ limit: 50 }),
    }, true);
    renderJson(elements.maintenanceResult, result);
    refreshOverview();
  } catch (error) {
    toast(error.message, true);
  }
}

async function rebuildIndex() {
  try {
    const result = await fetchJson("/api/v1/maintenance/rebuild-index", {
      method: "POST",
    }, true);
    renderJson(elements.maintenanceResult, result);
    toast("索引重建完成");
  } catch (error) {
    toast(error.message, true);
  }
}

function bindEvents() {
  document.querySelector("#save-connection").addEventListener("click", saveConnection);
  document.querySelector("#check-connection").addEventListener("click", refreshOverview);
  document.querySelector("#refresh-overview").addEventListener("click", refreshOverview);
  document.querySelector("#run-retrieval").addEventListener("click", runRetrieval);
  document.querySelector("#list-memories").addEventListener("click", loadMemories);
  document.querySelector("#load-pending").addEventListener("click", () => loadCandidates("pending"));
  document.querySelector("#load-all-candidates").addEventListener("click", () => loadCandidates(null));
  document.querySelector("#load-context").addEventListener("click", readContext);
  document.querySelector("#refresh-context").addEventListener("click", refreshContext);
  document.querySelector("#reset-context").addEventListener("click", resetContext);
  document.querySelector("#flush-queue").addEventListener("click", flushQueue);
  document.querySelector("#rebuild-index").addEventListener("click", rebuildIndex);
}

async function bootstrap() {
  bindEvents();
  await loadReadyState();
  const stored = loadConnection();
  if (stored.agent && stored.apiKey) {
    await refreshOverview();
    await loadMemories();
    await loadCandidates("pending");
  }
}

bootstrap().catch((error) => toast(error.message, true));
