(function () {
  "use strict";

  const statusLine = document.getElementById("status-line");
  const accountBody = document.getElementById("account-body");
  const stackBody = document.getElementById("stack-body");
  const signalsList = document.getElementById("signals-list");
  const orderbookList = document.getElementById("orderbook-list");
  const pocketPanel = document.getElementById("pocket-lock-panel");
  const pairCard = document.getElementById("pair-card");
  const pairStatus = document.getElementById("pair-status");

  let wsPort = 8791;
  let wsHandle = null;

  if (window.GSPocketLock && pocketPanel) {
    window.GSPocketLock.renderPanel(pocketPanel);
  }

  function renderAccount(data) {
    const acc = (data && data.account) || {};
    accountBody.textContent =
      "Equity: " +
      (acc.equity != null ? acc.equity : "—") +
      " | USDT: " +
      (acc.balance != null ? acc.balance : acc.free_cash != null ? acc.free_cash : "—");
  }

  function renderSignals(data) {
    signalsList.innerHTML = "";
    const rows = (data && data.signals) || [];
    rows.slice(0, 15).forEach(function (row) {
      const li = document.createElement("li");
      li.textContent =
        (row.sym || row.symbol || "?") +
        " " +
        (row.signal || "") +
        " " +
        (row.score != null ? row.score + "/10" : "");
      signalsList.appendChild(li);
    });
  }

  function renderStack(data) {
    stackBody.textContent = JSON.stringify((data && data.stack) || {}, null, 2);
  }

  function renderOrderbookEvents(events) {
    orderbookList.innerHTML = "";
    (events || [])
      .filter(function (e) {
        return e.channel === "orderbook";
      })
      .slice(-8)
      .reverse()
      .forEach(function (ev) {
        const li = document.createElement("li");
        const p = ev.payload || {};
        li.textContent =
          ev.symbol +
          " bid=" +
          (p.bid_qty != null ? p.bid_qty.toFixed(2) : "?") +
          " ask=" +
          (p.ask_qty != null ? p.ask_qty.toFixed(2) : "?") +
          " imb=" +
          (p.imbalance != null ? (p.imbalance * 100).toFixed(1) + "%" : "?");
        orderbookList.appendChild(li);
      });
  }

  function connectWs() {
    if (wsHandle) {
      try {
        wsHandle.close();
      } catch (e) {}
    }
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const host = location.hostname || "127.0.0.1";
    const url = proto + "//" + host + ":" + wsPort;
    try {
      wsHandle = new WebSocket(url);
      wsHandle.onmessage = function (msg) {
        try {
          const data = JSON.parse(msg.data);
          if (data.type === "hello" && data.snapshot) {
            renderOrderbookEvents(data.snapshot);
          }
          if (data.type === "event" && data.channel === "orderbook") {
            renderOrderbookEvents([
              {
                channel: "orderbook",
                symbol: data.symbol,
                payload: data.payload,
              },
            ]);
          }
        } catch (e) {}
      };
    } catch (e) {
      orderbookList.innerHTML = "<li>WS غير متاح — استخدم /api/ws/snapshot</li>";
    }
  }

  async function refresh() {
    if (!window.GSApi.getToken()) {
      statusLine.textContent = "اربط الجهاز أولاً";
      return;
    }
    try {
      const st = await window.GSApi.status();
      statusLine.textContent =
        "متصل — " +
        (st.status && st.status.open_positions != null
          ? st.status.open_positions + " مركز"
          : "OK");
      const acc = await window.GSApi.account();
      renderAccount(acc);
      const sig = await window.GSApi.signals();
      renderSignals(sig);
      const stack = await window.GSApi.stack();
      renderStack(stack);
      const snap = await window.GSApi.wsSnapshot();
      renderOrderbookEvents(snap.events || []);
    } catch (err) {
      statusLine.textContent = "خطأ: " + err.message;
    }
  }

  document.getElementById("btn-pair").addEventListener("click", function () {
    const code = (document.getElementById("pair-code") || {}).value || "";
    const name = (document.getElementById("device-name") || {}).value || "WebPanel";
    window.GSApi.pair(code.trim(), name.trim())
      .then(function (res) {
        if (res.device_token) {
          window.GSApi.setToken(res.device_token);
          pairStatus.textContent = "تم الربط";
          pairCard.style.display = "none";
          refresh();
        }
      })
      .catch(function (e) {
        pairStatus.textContent = e.message;
      });
  });

  document.getElementById("btn-refresh").addEventListener("click", function () {
    window.GSApi.act({ act: "refresh" }).then(refresh).catch(function (e) {
      statusLine.textContent = e.message;
    });
  });

  document.getElementById("btn-pause").addEventListener("click", function () {
    window.GSApi.act({ act: "pause" }).then(refresh);
  });

  document.getElementById("btn-panic").addEventListener("click", function () {
    const body = Object.assign({ act: "panic" }, window.GSPocketLock.payloadBase());
    window.GSApi.act(body).then(refresh);
  });

  window.GSApi.bootstrap()
    .then(function (boot) {
      if (boot.ws_port) wsPort = boot.ws_port;
      if (window.GSApi.getToken()) {
        pairCard.style.display = "none";
        connectWs();
        refresh();
      } else {
        statusLine.textContent = "أدخل رمز الربط من mobile_api_credentials";
      }
    })
    .catch(function () {
      refresh();
    });
})();
