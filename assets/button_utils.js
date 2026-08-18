document.addEventListener("DOMContentLoaded", function () {

  /* =========================================================
     1. BUTTON LOADING STATES
     Buttons with data-loading="true" get disabled + spinner
     on click, re-enabled after Dash callback completes.
     ========================================================= */
  var LOADING_IDS = [
    "btn-save-cloud", "btn-load-cloud", "btn-reload-module",
    "refresh-data", "btn-verify-api", "btn-download-csv",
    "btn-process", "btn-single-analysis"
  ];
  var LOADING_TEXT = {
    "btn-save-cloud": "Guardando...",
    "btn-load-cloud": "Cargando...",
    "btn-reload-module": "Recargando...",
    "refresh-data": "Refrescando...",
    "btn-verify-api": "Verificando...",
    "btn-download-csv": "Descargando...",
    "btn-process": "Procesando...",
    "btn-single-analysis": "Analizando..."
  };

  function setButtonLoading(btn, loading, btnId) {
    if (!btn) return;
    if (loading) {
      btn.setAttribute("data-original-text", btn.innerHTML);
      btn.disabled = true;
      btn.classList.add("is-loading");
      var spinner = document.createElement("span");
      spinner.className = "btn-spinner";
      btn.innerHTML = "";
      btn.appendChild(spinner);
      var lbl = document.createElement("span");
      lbl.className = "btn-loading-label";
      lbl.textContent = LOADING_TEXT[btnId] || "Procesando...";
      btn.appendChild(lbl);
    } else {
      btn.disabled = false;
      btn.classList.remove("is-loading");
      btn.innerHTML = btn.getAttribute("data-original-text") || btn.innerHTML;
    }
  }

  LOADING_IDS.forEach(function (id) {
    var btn = document.getElementById(id);
    if (!btn) return;
    btn.addEventListener("click", function () {
      setButtonLoading(btn, true, id);
    });
  });

  document.addEventListener("dash:callback", function () {
    LOADING_IDS.forEach(function (id) {
      var btn = document.getElementById(id);
      if (btn && btn.classList.contains("is-loading")) {
        setButtonLoading(btn, false, id);
      }
    });
  });

  setTimeout(function () {
    LOADING_IDS.forEach(function (id) {
      var btn = document.getElementById(id);
      if (btn && btn.classList.contains("is-loading")) {
        setButtonLoading(btn, false, id);
      }
    });
  }, 20000);

  /* =========================================================
     2. CONFIRMATION BEFORE DESTRUCTIVE ACTIONS
     Intercept clear-data click and show confirm dialog.
     ========================================================= */
  var clearBtn = document.getElementById("clear-data");
  if (clearBtn) {
    clearBtn.addEventListener("click", function (e) {
      if (!window.confirm("Esto limpiara todos los datos locales y la nube.\n\n¿Continuar?")) {
        e.stopImmediatePropagation();
        e.preventDefault();
        return false;
      }
    }, true);
  }

  /* =========================================================
     3. FILE UPLOAD PREVIEW
     Show file size and validate type before upload.
     ========================================================= */
  var uploadEl = document.getElementById("upload-data");
  var fileNameEl = document.getElementById("file-name");

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  if (uploadEl && fileNameEl) {
    uploadEl.addEventListener("drop", function (e) {
      var files = e.dataTransfer && e.dataTransfer.files;
      if (files && files.length > 0) {
        var f = files[0];
        var ext = f.name.split(".").pop().toLowerCase();
        if (["xlsx", "xls"].indexOf(ext) === -1) {
          fileNameEl.innerHTML = '<span style="color:#f87171">Archivo no valido. Solo se aceptan .xlsx o .xls</span>';
          e.preventDefault();
          return false;
        }
        fileNameEl.innerHTML = '<span style="color:#93c5fd">' + f.name + '</span> <span style="color:#64748b">(' + formatSize(f.size) + ')</span>';
      }
    }, true);
  }

  /* =========================================================
     4. KEYBOARD SHORTCUTS
     R = refresh, Ctrl+D = download, 1/2/3 = modules
     Only active when no input/textarea/dropdown is focused.
     ========================================================= */
  document.addEventListener("keydown", function (e) {
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return;
    if (e.target.closest && e.target.closest(".dropdown-menu")) return;

    if (e.key === "r" || e.key === "R") {
      if (e.ctrlKey || e.metaKey) return;
      e.preventDefault();
      var refreshBtn = document.getElementById("refresh-data");
      if (refreshBtn) refreshBtn.click();
      return;
    }

    if ((e.ctrlKey || e.metaKey) && (e.key === "d" || e.key === "D")) {
      e.preventDefault();
      var dlBtn = document.getElementById("btn-download-csv");
      if (dlBtn) dlBtn.click();
      return;
    }

    if (e.key === "1") {
      e.preventDefault();
      var p = document.getElementById("mod-pedidos");
      if (p) p.click();
      return;
    }
    if (e.key === "2") {
      e.preventDefault();
      var f = document.getElementById("mod-facturas");
      if (f) f.click();
      return;
    }
    if (e.key === "3") {
      e.preventDefault();
      var inv = document.getElementById("mod-inventario");
      if (inv) inv.click();
      return;
    }
  });

  /* =========================================================
     5. TOAST NOTIFICATION HELPER
     Shows a brief toast for shortcut feedback.
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
