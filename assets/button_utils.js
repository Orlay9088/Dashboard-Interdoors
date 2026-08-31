/* =========================================================
   BUTTON UTILITIES — with AppState integration
   Fixes: loading states, confirm, upload preview, shortcuts
   ========================================================= */
document.addEventListener("DOMContentLoaded", function () {

  /* =========================================================
     1. BUTTON LOADING STATES (Bug 1+2 fix)
     Uses MutationObserver on Dash loading overlay + per-click timeout.
     ========================================================= */
  var LOADING_IDS = [
    "btn-save-cloud", "btn-load-cloud",
    "btn-verify-api",
    "btn-process", "btn-single-analysis"
  ];
  var LOADING_TEXT = {
    "btn-save-cloud": "Guardando...",
    "btn-load-cloud": "Cargando...",
    "btn-verify-api": "Verificando...",
    "btn-process": "Procesando...",
    "btn-single-analysis": "Analizando..."
  };

  function setButtonLoading(btn, loading, btnId) {
    if (!btn) return;
    if (loading) {
      btn.setAttribute("data-original-text", btn.innerHTML);
      btn.disabled = true;
      btn.classList.add("is-loading");
      btn.innerHTML = "";
      var spinner = document.createElement("span");
      spinner.className = "btn-spinner";
      btn.appendChild(spinner);
      var lbl = document.createElement("span");
      lbl.className = "btn-loading-label";
      lbl.textContent = LOADING_TEXT[btnId] || "Procesando...";
      btn.appendChild(lbl);
      if (typeof AppState !== "undefined") AppState.setLoading(btnId, true);
    } else {
      btn.disabled = false;
      btn.classList.remove("is-loading");
      btn.innerHTML = btn.getAttribute("data-original-text") || btn.innerHTML;
      if (typeof AppState !== "undefined") AppState.setLoading(btnId, false);
    }
  }

  function clearAllLoading() {
    LOADING_IDS.forEach(function (id) {
      var btn = document.getElementById(id);
      if (btn && btn.classList.contains("is-loading")) {
        setButtonLoading(btn, false, id);
      }
    });
  }

  LOADING_IDS.forEach(function (id) {
    var btn = document.getElementById(id);
    if (!btn) return;
    btn.addEventListener("click", function () {
      setButtonLoading(btn, true, id);
      setTimeout(function () {
        setButtonLoading(btn, false, id);
      }, 20000);
    });
  });

  /* MutationObserver: detect when Dash loading overlay disappears.
     Scoped to sidebar + action area to avoid watching the entire body. */
  var actionArea = document.getElementById("sidebar") || document.body;
  var observer = new MutationObserver(function () {
    var overlay = document.querySelector(
      "#_dash-loading, .dash-loading--default, ._dash-loading"
    );
    if (!overlay || overlay.style.display === "none" || overlay.children.length === 0) {
      clearAllLoading();
    }
  });
  observer.observe(actionArea, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["style", "class"],
  });

  /* Fallback: check every 3 seconds if no loading overlay exists */
  setInterval(function () {
    var overlay = document.querySelector(
      "#_dash-loading, .dash-loading--default, ._dash-loading"
    );
    var anyActive = LOADING_IDS.some(function (id) {
      var btn = document.getElementById(id);
      return btn && btn.classList.contains("is-loading");
    });
    if (anyActive && (!overlay || overlay.style.display === "none" || overlay.children.length === 0)) {
      clearAllLoading();
    }
  }, 3000);

  /* =========================================================
     2. CONFIRMATION BEFORE DESTRUCTIVE ACTIONS (Bug 3 fix)
     Removed JS hack — now handled by Dash server-side
     via dcc.ConfirmDialogProvider.
     ========================================================= */

  /* =========================================================
     3. FILE UPLOAD PREVIEW (Bug 4+10 fix)
     Listens on internal file input change event, works for
     both click-to-select and drag-and-drop.
     ========================================================= */
  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  function setupUploadPreview() {
    var uploadEl = document.getElementById("upload-data");
    var fileNameEl = document.getElementById("file-name");
    if (!uploadEl || !fileNameEl) return;

    var internalInput = uploadEl.querySelector('input[type="file"]');
    if (internalInput) {
      internalInput.addEventListener("change", function (e) {
        var files = e.target.files;
        if (files && files.length > 0) {
          var f = files[0];
          var ext = f.name.split(".").pop().toLowerCase();
          if (["xlsx", "xls"].indexOf(ext) === -1) {
            fileNameEl.innerHTML = '<span style="color:#f87171">Archivo no valido. Solo .xlsx o .xls</span>';
          } else {
            fileNameEl.innerHTML =
              '<span style="color:#93c5fd">' + f.name + "</span> " +
              '<span style="color:#64748b">(' + formatSize(f.size) + ")</span>";
          }
        }
      });
    }
  }
  setupUploadPreview();

  /* =========================================================
     4. KEYBOARD SHORTCUTS (Bug 5 fix)
     Alt+R = refresh, Ctrl+D = download, 1/2/3 = modules.
     Properly detects Dash dropdowns.
     ========================================================= */
  function isInDropdown(el) {
    if (!el || !el.closest) return false;
    return !!(
      el.closest(".dropdown-menu") ||
      el.closest(".dash-dropdown") ||
      el.closest("[class*='react-select']") ||
      el.closest("[class*='Select']") ||
      el.closest("[class*='Mantine']") ||
      el.closest(".ant-select-dropdown") ||
      el.closest(".DateInput") ||
      el.closest(".CalendarDay") ||
      el.closest(".DayPickerNavigation") ||
      el.closest("[class*='DateRangePicker']") ||
      el.closest("[class*='datepicker']") ||
      el.closest("[class*='DatePicker']")
    );
  }

  function isInInput(el) {
    if (!el) return false;
    var tag = (el.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return true;
    if (el.getAttribute && el.getAttribute("role") === "textbox") return true;
    return false;
  }

  document.addEventListener("keydown", function (e) {
    if (isInInput(e.target) || isInDropdown(e.target)) return;

    /* 1/2/3 = Module switch */
    if (e.key === "1" && !e.altKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      var p = document.getElementById("mod-pedidos");
      if (p) p.click();
      return;
    }
    if (e.key === "2" && !e.altKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      var f = document.getElementById("mod-facturas");
      if (f) f.click();
      return;
    }
    if (e.key === "3" && !e.altKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      var inv = document.getElementById("mod-inventario");
      if (inv) inv.click();
      return;
    }
  });

  /* =========================================================
     5. TOAST NOTIFICATION HELPER
     ========================================================= */
  window.showToast = function (msg, duration) {
    duration = duration || 1500;
    var t = document.createElement("div");
    t.className = "app-toast";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.classList.add("show"); }, 10);
    setTimeout(function () {
      t.classList.remove("show");
      setTimeout(function () { t.remove(); }, 300);
    }, duration);
  };

});
