/* AgentGate Console — vanilla JS, no build step. Talks to console_server.py. */
(() => {
  "use strict";

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const sleep = (ms) => new Promise((r) => setTimeout(r, reduced ? 0 : ms));
  const SVGNS = "http://www.w3.org/2000/svg";

  const TONE = { c: "var(--cloud)", p: "var(--private)", h: "var(--held)" };
  const TOOL_INFO = {
    search_documents: "Search documents. Restricted content is redacted.",
    lookup_customer: "Read a customer record.",
    draft_email: "Prepare an email draft. Never sends.",
  };
  const AGENT_SAMPLES = {
    "Customer lookup": "Use the lookup_customer tool with customer_id set to TRUSTED_CUSTOMER. AgentGate already has the customer identifier in trusted local context. Do not ask for the identifier or search documents. Request the lookup and wait for authorization.",
  };

  const S = {
    status: null,
    snap: { history: [], approvals: [], tool_log: [] },
    mode: "simulate",
    tool: "search_documents",
    args: {},
    caseFilter: "all",
    cases: [],
    shown: { c: 0, p: 0, h: 0 },
    seen: new Set(),
    seenTool: new Set(),
    renderKeys: {},
    animating: 0,
    reviewerToken: null,
    gatewayRequest: null,
    gatewayPolling: null,
    agentRequests: [],
    agentPolling: null,
  };

  // ── API ──────────────────────────────────────────────────────────────
  async function api(path, body, token = null) {
    const opts = body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        };

    if (token) {
      opts.headers ||= {};
      opts.headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(path, opts);
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      if (res.status === 401 && token) {
        S.reviewerToken = null;
        renderReviewer();
        S.snap = {
          history: [],
          approvals: [],
          tool_log: [],
          agent_history: [],
        };
        S.renderKeys = {};
        renderAll();
      }
      throw new Error(data.error || `Request failed (${res.status})`);
    }

    return data;
  }

  function renderReviewer() {
    const authenticated = Boolean(S.reviewerToken);

    $("#reviewer-secret").hidden = authenticated;
    $("#reviewer-login").hidden = authenticated;
    $("#reviewer-logout").hidden = !authenticated;

    $("#reviewer-status").textContent = authenticated
      ? "Reviewer authenticated — Governance Center unlocked"
      : "Locked — reviewer authentication required";

    const protectedArea = $("#activity-protected");
    if (protectedArea) {
      protectedArea.hidden = !authenticated;
    }
  }

  function syncGatewayExecution(request) {
    if (!request) return;

    const items = $$("#checks li");
    if (items.length < 5) return;

    const execution = items[4];
    const dot = execution.querySelector(".dot");
    if (!dot) return;

    const completed =
      request.status === "CONSUMED" &&
      request.execution_status === "COMPLETED";

    const rejected = request.status === "REJECTED";
    const failed =
      request.status === "CONSUMED" &&
      request.execution_status !== "COMPLETED";

    execution.classList.remove("skip", "done", "pass", "fail", "wait");

    if (completed) {
      execution.classList.add("done", "pass");
      dot.textContent = "✓";
      execution.lastElementChild.innerHTML = pill("COMPLETED");
    } else if (rejected) {
      execution.classList.add("skip");
      dot.textContent = "";
      execution.lastElementChild.innerHTML = pill("REJECTED");
    } else if (failed) {
      execution.classList.add("done", "fail");
      dot.textContent = "✕";
      execution.lastElementChild.innerHTML = pill("FAILED");
    } else {
      execution.classList.add("done", "wait");
      dot.textContent = "…";
      execution.lastElementChild.innerHTML = pill("PENDING");
    }
  }

  function renderGatewayStatus() {
    const box = $("#gateway-status");
    if (!box) return;

    const request = S.gatewayRequest;
    const displayKey = request
      ? `${request.token}:${request.status}:${request.execution_status}`
      : "empty";

    if (box.dataset.displayKey === displayKey) return;
    box.dataset.displayKey = displayKey;

    if (!request) {
      box.innerHTML = `
        <p class="empty">
          Submit a restricted tool request to see its approval status.
        </p>`;
      return;
    }

    const status = request.execution_status === "COMPLETED"
      ? "COMPLETED"
      : request.status;

    const messages = {
      PENDING: "Awaiting authorized reviewer approval.",
      APPROVED: "Approved by reviewer. Execution is pending.",
      REJECTED: "Request rejected. The tool will not execute.",
      CONSUMED: "Approval consumed.",
      COMPLETED: "Approved and executed successfully.",
      FAILED: "Execution failed.",
    };

    box.innerHTML = `
      <div class="req">
        <div class="req-top">
          <strong>${esc(request.tool)}</strong>
          ${pill(status)}
        </div>
        <p class="req-meta">
          ${esc(messages[status] || "Status unavailable.")}
        </p>
      </div>`;
  }

  async function checkGatewayStatus() {
    const request = S.gatewayRequest;
    if (!request?.token) return;

    try {
      const state = await api("/api/request-status", {
        status_token: request.token,
      });

      // Ignore responses for a request that has since been replaced.
      if (S.gatewayRequest !== request) return;

      request.status = state.status;
      request.execution_status = state.execution_status;

      renderGatewayStatus();
      syncGatewayExecution(request);

      if (["REJECTED", "CONSUMED"].includes(state.status)) {
        clearInterval(S.gatewayPolling);
        S.gatewayPolling = null;
      }
    } catch (error) {
      // Do not silently turn a failed status check into an approval.
      console.warn("Could not update Gateway approval status:", error);
    }
  }

  function watchGatewayRequest(entry) {
    if (S.gatewayPolling !== null) {
      clearInterval(S.gatewayPolling);
      S.gatewayPolling = null;
    }

    S.gatewayRequest = null;

    if (entry.status !== "APPROVAL_REQUIRED" || !entry.status_token) {
      renderGatewayStatus();
      return;
    }

    S.gatewayRequest = {
      token: entry.status_token,
      tool: entry.tool,
      status: "PENDING",
      execution_status: null,
    };

    renderGatewayStatus();

    S.gatewayPolling = setInterval(checkGatewayStatus, 3000);
  }

  function stopAgentPolling() {
    if (S.agentPolling !== null) {
      clearInterval(S.agentPolling);
      S.agentPolling = null;
    }
  }

  function updateAgentStatusDisplay() {
    const box = $("#agent-out");
    if (!box || !S.agentRequests.length) return;

    const statuses = S.agentRequests.map((request) => {
      if (request.execution_status === "COMPLETED") return "COMPLETED";
      if (request.status === "REJECTED") return "REJECTED";
      if (request.status === "CONSUMED") return "FAILED";
      return request.status;
    });

    let overall = "ACTION_REQUIRED";

    if (statuses.includes("REJECTED")) {
      overall = "REJECTED";
    } else if (statuses.includes("FAILED")) {
      overall = "FAILED";
    } else if (statuses.every((status) => status === "COMPLETED")) {
      overall = "COMPLETED";
    }

    const statusBadge = box.querySelector(".agent-live-status");

    if (statusBadge) {
      statusBadge.innerHTML = pill(overall);
    }

    const list = box.querySelector(".agent-live-approvals");

    if (list) {
      list.innerHTML = S.agentRequests.map((request) => {
        const status = request.execution_status === "COMPLETED"
          ? "COMPLETED"
          : request.status;

        return `<div class="req">
          <div class="req-h">
            <b>${esc(request.tool)}</b>
            ${pill(status)}
          </div>
          <p class="req-meta">
            ${esc(status === "PENDING"
              ? "Awaiting reviewer approval."
              : status === "APPROVED"
                ? "Approved. Awaiting execution."
                : status === "REJECTED"
                  ? "Reviewer denied this action."
                  : status === "COMPLETED"
                    ? "Authorized execution completed."
                    : "Execution did not complete successfully.")}
          </p>
        </div>`;
      }).join("");
    }

        const message = box.querySelector(".agent-live-message");

        if (message) {
          message.textContent = overall === "COMPLETED"
            ? "The authorized action was executed successfully."
            : overall === "REJECTED"
              ? "The reviewer rejected this action. It will not execute."
              : overall === "FAILED"
                ? "The action could not be completed."
                : "Waiting for an authorized reviewer to approve and execute this action.";
        }
  }

  async function checkAgentRequests() {
    if (!S.agentRequests.length) return;

    const requests = S.agentRequests;

    for (const request of requests) {
      if (["REJECTED", "CONSUMED"].includes(request.status)) continue;

      try {
        const state = await api("/api/request-status", {
          status_token: request.token,
        });

        if (S.agentRequests !== requests) return;

        request.status = state.status;
        request.execution_status = state.execution_status;
      } catch (error) {
        console.warn("Agent approval status unavailable:", error);
      }
    }

    updateAgentStatusDisplay();

    if (requests.every((request) =>
      ["REJECTED", "CONSUMED"].includes(request.status)
    )) {
      stopAgentPolling();
    }
  }

  function watchAgentRequests(result) {
    stopAgentPolling();

    S.agentRequests = (result.tools || [])
      .filter((tool) =>
        tool.status === "APPROVAL_REQUIRED" &&
        typeof tool.status_token === "string"
      )
      .map((tool) => ({
        tool: tool.tool,
        token: tool.status_token,
        status: "PENDING",
        execution_status: null,
      }));

    if (!S.agentRequests.length) return;

    S.agentPolling = setInterval(checkAgentRequests, 3000);
  }

async function refresh() {
  const publicState = await api("/api/public-state");

  if (S.reviewerToken) {
    try {
      S.snap = await api("/api/state", undefined, S.reviewerToken);
    } catch (error) {
      S.reviewerToken = null;
      S.snap = {
        history: [],
        approvals: [],
        tool_log: [],
        agent_history: [],
      };
      renderReviewer();
    }
  } else {
    S.snap = {
      history: [],
      approvals: [],
      tool_log: [],
      agent_history: [],
    };
  }

  S.publicState = publicState;
  renderAll();
}

  async function refreshProtectedActivity() {
    if (!S.reviewerToken) return;

    try {
      await refresh();
    } catch (error) {
      console.warn("Activity refresh failed:", error);
    }
  }

  setInterval(() => {
    if (S.reviewerToken && location.hash === "#activity") {
      refreshProtectedActivity();
    }
  }, 4000);

  function toast(msg, err = false) {
    const t = document.createElement("div");
    t.className = "toast" + (err ? " err" : "");
    t.textContent = msg;
    $("#toasts").append(t);
    setTimeout(() => t.remove(), 4200);
  }
  const guard = (fn) => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message, true); } };

  // ── helpers ──────────────────────────────────────────────────────────
  const lane = (e) => (e.status === "BLOCKED" || e.status === "ERROR") ? "h" : e.route === "PRIVATE" ? "p" : "c";
  const clock = (ts) => { const d = new Date(ts); return isNaN(d) ? "—" : d.toLocaleTimeString([], { hour12: false }); };
  const median = (xs) => { if (!xs.length) return null; const s = [...xs].sort((a, b) => a - b), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const routeTag = (r) => `<span class="tag-route"><i style="background:${r === "PRIVATE" ? "var(--private)" : "var(--cloud)"}"></i>${esc(r)}</span>`;
  const PILL = { SIMULATED: "muted", COMPLETED: "ok", BLOCKED: "held", ERROR: "held", APPROVAL_REQUIRED: "approval",
    PENDING: "approval", APPROVED: "ok", REJECTED: "held", CONSUMED: "muted", ALLOW: "ok", BLOCK: "held", ACTION_REQUIRED: "approval" };
  const pill = (s) => `<span class="pill ${PILL[s] || "muted"}">${esc(String(s).replace(/_/g, " "))}</span>`;
  function changed(key, data) {
    const k = JSON.stringify(data);
    if (S.renderKeys[key] === k) return false;
    S.renderKeys[key] = k;
    return true;
  }
  function countTo(el, to, fmt = (v) => Math.round(v)) {
    const from = parseFloat(el.dataset.v || "0") || 0;
    el.dataset.v = to;
    if (reduced || from === to || typeof to !== "number") { el.textContent = typeof to === "number" ? fmt(to) : to; return; }
    const t0 = performance.now(), dur = 700;
    const step = (t) => {
      const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(from + (to - from) * e);
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function verdict(e) {
    const { route, status } = e;
    if (status === "ERROR") return ["h", "Inference error", "The model call failed after routing."];
    if (route === "CLOUD") {
      if (status === "COMPLETED") return ["c", "Answered in the cloud", "Public prompt, answered by hosted Nemotron."];
      if (status === "BLOCKED") return ["h", "Held at the gate", "Cloud-eligible, but hosted inference is not configured. Nothing was sent."];
      return ["c", "Cleared for cloud", "No sensitive pattern matched. Simulated, so no model was called."];
    }
    if (status === "COMPLETED") return ["p", "Answered privately", "Sensitive prompt handled by the localhost NIM endpoint."];
    if (status === "BLOCKED") return ["h", "Held at the gate", "Sensitive prompt and no private endpoint. Nothing was transmitted."];
    return ["p", "Private route only", "Sensitive data detected. Hosted inference is not allowed for this prompt."];
  }

  // ── Switchboard animation ────────────────────────────────────────────
  function tween(dur, fn) {
    return new Promise((resolve) => {
      if (reduced) { fn(1); return resolve(); }
      const t0 = performance.now();
      const step = (t) => { const k = Math.min(1, (t - t0) / dur); fn(k); k < 1 ? requestAnimationFrame(step) : resolve(); };
      requestAnimationFrame(step);
    });
  }
  const ease = (k) => (k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);

  // Switchboard geometry. Horizontal for wide boards; vertical (prompt → gate → three lanes side by side)
  // when the board is narrower than 820px, so phone and tablet-portrait text stays readable.
  const LAYOUTS = {
    h: { vb: "0 0 1000 290", input: [86, 145], gate: [392, 62], tag: [460, 240],
      wires: { in: "M118 145 H392", c: "M528 145 C640 145 640 58 760 58 H802", p: "M528 145 H802", h: "M528 145 C640 145 640 232 760 232 H802" },
      dest: { c: [802, 34], p: [802, 121], h: [802, 208] }, dw: 176, dh: 48, lbl: [16, 21], num: [160, 32] },
    v: { vb: "0 0 360 446", input: [180, 36], gate: [112, 96], tag: [180, 282],
      wires: { in: "M180 68 V96", c: "M180 262 C180 318 66 318 66 368", p: "M180 262 V368", h: "M180 262 C180 318 294 318 294 368" },
      dest: { c: [12, 368], p: [126, 368], h: [240, 368] }, dw: 108, dh: 72, lbl: [12, 24], num: [12, 58] },
  };
  let layout = LAYOUTS.h;
  function applyLayout(key) {
    const L = LAYOUTS[key];
    if (layout === L && $("#flow").dataset.layout === key) return;
    layout = L;
    const svg = $("#flow");
    svg.dataset.layout = key;
    svg.classList.toggle("vertical", key === "v");
    svg.setAttribute("viewBox", L.vb);
    $("#node-in").setAttribute("transform", `translate(${L.input})`);
    $("#gate").setAttribute("transform", `translate(${L.gate})`);
    ["in", "c", "p", "h"].forEach((w) => $("#w-" + w).setAttribute("d", L.wires[w]));
    ["c", "p", "h"].forEach((l) => {
      const g = $("#d-" + l), lbl = $(".t-lbl", g), num = $(".t-num", g), sub = $(".t-sub2", g);
      g.setAttribute("transform", `translate(${L.dest[l]})`);
      $("rect", g).setAttribute("width", L.dw);
      $("rect", g).setAttribute("height", L.dh);
      lbl.setAttribute("x", L.lbl[0]); lbl.setAttribute("y", L.lbl[1]);
      lbl.textContent = key === "v" ? lbl.dataset.short : lbl.dataset.long;
      num.setAttribute("x", L.num[0]); num.setAttribute("y", L.num[1]);
      sub.style.display = key === "v" ? "none" : "";
    });
  }
  function watchBoard() {
    const board = $(".board");
    const fit = () => applyLayout(board.clientWidth < 820 ? "v" : "h");
    fit();
    if ("ResizeObserver" in window) {
      new ResizeObserver(fit).observe(board);
      let lastW = 0;
      new ResizeObserver(() => { const w = $("#activity-panel").clientWidth; if (w !== lastW) { lastW = w; if (S.snap.history.length) renderActivity(); } }).observe($("#activity-panel"));
    }
    else window.addEventListener("resize", fit);
  }

  function showTags(signals) {
    const g = $("#tags");
    g.innerHTML = "";
    const list = signals.length > 2 ? [...signals.slice(0, 1), `+${signals.length - 1} more`] : signals;
    list.forEach((s, i) => {
      const [cx, cy] = layout.tag;
      const w = s.length * 6.7 + 16, y = cy + i * 24;
      const t = document.createElementNS(SVGNS, "g");
      t.setAttribute("class", "tag");
      t.innerHTML = `<rect x="${cx - w / 2}" y="${y}" width="${w}" height="19" rx="5"/><text x="${cx}" y="${y + 13}">${esc(s)}</text>`;
      t.style.opacity = 0;
      g.append(t);
      tween(220, (k) => { t.style.opacity = k; t.style.transform = `translateY(${(1 - k) * -6}px)`; });
    });
  }

  // Logo reacts to routing: allowed requests pass through the gate in their lane colour;
  // held requests make the gate close briefly. Throttled so bursts read as one rhythm.
  let lastPulse = 0;
  function brandPulse(l) {
    const now = performance.now();
    if (reduced || now - lastPulse < 260) return;
    lastPulse = now;
    const token = $(".brand-mark .token"), pl = $(".brand-mark .post.l"), pr = $(".brand-mark .post.r");
    const cs = getComputedStyle(document.documentElement);
    const color = cs.getPropertyValue({ c: "--cloud", p: "--private", h: "--held" }[l]).trim();
    const opts = { duration: 620, easing: cs.getPropertyValue("--e-standard-x").trim() || "ease" };
    token.style.transition = "none";  // snap to the lane colour; fade back afterwards via the CSS transition
    token.style.fill = color;
    clearTimeout(brandPulse.t);
    brandPulse.t = setTimeout(() => { token.style.transition = ""; token.style.fill = ""; }, 900);
    if (l === "h") {
      pl.animate([{ transform: "translateX(0)" }, { transform: "translateX(3.5px)", offset: .35 }, { transform: "translateX(0)" }], opts);
      pr.animate([{ transform: "translateX(0)" }, { transform: "translateX(-3.5px)", offset: .35 }, { transform: "translateX(0)" }], opts);
      token.animate([{ transform: "rotate(45deg) scale(1)" }, { transform: "rotate(45deg) scale(.45)", offset: .35 }, { transform: "rotate(45deg) scale(1)" }], opts);
    } else {
      token.animate([
        { transform: "translateX(0) rotate(45deg)", opacity: 1 },
        { transform: "translateX(10px) rotate(45deg)", opacity: 0, offset: .42 },
        { transform: "translateX(-10px) rotate(45deg)", opacity: 0, offset: .43 },
        { transform: "translateX(0) rotate(45deg)", opacity: 1 },
      ], opts);
    }
  }

  async function sendPacket(entry) {
    S.animating++;
    const l = lane(entry);
    const g = $("#packets");
    const dot = document.createElementNS(SVGNS, "circle");
    dot.setAttribute("r", "5.5");
    dot.setAttribute("class", "packet");
    dot.style.fill = "var(--paper)";
    dot.style.color = "var(--paper)";
    g.append(dot);
    const move = (path) => (k) => { const p = path.getPointAtLength(ease(k) * path.getTotalLength()); dot.setAttribute("cx", p.x); dot.setAttribute("cy", p.y); };
    await tween(420, move($("#w-in")));
    const gate = $("#gate");
    gate.classList.remove("hit"); void gate.getBBox(); gate.classList.add("hit");
    brandPulse(l);
    if (entry.signals.length) showTags(entry.signals);
    dot.style.fill = TONE[l]; dot.style.color = TONE[l];
    await sleep(entry.signals.length ? 380 : 160);
    await tween(560, move($("#w-" + l)));
    dot.remove();
    gate.classList.remove("hit");
    const dest = $(`.dest.${l}`);
    dest.classList.add("flash");
    setTimeout(() => dest.classList.remove("flash"), 650);
    S.shown[l]++;
    countTo($("#n-" + l), S.shown[l]);
    setTimeout(() => { if (!--S.animating) $("#tags").innerHTML = ""; }, 700);
  }

  // ── Renderers ────────────────────────────────────────────────────────
  function renderStatus() {
    const st = S.status;
    if (!st) return;
    $("#gate-n").textContent = st.patterns;
    $(".how li b").nextSibling.textContent = ` ${st.patterns} sensitive-data patterns`;
    renderModeNote();
  }
  // The environment answers the mode switch: a radial reveal anchored on the switch itself.
  function setAtmosphere(mode, origin) {
    const root = document.documentElement, live = $(".atmo-live");
    const r = origin.getBoundingClientRect();
    const x = r.left + r.width / 2, y = r.top + r.height / 2;
    const far = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    root.dataset.mode = mode;
    if (reduced || !live.animate) { live.style.clipPath = mode === "live" ? "none" : "circle(0 at 0 0)"; return; }
    const from = `circle(${mode === "live" ? 0 : far}px at ${x}px ${y}px)`, to = `circle(${mode === "live" ? far : 0}px at ${x}px ${y}px)`;
    const cs = getComputedStyle(root);
    live.animate([{ clipPath: from }, { clipPath: to }], {
      duration: mode === "live" ? 900 : 600,
      easing: cs.getPropertyValue(mode === "live" ? "--e-entrance-x" : "--e-exit").trim(),
      fill: "forwards",
    });
  }

  function renderModeNote() {
    const st = S.status || {};
    $("#mode-note").textContent = S.mode === "simulate" ? "No model calls. Decisions are real."
      : st.hosted_key ? "Cloud-eligible prompts go to hosted Nemotron." : "No NVIDIA_API_KEY. Cloud prompts will be held.";
  }

  function renderBoard(animate = false) {
    const h = S.snap.history;
    const counts = { c: 0, p: 0, h: 0 };
    h.forEach((e) => counts[lane(e)]++);
    if (!S.animating && !animate) {
      S.shown = { ...counts };
      ["c", "p", "h"].forEach((l) => countTo($("#n-" + l), counts[l]));
    }
    const total = h.length;
    countTo($("#st-total"), total);
    const med = median(h.map((e) => e.inspection_ms).filter((v) => v != null));
    $("#st-median").textContent = med == null ? "—" : `${med.toFixed(3)} ms`;
    countTo($("#st-signals"), h.reduce((n, e) => n + e.signals.length, 0));
    $("#st-private").textContent = total ? `${Math.round((h.filter((e) => e.route === "PRIVATE").length / total) * 100)}%` : "—";
    ["c", "p", "h"].forEach((l) => { $("#mix-" + l).style.width = total ? `${(counts[l] / total) * 100}%` : "0"; });
  }

  function renderReceipt(e) {
    const box = $("#receipt");
    if (!e) return;
    const [l, title, why] = verdict(e);
    const sigs = e.signals.length
      ? e.signals.map((s, i) => `<span class="sig hit" style="animation-delay:${.25 + i * .07}s">${esc(s)}</span>`).join("")
      : `<span class="sig none" style="animation-delay:.25s">NO SENSITIVE PATTERN</span>`;
    const inf = e.inference_ms != null ? `${e.inference_ms.toFixed(1)} ms` : "n/a";
    box.innerHTML = `<div class="rc" style="--tone:${TONE[l]}">
      <div class="rc-top"><span>REQUEST ${esc(e.request_id)}</span><span>${esc(clock(e.timestamp))} · ${esc(e.execution_mode)}</span></div>
      <div class="rc-verdict"><h2>${esc(title)}</h2>${pill(e.status)}</div>
      <p class="rc-why">${esc(why)}</p>
      <div class="rc-sigs">${sigs}</div>
      <div class="rc-steps">
        <div><span>Inspect</span><b>${e.signals.length} hit${e.signals.length === 1 ? "" : "s"} · ${e.inspection_ms.toFixed(3)} ms</b></div>
        <div><span>Policy</span><b>${esc(e.policy_id)} → ${esc(e.route)}</b></div>
        <div><span>Execute</span><b>${esc(e.status)}</b></div>
      </div>
      <div class="rc-out">${esc(e.response)}</div>
      <p class="rc-foot">inference ${inf} · tokens ${e.tokens ?? "n/a"} · ${esc(e.reason)}</p>
    </div>`;
  }

  // One quiet line under the prompt; the full receipt lives on the Activity page.
  function renderRouteResult(e) {
    const box = $("#route-result");
    if (!e) { box.hidden = true; box.innerHTML = ""; return; }
    const [l, title] = verdict(e);
    const matched = e.signals.length ? `Matched <span class="m">${e.signals.map(esc).join("</span> and <span class=\"m\">")}</span>` : "No sensitive pattern matched";
    box.innerHTML = `<i style="background:${TONE[l]}"></i><p><b style="color:${TONE[l]}">${esc(title)}.</b> ${matched} under policy <span class="m">${esc(e.policy_id)}</span>, checked in <span class="m">${e.inspection_ms.toFixed(3)} ms</span>. <a href="#activity">See the full decision</a></p>`;
    box.hidden = false;
    box.classList.remove("in"); void box.offsetWidth; box.classList.add("in");
  }

  function renderSignals() {
    const counts = {};
    S.snap.history.forEach((e) => e.signals.forEach((s) => { counts[s] = (counts[s] || 0) + 1; }));
    const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    if (!changed("sigs", rows)) return;
    const box = $("#sigs");
    $("#sig-meta").textContent = rows.length ? `${rows.length} of ${S.status?.patterns ?? "—"} patterns` : "";
    if (!rows.length) { box.innerHTML = `<p class="empty">No patterns have fired yet.</p>`; return; }
    const max = rows[0][1];
    box.innerHTML = rows.map(([s, n]) => `<span class="name">${esc(s)}</span><div class="track"><div class="fill" data-w="${(n / max) * 100}"></div></div><span class="n">${n}</span>`).join("");
    requestAnimationFrame(() => requestAnimationFrame(() => $$(".fill", box).forEach((f) => { f.style.width = f.dataset.w + "%"; })));
  }

  function renderStream() {
    const rows = S.snap.history.slice(0, 8);
    if (!changed("stream", rows.map((r) => r.request_id))) return;
    $("#stream-empty").hidden = rows.length > 0;
    $("#stream tbody").innerHTML = rows.map((e, i) => {
      const fresh = !S.seen.has(e.request_id);
      return `<tr class="${fresh ? "new" : ""}" style="animation-delay:${fresh ? i * 40 : 0}ms">
        <td class="m">${esc(clock(e.timestamp))}</td><td class="m">${esc(e.request_id)}</td><td>${routeTag(e.route)}</td><td class="m">${esc(e.policy_id)}</td>
        <td class="m">${esc(e.signals.join(", ") || "—")}</td><td>${pill(e.status)}</td></tr>`;
    }).join("");
    S.snap.history.forEach((e) => S.seen.add(e.request_id));
  }

  // gateway
  function renderTools() {
    const st = S.status;
    if (!st) return;
    $("#tools").innerHTML = Object.keys(st.tools).map((t) => `<button type="button" class="tool" role="radio" data-tool="${t}" aria-checked="${t === S.tool}"><b>${t}</b><span>${esc(TOOL_INFO[t] || "")}</span></button>`).join("");
    $("#fields").innerHTML = st.tools[S.tool].map((f) => {
      const v = esc(S.args[S.tool]?.[f] ?? "");
      const id = `arg-${S.tool}-${f}`;
      return f === "body" ? `<label for="${id}">${f}<textarea id="${id}" data-f="${f}" rows="3">${v}</textarea></label>`
        : `<label for="${id}">${f}<input type="text" id="${id}" data-f="${f}" value="${v}"></label>`;
    }).join("");
  }
  function setPreset(name) {
    const p = S.status.presets[name];
    S.tool = p.tool;
    S.args[p.tool] = { ...p.arguments };
    renderTools();
    $("#checks").innerHTML = ""; $("#checks-empty").hidden = false;
  }

  async function playChecks(entry) {
    const r = entry.reason, s = entry.status;
    const failAt = r === "Unknown tool" ? 0 : /must be an object|Invalid tool arguments/.test(r) ? 1 : /non-empty strings/.test(r) ? 2 : s === "BLOCKED" ? 3 : -1;
    const steps = [
      ["Registered tool", "on the allow-list"],
      ["Argument schema", "exact field set, JSON object"],
      ["Argument values", "non-empty strings"],
      ["Policy rule", r],
      ["Execution", s === "COMPLETED" ? "ran with synthetic data" : s === "APPROVAL_REQUIRED" ? "held until a person approves" : "did not run"],
    ];
    $("#checks-empty").hidden = true;
    const box = $("#checks");
    box.innerHTML = steps.map(([t, sub]) => `<li><span class="dot"></span><span>${esc(t)}<small>${esc(sub)}</small></span><span></span></li>`).join("");
    const items = $$("li", box);
    for (let i = 0; i < items.length; i++) {
      await sleep(190);
      const li = items[i];
      let cls = "pass", mark = "✓", tag = "";
      if (failAt >= 0 && i === failAt) { cls = "fail"; mark = "✕"; tag = pill("BLOCKED"); }
      else if (failAt >= 0 && i > failAt) { li.classList.add("skip"); continue; }
      else if (s === "APPROVAL_REQUIRED" && i === 3) { cls = "wait"; mark = "…"; tag = pill("APPROVAL_REQUIRED"); }
      else if (s === "APPROVAL_REQUIRED" && i === 4) { li.classList.add("skip"); continue; }
      else if (i === 3) tag = pill("ALLOW");
      else if (i === 4) tag = pill(s);
      li.classList.add("done", cls);
      li.querySelector(".dot").textContent = mark;
      li.lastElementChild.innerHTML = tag;
    }
  }

  function renderQueue() {
    const list = S.snap.approvals;
    const pending = list.filter((a) => a.status === "PENDING").length;
    const badge = $("#nav-pending");
    badge.hidden = !pending;
    if (badge.textContent !== String(pending)) { badge.textContent = pending; badge.style.animation = "none"; void badge.offsetWidth; badge.style.animation = ""; }
    if (!changed("queue", list)) return;
    $("#q-meta").textContent = pending ? `${pending} waiting` : "";
    if (!list.length) { $("#queue").innerHTML = `<p class="empty">Nothing waiting. Try <b>Customer record</b> or <b>Finance forecast</b>.</p>`; return; }
    const shown = [...list.filter((a) => a.status === "PENDING" || a.status === "APPROVED"), ...list.filter((a) => a.status !== "PENDING" && a.status !== "APPROVED").slice(0, 3)];
    $("#queue").innerHTML = shown.map((a) => {
      const args = Object.entries(a.arguments).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ");
      const act = a.status === "PENDING"
        ? `<div class="req-act"><button class="btn primary sm" data-act="approve" data-id="${a.approval_id}">Approve</button><button class="btn sm" data-act="reject" data-id="${a.approval_id}">Reject</button></div>`
        : a.status === "APPROVED" ? `<div class="req-act"><button class="btn primary sm" data-act="execute" data-id="${a.approval_id}">Execute once</button></div>` : "";
      return `<div class="req" data-status="${a.status}">
        <div class="req-h"><b>${esc(a.tool)}</b>${pill(a.status)}</div>
        <div class="req-args">${esc(args)}</div>
        <div class="req-meta">
          Requested at ${esc(clock(a.created_at))} ·
          Request <span class="m">${esc(a.approval_id.slice(0, 8))}</span>
        </div>
        ${act}
        </div>`;
    }).join("");
  }

  function renderPolicy() {
    const p = S.status?.policy || [];
    $("#policy tbody").innerHTML = p.map((r) => `<tr><td class="m">${esc(r.tool)}</td><td>${esc(r.condition)}</td><td>${pill(r.outcome)}</td></tr>`).join("");
  }
  function renderToolLog() {
    const rows = (S.publicState?.recent_tool_statuses || []).slice(0, 8);

    if (!changed("toollog", rows)) return;

    $("#toollog-empty").hidden = rows.length > 0;

    const descriptions = {
      APPROVAL_REQUIRED: [
        "Approval required",
        "The action was held for human authorization."
      ],
      PENDING: [
        "Awaiting approval",
        "The action is waiting for an authorized reviewer."
      ],
      APPROVED: [
        "Approved",
        "A reviewer authorized the action. Execution is tracked separately."
      ],
      REJECTED: [
        "Rejected",
        "A reviewer rejected the requested action."
      ],
      BLOCKED: [
        "Blocked",
        "AgentGate prevented the action under its security policy."
      ],
      COMPLETED: [
        "Completed",
        "A tool operation completed."
      ],
      ERROR: [
        "Error",
        "The action could not be completed."
      ]
    };

    $("#toollog tbody").innerHTML = rows.map((event) => {
      const [label, explanation] =
        descriptions[event.status] || [
          "Policy event",
          "AgentGate recorded a security decision."
        ];

      return `<tr>
        <td class="m">${esc(clock(event.time))}</td>
        <td>${esc(label)}</td>
        <td>${esc(explanation)}</td>
      </tr>`;
    }).join("");
  }
    function renderGatewayActivity() {
    const host = $("#agent-decision-chart");
    const empty = $("#agent-decision-chart-empty");
    if (!host || !empty) return;

    const events = (S.publicState?.recent_tool_statuses || []).slice().reverse();

    empty.hidden = events.length > 0;
    host.innerHTML = "";

    if (!events.length) return;

    let allow = 0;
    let approval = 0;
    let blocked = 0;

    const points = events.map((e, i) => {
      const status = String(e.status || "");

            if (
        status === "ALLOW" ||
        status === "ALLOWED" ||
        status === "PASSED"
      ) {
        allow += 1;
      } else if (
        status === "APPROVAL_REQUIRED" ||
        status === "PENDING"
      ) {
        approval += 1;
      } else if (
        status === "BLOCKED" ||
        status === "DENIED"
      ) {
        blocked += 1;
      }

      return {
        x: i,
        allow,
        approval,
        blocked,
      };
    });

    const w = Math.max(host.clientWidth || 640, 640);
    const h = 220;
    const pad = { t: 16, r: 20, b: 30, l: 36 };
    const innerW = w - pad.l - pad.r;
    const innerH = h - pad.t - pad.b;
    const maxY = Math.max(
      1,
      ...points.map((p) => Math.max(p.allow, p.approval, p.blocked))
    );

    const svg = document.createElementNS(SVGNS, "svg");
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", h);

    const x = (i) =>
      pad.l + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);

    const y = (v) => pad.t + innerH - (v / maxY) * innerH;

    function linePath(key) {
      return points
        .map((p, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(p[key])}`)
        .join(" ");
    }

    function addLine(pathData, colorVar) {
      const path = document.createElementNS(SVGNS, "path");
      path.setAttribute("d", pathData);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", `var(${colorVar})`);
      path.setAttribute("stroke-width", "2.5");
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");
      svg.appendChild(path);
    }

    function addLabel(text, xPos, yPos, colorVar) {
      const t = document.createElementNS(SVGNS, "text");
      t.setAttribute("x", xPos);
      t.setAttribute("y", yPos);
      t.setAttribute("fill", `var(${colorVar})`);
      t.setAttribute("font-size", "12");
      t.textContent = text;
      svg.appendChild(t);
    }

    // Grid lines
    for (let i = 0; i <= 4; i++) {
      const gy = pad.t + (i / 4) * innerH;
      const line = document.createElementNS(SVGNS, "line");
      line.setAttribute("x1", pad.l);
      line.setAttribute("x2", w - pad.r);
      line.setAttribute("y1", gy);
      line.setAttribute("y2", gy);
      line.setAttribute("stroke", "rgba(255,255,255,0.08)");
      line.setAttribute("stroke-width", "1");
      svg.appendChild(line);
    }

    addLine(linePath("allow"), "--chart-passed");
    addLine(linePath("approval"), "--chart-approval");
    addLine(linePath("blocked"), "--chart-blocked");

    addLabel("Passed", pad.l, 14, "--chart-passed");
    addLabel("Needs review", pad.l + 80, 14, "--chart-approval");
    addLabel("Blocked", pad.l + 190, 14, "--chart-blocked");

    host.appendChild(svg);
  }
  // evidence
  function renderFigures() {
    const st = S.status, s = st?.summary;
    const figs = s ? [
      ["Accuracy", `${(s.accuracy * 100).toFixed(1)}%`, `${s.samples} synthetic prompts`],
      ["Sensitive recall", `${(s.sensitive_recall * 100).toFixed(1)}%`, `${s.false_negative_count} missed`],
      ["False positives", `${(s.false_positive_rate * 100).toFixed(1)}%`, `${s.false_positive_count} over-flagged`],
      ["Median inspection", `${s.median_inspection_ms} ms`, "offline run"],
    ] : [["Evaluation", "—", "run python evaluate.py"]];
    $("#figures").innerHTML = figs.map(([l, v, f]) => `<div class="fig"><span>${esc(l)}</span><b>${esc(v)}</b><small>${esc(f)}</small></div>`).join("");
  }
  function renderCases() {
    const f = S.caseFilter;
    if (S.casesLoaded && !S.cases.length) { $("#cases tbody").innerHTML = `<tr><td colspan="5" class="empty">No evaluation cases yet. Run <code>python evaluate.py</code> to generate them.</td></tr>`; return; }
    const rows = S.cases.filter((c) => f === "all" || (f === "miss" ? c.correct !== "1" : c.expected === f));
    $("#cases tbody").innerHTML = rows.length ? rows.map((c) => `<tr><td>${esc(c.prompt)}</td><td>${routeTag(c.expected)}</td><td>${routeTag(c.actual)}${c.correct === "1" ? "" : " " + pill("BLOCKED").replace("BLOCKED", "MISS")}</td><td class="m">${esc(c.signals || "—")}</td><td class="m r">${esc(Number(c.inspection_ms).toFixed(3))}</td></tr>`).join("")
      : `<tr><td colspan="5" class="empty">${f === "miss" ? "No misclassified cases in this run." : "No cases."}</td></tr>`;
  }
  function renderAudit() {
    const h = S.snap.history;
    if (!changed("audit", h.map((e) => e.request_id))) return;
    $("#audit-empty").hidden = h.length > 0;
    const num = (v, d) => (v == null ? "—" : Number(v).toFixed(d));
    $("#audit tbody").innerHTML = h.slice(0, 50).map((e) => `<tr><td class="m">${esc(e.timestamp.replace("T", " ").slice(0, 19))}</td><td class="m">${esc(e.request_id)}</td><td>${routeTag(e.route)}</td><td class="m">${esc(e.policy_id)}</td>
      <td class="m wrap">${esc(e.signals.join(", ") || "—")}</td><td class="wrap">${esc(e.reason)}</td><td class="m">${esc(e.execution_mode)}</td><td>${pill(e.status)}</td>
      <td class="m r">${num(e.inspection_ms, 3)}</td><td class="m r">${num(e.inference_ms, 1)}</td><td class="m r">${e.tokens ?? "—"}</td></tr>`).join("");
  }

  // Routing activity: cumulative count per lane by request order (the old dashboard's "Traffic trend").
  function renderActivity() {
    const wrap = $("#activity");
    const rows = [...S.snap.history].reverse();
    $("#activity-empty").hidden = rows.length > 0;
    wrap.hidden = !rows.length;
    if (!rows.length) { wrap.innerHTML = ""; S.actN = 0; return; }
    const W = Math.max(280, wrap.clientWidth || 600), H = W < 520 ? 190 : 230;
    const m = { l: 30, r: W < 520 ? 74 : 96, t: 10, b: 26 };
    const lanes = ["c", "p", "h"], name = { c: "Cloud", p: "Private", h: "Held" };
    const series = { c: [], p: [], h: [] }, tally = { c: 0, p: 0, h: 0 };
    rows.forEach((e) => { tally[lane(e)]++; lanes.forEach((l) => series[l].push(tally[l])); });
    const n = rows.length, maxV = Math.max(1, ...lanes.map((l) => tally[l]));
    const step = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500].find((s) => maxV / s <= 4) || Math.ceil(maxV / 4);
    const top = Math.ceil(maxV / step) * step;
    const x = (i) => m.l + (n === 1 ? (W - m.l - m.r) / 2 : (i / (n - 1)) * (W - m.l - m.r));
    const y = (v) => m.t + (1 - v / top) * (H - m.t - m.b);
    let g = "";
    for (let v = 0; v <= top; v += step) g += `<line class="act-grid" x1="${m.l}" x2="${W - m.r + 8}" y1="${y(v)}" y2="${y(v)}"/><text class="act-axis" x="${m.l - 8}" y="${y(v) + 3.5}" text-anchor="end">${v}</text>`;
    const ticks = n === 1 ? [0] : [...new Set([0, Math.round((n - 1) / 2), n - 1])];
    ticks.forEach((i) => { g += `<text class="act-axis" x="${x(i)}" y="${H - 6}" text-anchor="middle">#${i + 1}</text>`; });
    const animate = !reduced && !S.actN;
    let lines = "", dots = "";
    lanes.forEach((l) => {
      const d = series[l].map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
      lines += `<path class="act-line ${l}${animate ? " draw" : ""}" d="${d}"/>`;
      dots += `<circle class="act-dot" cx="${x(n - 1)}" cy="${y(tally[l])}" r="4" style="fill:var(--${{ c: "cloud", p: "private", h: "held" }[l]}-solid)"/>`;
    });
    // direct end labels, nudged apart so equal values never overlap
    const ends = lanes.map((l) => ({ l, y: y(tally[l]) })).sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 15);
    const shift = Math.max(0, ends[ends.length - 1].y - (H - m.b + 4));
    const labels = ends.map((e) => `<text class="act-end" x="${x(n - 1) + 10}" y="${e.y - shift + 4}"><tspan class="k">${name[e.l]}</tspan> ${tally[e.l]}</text>`).join("");
    wrap.innerHTML = `<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img" aria-label="Cumulative requests: cloud ${tally.c}, private ${tally.p}, held ${tally.h}">${g}${lines}<line class="act-cross" id="act-cross" y1="${m.t}" y2="${H - m.b}" visibility="hidden"/>${dots}${labels}<rect id="act-hit" x="${m.l - 10}" y="0" width="${W - m.l - m.r + 20}" height="${H}" fill="transparent"/></svg><div class="act-tip" id="act-tip" style="opacity:0"></div>`;
    $$(".act-line.draw", wrap).forEach((p) => p.style.setProperty("--len", p.getTotalLength()));
    S.actN = n;
    const hit = $("#act-hit", wrap), cross = $("#act-cross", wrap), tip = $("#act-tip", wrap), svg = $("svg", wrap);
    const show = (ev) => {
      const r = svg.getBoundingClientRect(), px = (ev.clientX - r.left) * (W / r.width);
      const i = n === 1 ? 0 : Math.max(0, Math.min(n - 1, Math.round(((px - m.l) / (W - m.l - m.r)) * (n - 1))));
      cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
      const e = rows[i];
      tip.innerHTML = `<b>#${i + 1} · ${esc(clock(e.timestamp))} · ${esc(e.route)}</b>` + lanes.map((l) => `<div><i style="background:var(--${{ c: "cloud", p: "private", h: "held" }[l]}-solid)"></i>${name[l]}<span>${series[l][i]}</span></div>`).join("");
      const left = (x(i) / W) * r.width, tw = tip.offsetWidth;
      tip.style.left = `${left + 14 + tw > r.width ? left - tw - 14 : left + 14}px`;
      tip.style.top = "8px";
      tip.style.opacity = 1;
    };
    hit.addEventListener("pointermove", show);
    hit.addEventListener("pointerdown", show);
    hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); tip.style.opacity = 0; });
  }

  function renderAgentMetrics() {
    const h = S.snap.agent_history || [];
    const totals = { completed: 0, blocked: 0, pending: 0, errors: 0, tools: 0 };
    const times = [];
    h.forEach((r) => {
      if (r.status === "COMPLETED") totals.completed++;
      if (r.status === "BLOCKED") totals.blocked++;
      if (r.status === "ACTION_REQUIRED") totals.pending++;
      if (r.status === "ERROR") totals.errors++;
      (r.events || []).forEach((e) => { if (e.event_type === "TOOL_EXECUTION" && e.status === "COMPLETED") totals.tools++; });
      if (typeof r.duration_ms === "number") times.push(r.duration_ms);
    });
    const latency = times.length ? (times.reduce((a,b) => a+b, 0)/times.length).toFixed(0) + " ms" : "—";
    const data = [["Agent runs", h.length], ["Blocked / pending", `${totals.blocked} / ${totals.pending}`],
      ["Completed tools", totals.tools], ["Avg. latency", latency]];
    const box = $("#agent-metrics");
    if (box) box.innerHTML = data.map(([name,value]) => `<div class="fig"><span>${esc(name)}</span><b>${esc(value)}</b><small>Current session</small></div>`).join("");
    const table = $("#agent-history tbody");
    if (table) table.innerHTML = h.slice(0, 20).map((r) => `<tr><td class="m">${esc(clock(r.timestamp))}</td><td class="m">${esc(r.request_id || "—")}</td><td>${pill(r.status)}</td><td class="m">${r.events.length}</td><td class="m r">${r.duration_ms == null ? "—" : Number(r.duration_ms).toFixed(1)}</td></tr>`).join("");
    const empty = $("#agent-history-empty"); if (empty) empty.hidden = !!h.length;
  }

  function renderAll() {
    renderBoard();
    renderReceipt(S.snap.history[0]);
    renderRouteResult(S.snap.history[0]);
    renderSignals();
    renderStream();
    renderActivity();
    renderQueue();
    renderToolLog();
    renderAudit();
    renderAgentMetrics();
    renderGatewayActivity();
  }

  // ── Views ────────────────────────────────────────────────────────────
  function placeIndicator() {
    const ind = $(".nav-ind"), a = $(".nav a[aria-current='page']");
    if (!ind || !a) return;
    ind.style.width = a.offsetWidth + "px";
    ind.style.height = a.offsetHeight + "px";
    ind.style.transform = `translate(${a.offsetLeft}px, ${a.offsetTop}px)`;
    if (!ind.classList.contains("ready")) requestAnimationFrame(() => ind.classList.add("ready"));
  }
  function showView() {
    const name = (location.hash || "#switchboard").slice(1);
    const view = $("#view-" + name) ? name : "switchboard";
    const current = $(".view:not([hidden])");
    const same = current && current.id === "view-" + view;
    const swap = () => {
      $$(".view").forEach((v) => { v.hidden = v.id !== "view-" + view; v.classList.remove("swap"); });
      window.scrollTo(0, 0);
    };
    $$(".nav a").forEach((a) => { if (a.dataset.view === view) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    placeIndicator();
    if (!same) {
      swap();
    }
    document.title = `${$("#view-" + view).dataset.title} · AgentGate`;
    if (view === "evidence" && !S.cases.length) loadCases();
  }
  const loadCases = guard(async () => { S.cases = (await api("/api/evaluation")).cases; S.casesLoaded = true; renderCases(); });

  // ── Wiring ───────────────────────────────────────────────────────────
  function wire() {
    window.addEventListener("hashchange", showView);
    $(".nav").insertAdjacentHTML("afterbegin", '<span class="nav-ind" aria-hidden="true"></span>');
    window.addEventListener("resize", () => { const i = $(".nav-ind"); i.classList.remove("ready"); placeIndicator(); });
    document.fonts?.ready.then(placeIndicator);

    $$(".mode button").forEach((b) => b.addEventListener("click", () => {
      if (S.mode === b.dataset.mode) return;
      S.mode = b.dataset.mode;
      $(".mode").dataset.mode = S.mode;
      $$(".mode button").forEach((x) => x.setAttribute("aria-checked", x === b));
      setAtmosphere(S.mode, b);
      renderModeNote();
      if (S.mode === "live" && S.status && !S.status.hosted_key) toast("Live mode is on, but hosted inference isn't configured. Cloud-eligible prompts will be held, not sent.");
    }));

    const samples = S.status.samples;
    const dots = { Public: "var(--cloud)", Personal: "var(--private)", Confidential: "var(--held)" };
    $("#samples").innerHTML = Object.keys(samples).map((k) => `<button type="button" class="chip" data-s="${esc(k)}"><i style="background:${dots[k] || "var(--muted)"}"></i>${esc(k)}</button>`).join("");
    $("#samples").addEventListener("click", (ev) => { const b = ev.target.closest("[data-s]"); if (b) { $("#prompt").value = samples[b.dataset.s]; $("#prompt").focus(); } });

    $("#composer").addEventListener("submit", guard(async (ev) => {
      ev.preventDefault();
      const prompt = $("#prompt").value;
      if (!prompt.trim()) { toast("Write a prompt or pick an example first."); return; }
      const btn = $("#btn-route"); btn.disabled = true;
      try {
        const entry = await api("/api/route", { prompt, mode: S.mode });
        S.snap.history.unshift(entry);
        renderBoard(true);
        const flight = sendPacket(entry);
        await sleep(reduced ? 0 : 980);
        renderReceipt(entry); renderRouteResult(entry); renderSignals(); renderStream(); renderActivity(); renderAudit();
        await flight;
      } finally { btn.disabled = false; }
    }));
    $("#prompt").addEventListener("keydown", (ev) => { if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) { ev.preventDefault(); $("#composer").requestSubmit(); } });

    $("#btn-demo").addEventListener("click", guard(async () => {
      const btn = $("#btn-demo"), label = $("#replay-label"), sub = $("#replay-sub");
      btn.disabled = true; btn.setAttribute("aria-busy", "true");
      label.textContent = "Replaying";
      try {
        const entries = await api("/api/demo", {});
        const flights = [];
        for (const [i, e] of entries.entries()) {
          S.snap.history.unshift(e);
          renderBoard(true);
          flights.push(sendPacket(e));
          sub.textContent = `${i + 1} of ${entries.length} requests`;
          btn.style.setProperty("--progress", `${((i + 1) / entries.length) * 100}%`);
          await sleep(170);
        }
        await Promise.all(flights);
        await refresh();
      } finally {
        btn.disabled = false; btn.removeAttribute("aria-busy"); btn.style.removeProperty("--progress");
        label.textContent = "Replay demo traffic"; sub.textContent = "12 sample requests through the gate";
      }
    }));
    $("#btn-clear").addEventListener("click", guard(async () => {
      await api("/api/clear", {});
      $("#receipt").innerHTML = S.emptyReceipt;
      S.actN = 0;
      S.seen.clear();
      await refresh();
    }));

    // gateway

    // Reviewer authentication
    renderReviewer();

    $("#reviewer-form").addEventListener("submit", guard(async (ev) => {
      ev.preventDefault();

      const input = $("#reviewer-secret");
      const secret = input.value;

      // Clear the passphrase from the form immediately.
      input.value = "";

      const result = await api("/api/reviewer/login", { secret });

      S.reviewerToken = result.token;
      renderReviewer();
      await refresh();
      toast("Governance Center unlocked");
    }));

    $("#reviewer-logout").addEventListener("click", guard(async () => {
      const token = S.reviewerToken;

      if (!token) return;

      // Remove local authorization immediately.
      S.reviewerToken = null;
      renderReviewer();

      await api("/api/reviewer/logout", {}, token);
      toast("Reviewer session locked");
    }));
    $("#tools").addEventListener("click", (ev) => { const b = ev.target.closest("[data-tool]"); if (b) { S.tool = b.dataset.tool; renderTools(); $("#checks").innerHTML = ""; $("#checks-empty").hidden = false; } });
    $("#fields").addEventListener("input", (ev) => { const f = ev.target.dataset.f; if (f) (S.args[S.tool] ||= {})[f] = ev.target.value; });
    $("#presets").insertAdjacentHTML("beforeend", Object.keys(S.status.presets).map((n) => `<button type="button" data-p="${esc(n)}">${esc(n)}</button>`).join(""));
    $("#presets").addEventListener("click", (ev) => { const b = ev.target.closest("[data-p]"); if (b) setPreset(b.dataset.p); });
    $("#toolform").addEventListener("submit", guard(async (ev) => {
      ev.preventDefault();

      const args = {};
      S.status.tools[S.tool].forEach((f) => {
        args[f] = S.args[S.tool]?.[f] ?? "";
      });

      const entry = await api("/api/tools/call", {
        tool: S.tool,
        arguments: args,
      });

      watchGatewayRequest(entry);

      await playChecks(entry);
      await refresh();
    }));
    $("#queue").addEventListener("click", guard(async (ev) => {
      const b = ev.target.closest("[data-act]");
      if (!b) return;
      b.disabled = true;
      if (!S.reviewerToken) {
        throw new Error("Unlock reviewer approvals before continuing.");
      }

      await api(
        `/api/approvals/${b.dataset.id}/${b.dataset.act}`,
        {},
        S.reviewerToken
      );
      await refresh();
    }));

    // evidence
    $("#case-filter").addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-f]"); if (!b) return;
      S.caseFilter = b.dataset.f;
      $$("#case-filter button").forEach((x) => x.setAttribute("aria-selected", x === b));
      renderCases();
    });
    $("#btn-export").addEventListener("click", guard(async () => {
      if (!S.reviewerToken) {
        toast("Unlock Activity with reviewer credentials to export the audit.", true);
        return;
      }

      const data = await api(
        "/api/audit.json",
        undefined,
        S.reviewerToken
      );

      const url = URL.createObjectURL(
        new Blob(
          [JSON.stringify(data, null, 2)],
          { type: "application/json" }
        )
      );

      const a = Object.assign(document.createElement("a"), {
        href: url,
        download: "agentgate-audit.json",
      });

      document.body.append(a);
      a.click();
      a.remove();

      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast(
        `Exported ${data.length} audit event${data.length === 1 ? "" : "s"}.`
      );
    }));

    // agent
    $("#agent-samples").innerHTML = Object.keys(AGENT_SAMPLES).map((k) => `<button type="button" class="chip" data-a="${esc(k)}"><i style="background:var(--muted)"></i>${esc(k)}</button>`).join("");
    $("#agent-samples").addEventListener("click", (ev) => {
      const button = ev.target.closest("[data-a]");
      if (!button) return;

      $("#agent-prompt").value = AGENT_SAMPLES[button.dataset.a];

      $("#agent-trusted-fields").hidden =
        button.dataset.a !== "Customer lookup";
    });

    $("#agentform").addEventListener("submit", guard(async (ev) => {
      ev.preventDefault();
      const prompt = $("#agent-prompt").value;
      if (!prompt.trim()) { toast("Write a request for the agent first."); return; }
      const out = $("#agent-out"), btn = $("#btn-agent");
      btn.disabled = true;
      out.innerHTML = `<p class="p-title">Run</p><p class="empty">Checking policy and calling Nemotron…</p>`;
      try {
        const trustedFields = $("#agent-trusted-fields");

        const body = { prompt };

        if (!trustedFields.hidden) {
          body.trusted_customer_id =
            $("#agent-customer-id").value.trim();
        }

        const r = await api("/api/agent", body);

        watchAgentRequests(r);
        const awaitingReview = S.agentRequests.length > 0;

        const messages = {
          COMPLETED: "The agent completed the request.",
          ACTION_REQUIRED: awaitingReview
            ? "This action requires an authorized reviewer before it can continue."
            : "The requested action could not proceed.",
          BLOCKED: "AgentGate blocked this request under its security policy.",
          ERROR: "The request could not be completed."
        };

        const initialStatus = awaitingReview
          ? "ACTION_REQUIRED"
          : r.status;

        const explanation =
          messages[r.status] || r.reason || "Status unavailable.";

        out.innerHTML = `
          <div class="p-row">
            <p class="p-title">Request status</p>
            <span class="agent-live-status">${pill(initialStatus)}</span>
          </div>

          <p class="note agent-live-message">
            ${esc(explanation)}
          </p>

          ${awaitingReview ? `
            <div class="agent-tools agent-live-approvals"></div>
          ` : ""}

          ${r.answer && !awaitingReview ? `
            <div class="agent-answer">${esc(r.answer)}</div>
          ` : ""}

          <details class="agent-technical-details">
            <summary>Technical details</summary>

            ${(r.tools || []).length ? `
              <h3 class="p-title">Tool decisions</h3>
              <div class="agent-tools">
                ${(r.tools || []).map((tool) => `
                  <div class="req">
                    <div class="req-h">
                      <b>${esc(tool.tool)}</b>
                      ${pill(tool.status)}
                    </div>
                    <p class="req-meta">
                      ${esc(tool.reason || "No additional details.")}
                    </p>
                  </div>
                `).join("")}
              </div>
            ` : ""}

            ${r.audit ? `
              <h3 class="p-title">Execution audit</h3>
              <p class="p-sub2">
                ${esc(String(r.audit.duration_ms ?? "—"))}
                ms elapsed · Metadata only
              </p>
              <div class="agent-tools">
                ${(r.audit.events || []).map((event) => `
                  <div class="req">
                    <div class="req-h">
                      <b>${esc(event.event_type)}</b>
                      ${pill(event.status)}
                    </div>
                    <p class="req-meta">
                      ${esc(event.detail || "")}
                    </p>
                  </div>
                `).join("")}
              </div>
            ` : ""}
          </details>
        `;
          updateAgentStatusDisplay();
        await refresh();
      } finally { btn.disabled = false; }
    }));
  }

  // ── Boot ─────────────────────────────────────────────────────────────
  async function boot() {
    S.emptyReceipt = $("#receipt").innerHTML;
    try {
      S.status = await api("/api/status");
    } catch (e) {
      toast("Could not reach the AgentGate server. Start it with: python console_server.py", true);
      return;
    }
    S.args = Object.fromEntries(Object.values(S.status.presets).reverse().map((p) => [p.tool, { ...p.arguments }]));
    S.args.draft_email = { recipient: "ops@company.test", subject: "Weekly update", body: "Draft for review." };
    watchBoard();
    renderStatus(); renderTools(); renderPolicy(); renderFigures();
    wire();
    showView();
    S.booted = true;
    await refresh();
    S.snap.history.forEach((e) => S.seen.add(e.request_id));
  }
  boot();
})();
