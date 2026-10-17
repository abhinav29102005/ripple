/**
 * Ripple Web Application Client (app.js)
 * Coordinates the 4 interactive panels with the FalkorDB API backend:
 * 1. Force-directed Graph Explorer (D3.js)
 * 2. Live Task Board with lease countdowns
 * 3. Tenant Memory & Procedural Rules Timeline
 * 4. Severity Alert Rankings, Analyst Tool Trace, and Cross-Session Chat
 */

let state = {
  tenant: "cardio",
  retractionId: "SYN-RET-001",
  session: null,
  tasks: [],
  rankings: [],
  activeRankingId: null,
};

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  refreshDashboard();
  // Auto-refresh task board every 3 seconds for live lease updates
  setInterval(fetchTasks, 3000);
});

function initEventListeners() {
  document.getElementById("tenant-select").addEventListener("change", (e) => {
    state.tenant = e.target.value;
    state.session = null; // reset session on tenant switch
    refreshDashboard();
  });

  document.getElementById("retraction-select").addEventListener("change", (e) => {
    state.retractionId = e.target.value;
    loadGraphData();
    fetchRankings();
  });
}

function refreshDashboard() {
  loadGraphData();
  fetchTasks();
  fetchMemory();
  fetchRankings();
}

// ==========================================
// Panel 1: D3 Interactive Force Graph
// ==========================================
let simulation = null;

async function loadGraphData() {
  try {
    const res = await fetch(`/api/graph/blast/${state.retractionId}`);
    const data = await res.json();
    document.getElementById("graph-node-count").innerText = `${data.nodes.length} nodes, ${data.edges.length} links`;
    renderD3Graph(data.nodes, data.edges);
  } catch (err) {
    console.error("Error loading blast graph:", err);
  }
}

function renderD3Graph(nodes, links) {
  const svg = d3.select("#blast-graph");
  svg.selectAll("*").remove();

  const width = svg.node().clientWidth || 600;
  const height = svg.node().clientHeight || 400;

  const g = svg.append("g");

  // Zoom behavior
  svg.call(d3.zoom().scaleExtent([0.3, 3]).on("zoom", (e) => {
    g.attr("transform", e.transform);
  }));

  // Node colors
  const colorMap = {
    Retraction: "#f43f5e",
    Trial: "#f59e0b",
    Review: "#06b6d4",
    Guideline: "#6366f1",
    Decision: "#a855f7",
  };

  simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(d => d.id).distance(75))
    .force("charge", d3.forceManyBody().strength(-200))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(25));

  // Edges
  const link = g.append("g")
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("stroke", "rgba(148, 163, 184, 0.3)")
    .attr("stroke-width", 1.5);

  // Nodes
  const node = g.append("g")
    .selectAll("circle")
    .data(nodes)
    .join("circle")
    .attr("r", d => d.label === "Retraction" ? 14 : d.label === "Review" ? 10 : 8)
    .attr("fill", d => colorMap[d.label] || "#94a3b8")
    .attr("stroke", "#0f172a")
    .attr("stroke-width", 2)
    .style("cursor", "pointer")
    .call(d3.drag()
      .on("start", (e, d) => {
        if (!e.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on("end", (e, d) => {
        if (!e.active) simulation.alphaTarget(0);
        d.fx = null; d.fy = null;
      })
    )
    .on("click", (e, d) => showInspector(d));

  // Labels
  const labels = g.append("g")
    .selectAll("text")
    .data(nodes)
    .join("text")
    .text(d => d.id)
    .attr("font-size", 9)
    .attr("font-family", "JetBrains Mono, monospace")
    .attr("fill", "#e2e8f0")
    .attr("dx", 12)
    .attr("dy", 4);

  simulation.on("tick", () => {
    link
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);

    node
      .attr("cx", d => d.x)
      .attr("cy", d => d.y);

    labels
      .attr("x", d => d.x)
      .attr("y", d => d.y);
  });
}

function resetGraphView() {
  loadGraphData();
}

function showInspector(node) {
  const inspector = document.getElementById("graph-inspector");
  inspector.classList.remove("hidden");
  document.getElementById("inspect-label").innerText = node.label || "Node";
  document.getElementById("inspect-title").innerText = node.id;

  let html = `<p><strong>Type:</strong> ${node.label}</p>`;
  if (node.yi !== undefined) html += `<p><strong>Pooled Effect (yi):</strong> ${node.yi}</p>`;
  if (node.sei !== undefined) html += `<p><strong>Standard Error (sei):</strong> ${node.sei}</p>`;
  if (node.status) html += `<p><strong>Status:</strong> ${node.status}</p>`;

  document.getElementById("inspect-details").innerHTML = html;
}

function closeInspector() {
  document.getElementById("graph-inspector").classList.add("hidden");
}

// ==========================================
// Panel 2: Live Coordination Board
// ==========================================
async function fetchTasks() {
  try {
    const res = await fetch("/api/tasks");
    const data = await res.json();
    state.tasks = data.tasks || [];
    renderTaskBoard(state.tasks);
  } catch (err) {
    console.error("Error fetching tasks:", err);
  }
}

function renderTaskBoard(tasks) {
  const cols = { queued: [], claimed: [], done: [], failed: [] };
  const now = Math.floor(Date.now() / 1000);

  tasks.forEach(t => {
    const s = t.status || "queued";
    if (cols[s]) cols[s].push(t);
  });

  ["queued", "claimed", "done", "failed"].forEach(col => {
    document.getElementById(`count-${col}`).innerText = cols[col].length;
    const container = document.getElementById(`cards-${col}`);
    container.innerHTML = "";

    cols[col].slice(0, 15).forEach(t => {
      const card = document.createElement("div");
      card.className = `task-card ${t.status}`;

      let timerHtml = "";
      if (t.status === "claimed" && t.lease_until) {
        const remaining = Math.max(0, t.lease_until - now);
        timerHtml = `<span class="lease-timer">⏳ ${remaining}s</span>`;
      }

      card.innerHTML = `
        <div class="task-card-header">
          <span class="badge badge-info">${t.type}</span>
          ${timerHtml}
        </div>
        <div class="task-id">${t.id}</div>
        <div style="font-size: 0.72rem; color: #94a3b8; margin-top: 0.2rem;">
          ${t.claimed_by ? `Agent: ${t.claimed_by}` : `Attempts: ${t.attempts}`}
        </div>
      `;
      container.appendChild(card);
    });
  });
}

async function triggerSimulatedTask() {
  try {
    const res = await fetch("/api/retractions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        retraction_id: `SIM-RET-${Date.now().toString().slice(-4)}`,
        trial_id: "SYN-TR-0001",
        reason: "Simulated worker stress test",
        reason_category: "administrative",
      }),
    });
    fetchTasks();
  } catch (err) {
    console.error(err);
  }
}

