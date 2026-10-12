(function () {
  "use strict";

  const $ = function (id) {
    return document.getElementById(id);
  };

  const statusLine = $("status-line");
  const syncLine = $("sync-line");
  const signalsList = $("signals-list");
  const signalsRules = $("signals-rules");
  const signalsMeta = $("signals-meta");
  const positionsList = $("positions-list");
  const historyList = $("history-list");
  const reportBody = $("report-body");
  const pairCard = $("pair-card");
  const pairStatus = $("pair-status");
  const pocketPanel = $("pocket-lock-panel");
  const btnToggleRun = $("btn-toggle-run");
  const toggleRunLabel = $("toggle-run-label");
  const toggleRunIcon = $("toggle-run-icon");

  let wsPort = 8791;
  let refreshTimer = null;
  let lastPaused = null;
  let alertsEnabled = localStorage.getItem("gs_alerts_enabled") === "1";

  if (window.GSPocketLock && pocketPanel) {
    window.GSPocketLock.renderPanel(pocketPanel);
  }

  function fmtMoney(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return "$0.00";
    const sign = v < 0 ? "-" : "";
    return sign + "$" + Math.abs(v).toFixed(2);
  }

  function fmtBalance(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return "—";
    return "$" + v.toFixed(2);
  }

  function fmtPct(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return "—";
    const sign = v > 0 ? "+" : "";
    return sign + v.toFixed(2) + "%";
  }

  function liveTimeStr() {
    try {
      return new Date().toLocaleTimeString("ar-EG", {
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch (e) {
      return new Date().toLocaleTimeString();
    }
  }

  function setDailyPct(el, pct) {
    el.textContent = fmtPct(pct);
    el.classList.remove("gs-positive", "gs-negative");
    const v = Number(pct);
    if (Number.isFinite(v)) {
      el.classList.add(v >= 0 ? "gs-positive" : "gs-negative");
    }
  }

  function renderHero(status) {
    const st = status || {};
    $("stat-balance").textContent = fmtBalance(st.balance);
    setDailyPct($("stat-daily"), st.daily_net_pct);
    const open = st.open_positions != null ? st.open_positions : 0;
    const dust = st.dust_positions != null ? st.dust_positions : 0;
    $("stat-open").textContent = open + " • غبار " + dust;
    $("stat-win").textContent = fmtMoney(st.win_open);
    $("stat-lose").textContent = fmtMoney(st.lose_open);

    lastPaused = !!st.paused;
    btnToggleRun.classList.toggle("is-paused", lastPaused);
    toggleRunLabel.textContent = lastPaused ? "تشغيل" : "إيقاف";
    toggleRunIcon.textContent = lastPaused ? "▶" : "⏸";
  }

  function renderRules(rules) {
    const r = rules || {};
    const ladder = (r.strength_ladder || [70, 75, 80, 85, 90, 95, 100]).join(" · ");
    signalsRules.textContent =
      "عرض ≥ " +
      (r.display_min != null ? r.display_min : 70) +
      " فقط · سلم " +
      ladder +
      " · تنبيه ≥ " +
      (r.notify_min != null ? r.notify_min : 70) +
      " · تلقائي ≥ " +
      (r.auto_min != null ? r.auto_min : 80) +
      " · أهداف × " +
      (r.targets != null ? r.targets : 3);
  }

  function renderSignals(rows, rules) {
    signalsList.innerHTML = "";
    const minDisplay = (rules && rules.display_min) || 70;
    const filtered = (rows || []).filter(function (row) {
      return Number(row.score || row.strength || 0) >= minDisplay;
    });
    filtered.sort(function (a, b) {
      return Number(b.score || 0) - Number(a.score || 0);
    });

    if (!filtered.length) {
      const li = document.createElement("li");
      li.className = "gs-muted";
      li.textContent = "لا إشارات ≥ " + minDisplay + " حالياً — يتم التحديث تلقائياً";
      signalsList.appendChild(li);
      return;
    }

    filtered.slice(0, 24).forEach(function (row) {
      const pct = Number(row.score != null ? row.score : row.strength || 0);
      const sym = row.sym || row.symbol || "?";
      const price = row.price != null ? Number(row.price) : 0;
      const liq = row.liquidity != null ? row.liquidity : "—";
      const sig = row.signal || "WAIT";
      const autoMin = (rules && rules.auto_min) || 80;
      const isAuto = pct >= autoMin;

      const li = document.createElement("li");
      li.className = "gs-signal-card";
      li.innerHTML =
        '<div class="gs-signal-score">' +
        pct +
        "</div>" +
        '<div><div class="gs-signal-head"><span class="gs-signal-sym">' +
        sym +
        " " +
        pct +
        '</span></div><div class="gs-signal-tags">' +
        (isAuto ? '<span class="gs-tag gs-tag--auto">تلقائي</span>' : "") +
        '<span class="gs-tag">' +
        (price > 0 ? price.toFixed(price < 1 ? 4 : 2) : "—") +
        "</span>" +
        '<span class="gs-tag">سيولة ' +
        liq +
        "</span>" +
        '<span class="gs-tag gs-tag--wait">' +
        sig +
        " " +
        pct +
        "/100</span></div></div>";
      signalsList.appendChild(li);
    });
  }

  function renderPositions(rows) {
    positionsList.innerHTML = "";
    const list = rows || [];
    if (!list.length) {
      positionsList.innerHTML = '<li class="gs-muted">لا مراكز مفتوحة</li>';
      return;
    }
    list.forEach(function (p) {
      const li = document.createElement("li");
      li.className = "gs-pos-row";
      const sym = p.symbol || p.sym || "?";
      const pnl = Number(p.pnl != null ? p.pnl : 0);
      li.textContent =
        sym +
        " · PnL " +
        fmtMoney(pnl) +
        (p.entry_price != null ? " · دخول " + p.entry_price : "");
      positionsList.appendChild(li);
    });
  }

  function renderHistory(rows) {
    historyList.innerHTML = "";
    const list = (rows || []).slice(0, 30);
    if (!list.length) {
      historyList.innerHTML = '<li class="gs-muted">لا سجل بعد</li>';
      return;
    }
    list.forEach(function (t) {
      const li = document.createElement("li");
      li.className = "gs-history-row";
      const pnl = Number(t.pnl != null ? t.pnl : 0);
      li.textContent =
        (t.symbol || "?") +
        " · " +
        (t.side || "") +
        " · " +
        fmtMoney(pnl) +
        (t.closed_at ? " · " + String(t.closed_at).slice(0, 16) : "");
      historyList.appendChild(li);
    });
  }

  function reportRow(label, value) {
    return (
      '<div class="gs-report-row"><span>' +
      label +
      '</span><span dir="ltr">' +
      (value != null && value !== "" ? value : "—") +
      "</span></div>"
    );
  }

  function renderReport(status, stack, rules) {
    const st = status || {};
    const batt = (stack && stack.battalion) || {};
    const disc = (stack && stack.notify && stack.notify.discord) || {};
    const tri = batt.tri_commander || batt.commanders || batt;
    let triLine = "—";
    if (tri && typeof tri === "object") {
      const parts = [];
      ["smc", "gold_flash", "micro_momentum", "SMC", "GoldFlash", "MicroMomentum"].forEach(function (k) {
        if (tri[k] != null) parts.push(k + ": " + JSON.stringify(tri[k]).slice(0, 40));
      });
      if (parts.length) triLine = parts.slice(0, 3).join(" · ");
      else if (batt.ok) triLine = "Battalion نشط";
    }

    reportBody.innerHTML =
      reportRow("Tri-Commander / Battalion", triLine) +
      reportRow("Kill Switch", st.kill_switch ? "مفعّل" : "غير مفعّل") +
      reportRow("Demo", st.demo ? "Binance Demo" : "—") +
      reportRow("Discord", disc.configured ? disc.mode || "configured" : "غير مربوط") +
      reportRow("Strategy", st.strategy_code || stack.strategy_code || "—") +
      reportRow("حد الصفقات اليوم", rules && rules.daily_trade_cap != null ? rules.daily_trade_cap : "—") +
      reportRow("Tunnel", stack.tunnel_url || "—");
  }

  function updateAlertChip() {
    const btn = $("btn-alerts");
    const label = $("alert-chip-label");
    if (!btn || !label) return;
    btn.setAttribute("aria-pressed", alertsEnabled ? "true" : "false");
    label.textContent = alertsEnabled ? "التنبيهات مفعّلة" : "تفعيل التنبيه";
  }

  function maybeNotifySignal(prevRows, nextRows) {
    if (!alertsEnabled || typeof Notification === "undefined") return;
    if (Notification.permission !== "granted") return;
    const prev = {};
    (prevRows || []).forEach(function (r) {
      prev[r.sym || r.symbol] = Number(r.score || 0);
    });
    (nextRows || []).forEach(function (r) {
      const sym = r.sym || r.symbol;
      const score = Number(r.score || 0);
      if (score >= 80 && score > (prev[sym] || 0)) {
        try {
          new Notification("GoldenShield", {
            body: sym + " · " + score + "/100 · " + (r.signal || ""),
          });
        } catch (e) {}
      }
    });
  }

  let lastSignals = [];

  async function refresh() {
    if (!window.GSApi.getToken()) {
      statusLine.textContent = "اربط الجهاز أو فعّل web-auto";
      return;
    }

    const parts = [];
    let statusPayload = {};
    let rules = {};

    try {
      const stRes = await window.GSApi.status();
      statusPayload = (stRes && stRes.status) || {};
      rules = (stRes && stRes.rules) || {};
      renderHero(statusPayload);
      renderRules(rules);
    } catch (e) {
      parts.push("status:" + (e.message || "err"));
    }

    try {
      const acc = await window.GSApi.account();
      const st = (acc && acc.status) || statusPayload;
      if (st && Object.keys(st).length) renderHero(st);
    } catch (e) {
      parts.push("account:" + (e.message || "err"));
    }

    try {
      const sig = await window.GSApi.signals();
      const rows = (sig && sig.signals) || [];
      maybeNotifySignal(lastSignals, rows);
      lastSignals = rows;
      renderSignals(rows, rules);
      signalsMeta.textContent =
        "آخر تحديث · " +
        liveTimeStr() +
        " · سيولة السوق: " +
        (rows[0] && rows[0].liquidity != null ? rows[0].liquidity : "—");
    } catch (e) {
      parts.push("signals:" + (e.message || "err"));
    }

    try {
      const pos = await window.GSApi.positions();
      renderPositions((pos && pos.positions) || []);
    } catch (e) {
      parts.push("positions:" + (e.message || "err"));
    }

    try {
      const hist = await window.GSApi.history();
      renderHistory((hist && hist.history) || []);
    } catch (e) {
      parts.push("history:" + (e.message || "err"));
    }

    try {
      const stack = await window.GSApi.stack();
      renderReport(statusPayload, (stack && stack.stack) || {}, rules);
    } catch (e) {
      parts.push("stack:" + (e.message || "err"));
    }

    syncLine.textContent = "آخر مزامنة حية: " + liveTimeStr();
    if (parts.length) {
      statusLine.textContent = "آخر مزامنة " + liveTimeStr() + " • " + parts.join(", ");
    } else {
      statusLine.textContent =
        (statusPayload.bot_running ? "البوت يعمل" : "البوت متوقف") +
        (statusPayload.paused ? " · الدخول موقوف" : "");
    }
  }

  function actClose(mode) {
    const act = mode === "win" ? "close_winners" : "close_losers";
    return window.GSApi.act({ act: act }).then(refresh);
  }

  $("btn-close-win").addEventListener("click", function () {
    actClose("win").catch(function (e) {
      statusLine.textContent = e.message;
    });
  });

  $("btn-close-lose").addEventListener("click", function () {
    actClose("lose").catch(function (e) {
      statusLine.textContent = e.message;
    });
  });

  $("btn-toggle-run").addEventListener("click", function () {
    const act = lastPaused ? "resume" : "pause";
    window.GSApi.act({ act: act })
      .then(refresh)
      .catch(function (e) {
        statusLine.textContent = e.message;
      });
  });

  $("btn-refresh").addEventListener("click", function () {
    window.GSApi.act({ act: "refresh" })
      .then(refresh)
      .catch(function (e) {
        statusLine.textContent = e.message;
      });
  });

  $("btn-panic").addEventListener("click", function () {
    if (!window.confirm("تأكيد الطوارئ — إغلاق الكل وإيقاف الدخول؟")) return;
    const body = Object.assign({ act: "panic" }, window.GSPocketLock.payloadBase());
    window.GSApi.act(body)
      .then(refresh)
      .catch(function (e) {
        statusLine.textContent = e.message;
      });
  });

  $("btn-alerts").addEventListener("click", function () {
    alertsEnabled = !alertsEnabled;
    localStorage.setItem("gs_alerts_enabled", alertsEnabled ? "1" : "0");
    updateAlertChip();
    if (alertsEnabled && typeof Notification !== "undefined") {
      Notification.requestPermission().catch(function () {});
    }
  });

  $("btn-pair").addEventListener("click", function () {
    const code = ($("pair-code") || {}).value || "";
    const name = ($("device-name") || {}).value || "WebPanel";
    window.GSApi.pair(code.trim(), name.trim())
      .then(function (res) {
        if (res.device_token) {
          window.GSApi.setToken(res.device_token);
          pairStatus.textContent = "تم الربط";
          pairCard.classList.add("gs-pair--hidden");
          refresh();
        }
      })
      .catch(function (e) {
        pairStatus.textContent = e.message;
        pairCard.classList.remove("gs-pair--hidden");
      });
  });

  function startPanel() {
    pairCard.classList.add("gs-pair--hidden");
    updateAlertChip();
    refresh();
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(refresh, 15000);
  }

  function tryWebAutoPair(boot) {
    if (!boot || !boot.web_direct_access) return Promise.resolve(false);
    return window.GSApi.webAutoPair("WebPanel").then(function (res) {
      if (res.device_token) {
        window.GSApi.setToken(res.device_token);
        return true;
      }
      return false;
    });
  }

  window.GSApi.bootstrap()
    .then(function (boot) {
      if (boot.ws_port) wsPort = boot.ws_port;
      if (window.GSApi.getToken()) {
        startPanel();
        return;
      }
      return tryWebAutoPair(boot).then(function (ok) {
        if (ok) {
          startPanel();
        } else {
          pairCard.classList.remove("gs-pair--hidden");
          statusLine.textContent = "أدخل رمز الربط من mobile_api_credentials";
        }
      });
    })
    .catch(function () {
      refresh();
    });
})();
