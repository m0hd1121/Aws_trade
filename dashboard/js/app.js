(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const API = "/api";

  // ---------------------------------------------------------------- fetch helpers
  async function getJSON(path) {
    const res = await fetch(API + path);
    if (!res.ok) throw new Error(path + " -> " + res.status);
    return res.json();
  }
  async function postJSON(path, body) {
    const res = await fetch(API + path, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(path + " -> " + res.status + " " + text);
    }
    return res.json();
  }

  // ---------------------------------------------------------------- controls
  const controlButtons = {
    "btn-start": "/bot/start",
    "btn-stop": "/bot/stop",
    "btn-pause": "/bot/pause",
    "btn-resume": "/bot/resume",
    "btn-restart": "/bot/restart",
    "btn-reset": "/bot/reset-session",
    "btn-refresh": "/bot/refresh",
  };
  for (const [id, path] of Object.entries(controlButtons)) {
    $(id).addEventListener("click", async () => {
      try {
        const data = await postJSON(path);
        applyStatus(data.runner ? data : { state: data.state, runner: data.runner });
        refreshAll();
      } catch (e) {
        console.error(e);
        alert("Action failed: " + e.message);
      }
    });
  }
  $("btn-emergency").addEventListener("click", async () => {
    if (!confirm("EMERGENCY STOP: flatten all positions and cancel all orders immediately?")) return;
    try {
      await postJSON("/bot/emergency-stop");
      refreshAll();
    } catch (e) {
      alert("Emergency stop failed: " + e.message);
    }
  });

  // ---------------------------------------------------------------- config modal
  $("btn-config").addEventListener("click", async () => {
    const cfg = await getJSON("/config/");
    $("config-text").value = JSON.stringify(cfg, null, 2);
    $("config-modal").classList.add("open");
  });
  $("config-cancel").addEventListener("click", () => $("config-modal").classList.remove("open"));
  $("config-save").addEventListener("click", async () => {
    try {
      const parsed = JSON.parse($("config-text").value);
      await fetch(API + "/config/", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: parsed }),
      });
      $("config-modal").classList.remove("open");
      refreshAll();
    } catch (e) {
      alert("Invalid config JSON: " + e.message);
    }
  });

  // ---------------------------------------------------------------- status/badges
  const STAGE_LABELS = {
    STARTUP: "Starting up",
    DAILY_LOCKOUT_CHECK: "Checking daily lockout conditions",
    MARKING_THE_MAP: "Marking the map (pools, H1 bias, Asia range)",
    WAITING_FOR_KILL_ZONE: "Waiting for London/New York kill zone",
    SESSION_DISQUALIFIER_CHECK: "Checking session disqualifiers (D1-D7)",
    ACCOUNT_STATE_CHECK: "Verifying account risk limits",
    WAITING_FOR_SWEEP: "Waiting for a qualified liquidity sweep",
    WAITING_FOR_CHOCH: "Waiting for M5 Change of Character",
    CHOP_CHECK: "Checking chop condition",
    NEWS_BLACKOUT_CHECK: "Checking news blackout window",
    SCORING_SETUP: "Scoring the setup (12-point model)",
    CONSTRUCTING_TRADE: "Constructing trade (POI, stop, targets, size)",
    SUBMITTING_BRACKET_ORDER: "Submitting bracket order",
    WAITING_FOR_FILL: "Waiting for limit order fill",
    MONITORING_PRE_TP1: "Monitoring open trade — pre-TP1 (no intervention)",
    MANAGING_POST_TP1: "Managing trade post-TP1",
    TRAILING_RUNNER: "Trailing the runner by M5 structure",
    HARD_FLAT_CLOSE: "Hard-flat closing at 19:30 GMT",
    LOGGING_TRADE: "Logging completed trade",
    SESSION_ENDED: "Session ended — waiting for next kill zone",
    EMERGENCY_STOPPED: "EMERGENCY STOPPED",
  };

  function applyStatus(status) {
    if (!status) return;
    $("badge-state").textContent = "STATE: " + status.state;
    $("badge-state").className = "badge state-" + status.state;

    const runner = status.runner;
    if (!runner) return;
    $("badge-mode").textContent = "MODE: " + runner.mode;

    setDot("dot-feed", true); // presence of runner implies feed object exists; refined by health panel
    setDot("dot-adapter", true);

    const acct = runner.account || {};
    $("acct-equity").textContent = fmtMoney(acct.equity_current);
    $("acct-sod").textContent = fmtMoney(acct.equity_start_of_day);
    setPct("acct-daily", acct.daily_realized_loss_percent, 2.0);
    setPct("acct-weekly", acct.weekly_realized_loss_percent, 4.0);

    $("risk-consec").textContent = acct.consecutive_losses_running ?? "—";
    $("risk-today").textContent = acct.trades_today ?? "—";
    $("risk-recovery").textContent = acct.in_recovery_mode ? "ACTIVE (0.5%)" : "off (1.0%)";
    $("risk-brake").textContent = acct.monthly_brake_active ? "TRIPPED" : "clear";
    $("risk-brake").className = "value " + (acct.monthly_brake_active ? "bad" : "good");

    renderStagePanel(runner.instruments || {});
  }

  function setDot(id, up) {
    const el = $(id);
    el.className = "dot " + (up ? "up" : "down");
  }
  function fmtMoney(v) {
    if (v === undefined || v === null) return "—";
    return "$" + Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function setPct(id, v, limit) {
    const el = $(id);
    if (v === undefined || v === null) { el.textContent = "—"; return; }
    el.textContent = v.toFixed(2) + "%";
    el.className = "value " + (v >= limit ? "bad" : "");
  }

  function renderStagePanel(instruments) {
    const container = $("stage-panel");
    const keys = Object.keys(instruments);
    if (!keys.length) { container.innerHTML = '<div class="empty">No engine data yet.</div>'; return; }
    container.innerHTML = keys.map((sym) => {
      const info = instruments[sym];
      const label = STAGE_LABELS[info.stage] || info.stage;
      const activeLine = info.active_trade ? `Active trade: ${info.active_trade}` : (info.pending_trade ? `Pending order: ${info.pending_trade}` : "No open exposure");
      const blocked = info.day_trading_allowed === false ? `<div class="stage-detail">Blocked: ${info.day_block_reason || "n/a"}</div>` : "";
      return `<div class="stage-block">
        <div class="stage-instrument">${sym}</div>
        <div class="stage-name">${label}</div>
        <div class="stage-detail">${activeLine}</div>
        ${blocked}
      </div>`;
    }).join("");
  }

  // ---------------------------------------------------------------- tables
  function renderPositions(rows) {
    const body = $("positions-body");
    if (!rows.length) { body.innerHTML = '<tr><td colspan="7" class="empty">No open positions.</td></tr>'; return; }
    body.innerHTML = rows.map((p) => `<tr>
      <td>${p.instrument}</td>
      <td><span class="pill ${p.direction === "LONG" ? "long" : "short"}">${p.direction}</span></td>
      <td>${p.volume}</td>
      <td>${fmtPrice(p.open_price)}</td>
      <td>${fmtPrice(p.stop_price)}</td>
      <td>${fmtPrice(p.tp_price)}</td>
      <td class="${p.unrealized_pnl >= 0 ? "r-pos" : "r-neg"}">${fmtMoney(p.unrealized_pnl)}</td>
    </tr>`).join("");
  }

  function renderTrades(rows) {
    const body = $("trades-body");
    if (!rows.length) { body.innerHTML = '<tr><td colspan="8" class="empty">No closed trades yet.</td></tr>'; return; }
    body.innerHTML = rows.slice(0, 100).map((t) => `<tr>
      <td>${t.instrument}</td>
      <td>${t.session}</td>
      <td><span class="pill ${t.direction === "LONG" ? "long" : "short"}">${t.direction}</span></td>
      <td>${fmtPrice(t.entry_price)}</td>
      <td>${fmtPrice(t.exit_price)}</td>
      <td>${t.close_reason || "—"}</td>
      <td class="${(t.r_result || 0) >= 0 ? "r-pos" : "r-neg"}">${t.r_result != null ? t.r_result.toFixed(2) + "R" : "—"}</td>
      <td>${t.rule_compliance ? "✅" : "❌"}</td>
    </tr>`).join("");
  }

  function renderSkips(rows) {
    const body = $("skips-body");
    if (!rows.length) { body.innerHTML = '<tr><td colspan="4" class="empty">No skips logged yet.</td></tr>'; return; }
    body.innerHTML = rows.slice(0, 100).map((s) => `<tr>
      <td>${fmtTime(s.timestamp)}</td><td>${s.instrument}</td><td>${s.session}</td><td>${s.reason}</td>
    </tr>`).join("");
  }

  function renderHealth(rows) {
    const body = $("health-body");
    if (!rows.length) { body.innerHTML = '<tr><td colspan="5" class="empty">No health data yet.</td></tr>'; return; }
    body.innerHTML = rows.map((h) => `<tr>
      <td>${h.component}</td>
      <td><span class="dot ${h.status === "UP" ? "up" : (h.status === "DEGRADED" ? "warn" : "down")}"></span> ${h.status}</td>
      <td>${h.latency_ms != null ? h.latency_ms.toFixed(0) + "ms" : "—"}</td>
      <td>${h.detail || ""}</td>
      <td>${fmtTime(h.timestamp)}</td>
    </tr>`).join("");
    const overallUp = rows.every((h) => h.status === "UP");
    setDot("dot-feed", rows.some((h) => h.component === "data_feed" && h.status === "UP"));
    setDot("dot-adapter", rows.some((h) => h.component === "execution_adapter" && h.status === "UP"));
  }

  function renderStageLog(rows) {
    const el = $("stage-log");
    if (!rows.length) { el.innerHTML = '<div class="empty">Waiting for events…</div>'; return; }
    el.innerHTML = rows.slice(0, 200).map((r) => `<div class="log-row">
      <div class="log-time">${fmtTime(r.timestamp, true)}</div>
      <div class="log-msg"><b>${r.instrument}</b> — ${STAGE_LABELS[r.stage] || r.stage}${r.detail ? " — " + r.detail : ""}</div>
    </div>`).join("");
  }

  function renderSystemLog(rows) {
    const el = $("system-log");
    if (!rows.length) { el.innerHTML = '<div class="empty">Waiting for events…</div>'; return; }
    el.innerHTML = rows.slice(0, 200).map((r) => `<div class="log-row">
      <div class="log-time">${fmtTime(r.timestamp, true)}</div>
      <div class="log-level ${r.level}">${r.level}</div>
      <div class="log-msg">[${r.component}] ${r.message}</div>
    </div>`).join("");
  }

  function renderAI(rows) {
    const body = $("ai-body");
    if (!rows.length) { body.innerHTML = '<tr><td colspan="5" class="empty">No AI insights yet.</td></tr>'; return; }
    body.innerHTML = rows.slice(0, 100).map((r) => `<tr>
      <td>${fmtTime(r.timestamp)}</td><td>${r.category}</td><td>${r.metric}</td>
      <td>${r.value != null ? Number(r.value).toFixed(4) : "—"}</td>
      <td>${r.detail ? JSON.stringify(r.detail) : ""}</td>
    </tr>`).join("");
  }

  function renderPerformance(summary) {
    $("perf-trades").textContent = summary.trades_count ?? 0;
    $("perf-winrate").textContent = summary.win_rate != null ? (summary.win_rate * 100).toFixed(1) + "%" : "—";
    $("perf-winrate").className = "value " + (summary.win_rate_in_expected_range === false ? "bad" : summary.win_rate_in_expected_range === true ? "good" : "");
    $("perf-expectancy").textContent = summary.expectancy_r != null ? summary.expectancy_r.toFixed(3) + "R" : "—";
    $("perf-expectancy").className = "value " + (summary.expectancy_in_expected_range === false ? "bad" : summary.expectancy_in_expected_range === true ? "good" : "");
    $("perf-compliance").textContent = summary.rule_compliance_rate != null ? (summary.rule_compliance_rate * 100).toFixed(1) + "%" : "—";
  }

  function fmtPrice(v) { return v == null ? "—" : Number(v).toFixed(5).replace(/0+$/, "").replace(/\.$/, ""); }
  function fmtTime(iso, timeOnly) {
    if (!iso) return "—";
    const d = new Date(iso);
    return timeOnly ? d.toLocaleTimeString() : d.toLocaleString();
  }

  // ---------------------------------------------------------------- equity chart
  function renderEquityChart(payload) {
    const svg = $("equity-chart");
    const tooltip = $("chart-tooltip");
    const curve = payload.curve || [];
    const W = 760, H = 220, PAD = 28;
    svg.innerHTML = "";
    if (curve.length < 2) {
      svg.innerHTML = `<text x="${W/2}" y="${H/2}" text-anchor="middle">Not enough closed trades yet for an equity curve.</text>`;
      return;
    }
    const values = curve.map((c) => c.cumulative_r);
    const min = Math.min(0, ...values), max = Math.max(0, ...values);
    const range = (max - min) || 1;
    const x = (i) => PAD + (i / (curve.length - 1)) * (W - PAD * 2);
    const y = (v) => H - PAD - ((v - min) / range) * (H - PAD * 2);

    const ns = "http://www.w3.org/2000/svg";
    const zeroY = y(0);
    const gridline = document.createElementNS(ns, "line");
    gridline.setAttribute("x1", PAD); gridline.setAttribute("x2", W - PAD);
    gridline.setAttribute("y1", zeroY); gridline.setAttribute("y2", zeroY);
    gridline.setAttribute("class", "chart-baseline");
    svg.appendChild(gridline);

    let path = "M " + curve.map((c, i) => `${x(i)},${y(c.cumulative_r)}`).join(" L ");
    const line = document.createElementNS(ns, "path");
    line.setAttribute("d", path);
    line.setAttribute("class", "chart-line");
    svg.appendChild(line);

    let ddPath = `M ${x(0)},${zeroY} ` + curve.map((c, i) => `L ${x(i)},${y(c.cumulative_r - c.drawdown_r)}`).join(" ") + ` L ${x(curve.length - 1)},${zeroY} Z`;
    // simple drawdown shading beneath the equity line down to the running peak
    const dd = document.createElementNS(ns, "path");
    let ddArea = "M " + curve.map((c, i) => `${x(i)},${y(c.cumulative_r)}`).join(" L ") +
      " L " + curve.map((c, i) => `${x(curve.length - 1 - i)},${y(c.cumulative_r + c.drawdown_r)}`).join(" L ") + " Z";
    dd.setAttribute("d", ddArea);
    dd.setAttribute("class", "chart-dd");
    svg.insertBefore(dd, line);

    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", PAD); label.setAttribute("y", 14);
    label.textContent = `Total: ${values[values.length - 1].toFixed(2)}R   Max drawdown: ${payload.max_drawdown_r.toFixed(2)}R`;
    svg.appendChild(label);

    // hover crosshair
    const hitArea = document.createElementNS(ns, "rect");
    hitArea.setAttribute("x", 0); hitArea.setAttribute("y", 0); hitArea.setAttribute("width", W); hitArea.setAttribute("height", H);
    hitArea.setAttribute("fill", "transparent");
    hitArea.addEventListener("mousemove", (evt) => {
      const rect = svg.getBoundingClientRect();
      const relX = ((evt.clientX - rect.left) / rect.width) * W;
      const i = Math.max(0, Math.min(curve.length - 1, Math.round(((relX - PAD) / (W - PAD * 2)) * (curve.length - 1))));
      const pt = curve[i];
      tooltip.style.opacity = 1;
      tooltip.style.left = (evt.clientX - rect.left + 12) + "px";
      tooltip.style.top = (evt.clientY - rect.top - 30) + "px";
      tooltip.innerHTML = `<b>${fmtTime(pt.time)}</b><br/>Cumulative: ${pt.cumulative_r.toFixed(2)}R<br/>Drawdown: ${pt.drawdown_r.toFixed(2)}R`;
    });
    hitArea.addEventListener("mouseleave", () => { tooltip.style.opacity = 0; });
    svg.appendChild(hitArea);
  }

  // ---------------------------------------------------------------- polling + websocket
  async function refreshAll() {
    try {
      const [status, positions, trades, skips, health, stageLog, sysLog, ai, perf, equity] = await Promise.all([
        getJSON("/bot/status"),
        getJSON("/dashboard/positions"),
        getJSON("/dashboard/trades/closed"),
        getJSON("/dashboard/trades/skips"),
        getJSON("/dashboard/connection-health"),
        getJSON("/dashboard/execution-log"),
        getJSON("/dashboard/system-logs"),
        getJSON("/dashboard/ai-insights"),
        getJSON("/dashboard/performance"),
        getJSON("/dashboard/equity-curve"),
      ]);
      applyStatus(status);
      renderPositions(positions);
      renderTrades(trades);
      renderSkips(skips);
      renderHealth(health);
      renderStageLog(stageLog);
      renderSystemLog(sysLog);
      renderAI(ai);
      renderPerformance(perf);
      renderEquityChart(equity);
    } catch (e) {
      console.error("refreshAll failed", e);
    }
  }

  let ws;
  function connectWS() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/api/ws`);
    ws.onopen = () => { setDot("dot-ws", true); $("ws-label").textContent = "live"; };
    ws.onclose = () => { setDot("dot-ws", false); $("ws-label").textContent = "reconnecting…"; setTimeout(connectWS, 2000); };
    ws.onerror = () => ws.close();
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "status") applyStatus(msg.data);
      } catch (e) { /* ignore */ }
    };
  }

  connectWS();
  refreshAll();
  setInterval(refreshAll, 5000);
})();