// ==========================================
// Panel 3: Memory & Rules
// ==========================================
async function fetchMemory() {
  try {
    const res = await fetch(`/api/tenants/${state.tenant}/memory`);
    const data = await res.json();
    renderMemory(data);
  } catch (err) {
    console.error("Error fetching memory:", err);
  }
}

function renderMemory(data) {
  const rulesList = document.getElementById("rules-list");
  const rules = data.active_rules || [];
  document.getElementById("active-rules-count").innerText = `${rules.length} Rules`;

  if (rules.length === 0) {
    rulesList.innerHTML = `<div class="empty-state">No rules consolidated yet. Dismiss or escalate alerts below to train the Librarian.</div>`;
  } else {
    rulesList.innerHTML = "";
    rules.forEach(r => {
      const el = document.createElement("div");
      el.className = "rule-card";
      el.innerHTML = `
        <div class="rule-header">
          <span>${r.id}</span>
          <span class="badge ${r.delta < 0 ? 'badge-danger' : 'badge-success'}">Δ ${r.delta > 0 ? '+' : ''}${r.delta}</span>
        </div>
        <div>${r.description}</div>
        <div style="font-size: 0.7rem; color: #64748b; margin-top: 0.2rem;">
          Support: ${r.support} episodes | Hit rate: ${(r.hit_rate * 100).toFixed(0)}%
        </div>
      `;
      rulesList.appendChild(el);
    });
  }

  // Facts
  const factsList = document.getElementById("facts-list");
  factsList.innerHTML = "";
  (data.facts || []).slice(0, 5).forEach(f => {
    const el = document.createElement("div");
    el.className = "fact-item";
    el.innerHTML = `
      <span class="fact-key">${f.key}:</span>
      <span>${f.value} ${f.supersedes_id ? '<span style="color:#64748b">(superseded)</span>' : ''}</span>
    `;
    factsList.appendChild(el);
  });

  // Episodes
  const epList = document.getElementById("episodes-list");
  epList.innerHTML = "";
  (data.episodes || []).slice(0, 6).forEach(e => {
    const el = document.createElement("div");
    el.className = "fact-item";
    el.innerHTML = `
      <span><span class="badge ${e.kind === 'dismiss' ? 'badge-warning' : 'badge-info'}">${e.kind}</span> ${e.ext_review}</span>
      <span style="color: #64748b; font-size: 0.7rem;">${e.reason}</span>
    `;
    epList.appendChild(el);
  });
}

