(function () {
  "use strict";

  const CONFIRM = "CONFIRM-PANIC";

  function renderPanel(root) {
    root.innerHTML =
      '<label>رمز PIN<input type="password" id="gs-pin" maxlength="12" inputmode="numeric" /></label>' +
      '<label>تأكيد الطوارئ<input type="text" id="gs-confirm" placeholder="' +
      CONFIRM +
      '" /></label>' +
      '<label>ضغط مطول (ث)<input type="number" id="gs-hold" min="0" step="0.1" value="1.5" /></label>' +
      '<label>2FA (اختياري)<input type="text" id="gs-totp" maxlength="8" inputmode="numeric" /></label>';
  }

  function payloadBase() {
    return {
      pin: (document.getElementById("gs-pin") || {}).value || "",
      confirm: (document.getElementById("gs-confirm") || {}).value || "",
      hold_seconds: parseFloat((document.getElementById("gs-hold") || {}).value || "1.5"),
      totp: (document.getElementById("gs-totp") || {}).value || "",
    };
  }

  window.GSPocketLock = {
    renderPanel: renderPanel,
    payloadBase: payloadBase,
    CONFIRM: CONFIRM,
  };
})();
