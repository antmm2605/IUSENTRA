(function (window, document) {
  const STORAGE_KEY = "hacs.firma_visibile.mode";
  const MODE_LATERALE = "laterale";
  const MODE_BASSO_DESTRA = "basso_destra";
  const VALID_MODES = new Set([MODE_LATERALE, MODE_BASSO_DESTRA]);

  function normalizeMode(value) {
    const raw = String(value || "").trim().toLowerCase();
    return VALID_MODES.has(raw) ? raw : MODE_LATERALE;
  }

  function loadStoredMode() {
    try {
      return normalizeMode(window.localStorage.getItem(STORAGE_KEY));
    } catch (_) {
      return MODE_LATERALE;
    }
  }

  function saveMode(value) {
    const mode = normalizeMode(value);
    try {
      window.localStorage.setItem(STORAGE_KEY, mode);
    } catch (_) {}
    return mode;
  }

  function syncRoot(root, mode) {
    const groupName = root?.dataset?.signatureModeName;
    if (!root || !groupName) return;
    const resolvedMode = normalizeMode(mode);
    root.querySelectorAll(`input[name="${groupName}"]`).forEach((input) => {
      input.checked = input.value === resolvedMode;
    });
  }

  function bindRoot(root) {
    if (!root || root.dataset.firmaVisibileBound === "true") return;
    const groupName = root.dataset.signatureModeName;
    if (!groupName) return;

    syncRoot(root, loadStoredMode());
    root.querySelectorAll(`input[name="${groupName}"]`).forEach((input) => {
      input.addEventListener("change", () => {
        const mode = saveMode(input.value);
        document.querySelectorAll('[data-firma-visibile-root="true"]').forEach((node) => {
          syncRoot(node, mode);
        });
      });
    });
    root.dataset.firmaVisibileBound = "true";
  }

  function initAll() {
    document.querySelectorAll('[data-firma-visibile-root="true"]').forEach(bindRoot);
  }

  function resolveRoot(rootOrSelector) {
    if (!rootOrSelector) return null;
    if (rootOrSelector instanceof Element) return rootOrSelector;
    if (typeof rootOrSelector === "string") {
      return document.querySelector(rootOrSelector);
    }
    return null;
  }

  function getSelectedMode(groupName, rootOrSelector) {
    const root = resolveRoot(rootOrSelector);
    const scope = root || document;
    const selected = scope.querySelector(`input[name="${groupName}"]:checked`);
    if (selected) {
      return normalizeMode(selected.value);
    }
    return loadStoredMode();
  }

  function getSignaturePlace(rootOrSelector) {
    const root = resolveRoot(rootOrSelector);
    return String(root?.dataset?.signaturePlace || "").trim();
  }

  window.HacsFirmaVisibileMode = {
    initAll,
    getSelectedMode,
    getSignaturePlace,
    loadStoredMode,
    saveMode,
    normalizeMode,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})(window, document);