// ==========================================
// Panel 4: Ranked Alerts & Actions
// ==========================================
async function fetchRankings() {
  try {
    const res = await fetch(`/api/tenants/${state.tenant}/rankings?retraction_id=${state.retractionId}`);
    const data = await res.json();
    state.rankings = data.ranked_alerts || [];
    state.activeRankingId = data.ranking_id;
    renderRankedAlerts(state.rankings);
  } catch (err) {
    console.error("Error fetching rankings:", err);
  }
}

function renderRankedAlerts(alerts) {
  const container = document.getElementById("alerts-list");
  container.innerHTML = "";

  if (alerts.length === 0) {
    container.innerHTML = `<div class="empty-state">No alerts flagged for this retraction.</div>`;
    return;
  }

  alerts.forEach(a => {
    const card = document.createElement("div");
    card.className = "alert-card";

    const scoreClass = a.score > 0.6 ? "score-high" : a.score > 0.3 ? "score-mid" : "score-low";

    card.innerHTML = `
      <div class="alert-header">
        <strong>${a.review_id}</strong>
        <div class="alert-scores">
          <span style="font-size: 0.72rem; color: #64748b;">Base: ${a.base}</span>
          <span class="score-badge ${scoreClass}">Score: ${a.score}</span>
        </div>
      </div>
      <div style="font-size: 0.8rem; color: #cbd5e1;">${a.title}</div>
      <div style="font-size: 0.72rem; color: #94a3b8; margin-top: 0.2rem;">
        Reason: <span style="color:#f43f5e">${a.reason_category}</span> | Weight share: ${(a.weight_share * 100).toFixed(0)}% | Flips: ${a.flips}
      </div>
      <div class="alert-actions">
        <button class="btn btn-xs btn-secondary" onclick="recordFeedback('${a.review_id}', 'dismiss', '${a.reason_category}', '${a.weight_bucket}', ${a.flips})">
          ✕ Dismiss
        </button>
        <button class="btn btn-xs btn-primary" onclick="recordFeedback('${a.review_id}', 'escalate', '${a.reason_category}', '${a.weight_bucket}', ${a.flips})">
          ▲ Escalate
        </button>
        <span class="why-expander" onclick="toggleWhy(this, '${a.review_id}')">Why this rank?</span>
      </div>
      <div class="why-details hidden" id="why-${a.review_id}">
        Loading explanation path from graph...
      </div>
    `;
    container.appendChild(card);
  });
}

