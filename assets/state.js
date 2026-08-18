/* =========================================================
   STATE MANAGER — Zustand-style vanilla JS
   Centralizes app state for buttons, filters, loading.
   ========================================================= */
var AppState = (function () {
  var _state = {
    loadingButtons: {},
    sidebarOpen: false,
    currentModule: "pedidos",
    currentPage: "resumen",
  };
  var _listeners = [];

  function get(key) {
    return key ? _state[key] : Object.assign({}, _state);
  }

  function set(key, value) {
    if (typeof key === "object") {
      Object.assign(_state, key);
    } else {
      _state[key] = value;
    }
    _notify();
  }

  function subscribe(key, fn) {
    if (typeof key === "function") {
      _listeners.push({ key: null, fn: key });
    } else {
      _listeners.push({ key: key, fn: fn });
    }
    return function () {
      _listeners = _listeners.filter(function (l) { return l.fn !== fn; });
    };
  }

  function _notify() {
    _listeners.forEach(function (l) {
      if (!l.key || l.key in _state) {
        l.fn(_state);
      }
    });
  }

  function isLoading(btnId) {
    return !!_state.loadingButtons[btnId];
  }

  function setLoading(btnId, loading) {
    var buttons = Object.assign({}, _state.loadingButtons);
    if (loading) {
      buttons[btnId] = true;
    } else {
      delete buttons[btnId];
    }
    set("loadingButtons", buttons);
  }

  return {
    get: get,
    set: set,
    subscribe: subscribe,
    isLoading: isLoading,
    setLoading: setLoading,
  };
})();
