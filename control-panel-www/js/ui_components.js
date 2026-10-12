(function () {
  "use strict";

  const statusLine = document.getElementById("status-line");
  const accountBody = document.getElementById("account-body");
  const signalsList = document.getElementById("signals-list");
  const pocketPanel = document.getElementById("pocket-lock-panel");

  if (window.GSPocketLock && pocketPanel) {
    window.GSPocketLock.renderPanel(pocketPanel);
  }

  function renderAccount(data) {
    const acc = (data && data.account) || {};
    accountBody.textContent =
      "Equity: " +
      (acc.equity != null ? acc.equity : "—") +
      " | USDT: " +
      (acc.balance != null ? acc.balance : "—");
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

  async function refresh() {
    try {
      const st = await window.GSApi.status();
      statusLine.textContent = "متصل — " + (st.status && st.status.open_positions != null
        ? st.status.open_positions + " مركز"
        : "OK");
      const acc = await window.GSApi.account();
      renderAccount(acc);
      const sig = await window.GSApi.signals();
      renderSignals(sig);
    } catch (err) {
      statusLine.textContent = "خطأ: " + err.message;
    }
  }

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

  window.GSApi.bootstrap().then(refresh).catch(function () {
    refresh();
  });
})();