async function recordFeedback(reviewId, kind, reason, weightBucket, flips) {
  try {
    const res = await fetch(`/api/tenants/${state.tenant}/episodes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.session,
        kind: kind,
        reason: reason,
        weight_bucket: weightBucket,
        flips: flips,
        ext_review: reviewId,
        ext_retraction: state.retractionId,
        notes: `User ${kind} action on alert`,
      }),
    });
    const data = await res.json();
    state.session = data.session_id;

    // Refresh memory and ranking to reflect updated rules
    await fetchMemory();
    await fetchRankings();
  } catch (err) {
    console.error("Error recording feedback:", err);
  }
}

async function toggleWhy(el, reviewId) {
  const detailsEl = document.getElementById(`why-${reviewId}`);
  if (!detailsEl.classList.contains("hidden")) {
    detailsEl.classList.add("hidden");
    return;
  }
  detailsEl.classList.remove("hidden");

  if (!state.activeRankingId) {
    detailsEl.innerHTML = "Base score calculated from retraction reason and trial weight share.";
    return;
  }

  try {
    const res = await fetch(`/api/tenants/${state.tenant}/explain/${state.activeRankingId}/${reviewId}`);
    const data = await res.json();

    if (!data.rules_applied || data.rules_applied.length === 0) {
      detailsEl.innerHTML = `<strong>Base Score:</strong> ${data.base_score}<br/>No active procedural rules matched this alert. Score reflects standard baseline.`;
    } else {
      let html = `<strong>Base Score:</strong> ${data.base_score} → <strong>Final Score:</strong> ${data.final_score}<br/><strong>Rules Applied:</strong><ul>`;
      data.rules_applied.forEach(r => {
        html += `<li><strong>${r.rule_id}</strong> (${r.delta > 0 ? '+' : ''}${r.delta}): ${r.description}<br/><span style="color:#64748b">Learned from episodes: ${r.learned_from_episodes.join(", ")}</span></li>`;
      });
      html += `</ul>`;
      detailsEl.innerHTML = html;
    }
  } catch (err) {
    detailsEl.innerHTML = "Explanation path unavailable.";
  }
}

// ==========================================
// Tabs & Analyst Plan
// ==========================================
function switchAlertTab(tab) {
  ["alerts", "analyst", "chat"].forEach(t => {
    document.getElementById(`tab-btn-${t}`).classList.remove("active");
    document.getElementById(`view-${t}`).classList.remove("active");
  });
  document.getElementById(`tab-btn-${tab}`).classList.add("active");
  document.getElementById(`view-${tab}`).classList.add("active");
}

async function runAnalystPlan() {
  const traceContainer = document.getElementById("analyst-trace");
  traceContainer.innerHTML = `<div class="empty-state">Executing multi-step graph analysis plan...</div>`;

  try {
    const res = await fetch("/api/analyst", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tenant: state.tenant,
        retraction_id: state.retractionId,
      }),
    });
    const data = await res.json();

    traceContainer.innerHTML = "";

    // Render tool calls
    data.tool_trace.forEach(step => {
      const stepEl = document.createElement("div");
      stepEl.className = "trace-step";
      stepEl.innerHTML = `
        <div class="trace-step-header">Step ${step.step}: Tool Call <span style="color:#06b6d4">${step.tool}</span></div>
        <div style="color: #94a3b8; font-size: 0.72rem;">Args: ${JSON.stringify(step.args)}</div>
        <div style="color: #10b981; margin-top: 0.2rem;">Output: ${step.output}</div>
      `;
      traceContainer.appendChild(stepEl);
    });

    // Final recommendation card
    const recEl = document.createElement("div");
    recEl.className = "rule-card";
    recEl.style.borderLeftColor = "#6366f1";
    recEl.style.marginTop = "0.5rem";
    recEl.innerHTML = `
      <div style="font-weight: 700; color: #818cf8; margin-bottom: 0.3rem;">📋 Analyst Synthesis & Remediation Plan</div>
      <div style="white-space: pre-line; line-height: 1.4;">${data.recommendation}</div>
    `;
    traceContainer.appendChild(recEl);
  } catch (err) {
    traceContainer.innerHTML = `<div class="empty-state" style="color: #f43f5e">Failed to run analyst plan.</div>`;
  }
}

// ==========================================
// Conversational Chat with Graph Recall
// ==========================================
async function sendChatMessage(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;

  const chatMessages = document.getElementById("chat-messages");

  // Append user bubble
  const userBubble = document.createElement("div");
  userBubble.className = "chat-bubble user";
  userBubble.innerText = text;
  chatMessages.appendChild(userBubble);
  input.value = "";
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tenant: state.tenant,
        session: state.session,
        text: text,
      }),
    });
    const data = await res.json();
    state.session = data.session_id;

    // Append assistant reply
    const assistBubble = document.createElement("div");
    assistBubble.className = "chat-bubble assistant";
    assistBubble.innerText = data.text;
    chatMessages.appendChild(assistBubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  } catch (err) {
    console.error("Chat error:", err);
  }
}

// ==========================================
// Modal: Submit Retraction Notice
// ==========================================
function openSubmitModal() {
  document.getElementById("modal-submit").classList.remove("hidden");
}

function closeSubmitModal() {
  document.getElementById("modal-submit").classList.add("hidden");
}

async function submitRetractionNotice(e) {
  e.preventDefault();
  const retId = document.getElementById("sub-ret-id").value;
  const trialId = document.getElementById("sub-trial-id").value;
  const category = document.getElementById("sub-category").value;
  const reason = document.getElementById("sub-reason").value;

  try {
    await fetch("/api/retractions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        retraction_id: retId,
        trial_id: trialId,
        reason_category: category,
        reason: reason,
      }),
    });

    closeSubmitModal();
    // Add to dropdown if not present
    const sel = document.getElementById("retraction-select");
    const opt = document.createElement("option");
    opt.value = retId;
    opt.text = `${retId} (${category})`;
    sel.appendChild(opt);
    sel.value = retId;
    state.retractionId = retId;

    refreshDashboard();
  } catch (err) {
    console.error("Error submitting retraction:", err);
  }
}
