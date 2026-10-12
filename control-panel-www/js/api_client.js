(function () {
  "use strict";

  const TOKEN_KEY = "gs_device_token";

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function setToken(value) {
    if (value) localStorage.setItem(TOKEN_KEY, value);
  }

  async function api(path, options) {
    const headers = Object.assign(
      { "Content-Type": "application/json", "X-GS-Token": getToken() },
      (options && options.headers) || {}
    );
    const res = await fetch(path, Object.assign({}, options || {}, { headers }));
    const data = await res.json().catch(function () {
      return { ok: false, error: "invalid json" };
    });
    if (!res.ok) throw new Error(data.error || data.reason || res.statusText);
    return data;
  }

  window.GSApi = {
    getToken: getToken,
    setToken: setToken,
    bootstrap: function () {
      return api("/api/bootstrap");
    },
    pair: function (pairCode, deviceName) {
      return api("/api/pair", {
        method: "POST",
        body: JSON.stringify({ pair_code: pairCode, device_name: deviceName }),
      });
    },
    webAutoPair: function (deviceName) {
      return fetch("/api/pair/web-auto", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_name: deviceName || "WebPanel" }),
      })
        .then(function (res) {
          return res.json().then(function (data) {
            if (!res.ok) throw new Error(data.error || res.statusText);
            return data;
          });
        });
    },
    status: function () {
      return api("/api/status");
    },
    account: function () {
      return api("/api/account");
    },
    signals: function () {
      return api("/api/signals");
    },
    stack: function () {
      return api("/api/stack");
    },
    positions: function () {
      return api("/api/positions");
    },
    history: function () {
      return api("/api/history");
    },
    wsSnapshot: function () {
      return api("/api/ws/snapshot");
    },
    act: function (body) {
      return api("/api/act", { method: "POST", body: JSON.stringify(body) });
    },
  };
})();
