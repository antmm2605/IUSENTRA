(function () {
  "use strict";

  if (window.__iusentraPecLocalSignerGuard) return;
  window.__iusentraPecLocalSignerGuard = true;

  var LOCAL_BASE = "http://127.0.0.1:27272";
  var RESTART_PROTOCOL = "iusentra-local-signer://restart";
  var TARGET_PATH = "/api/v1/ui/impostazioni/test/pec-smtp";
  var originalFetch = window.fetch.bind(window);

  function text(value, fallback) {
    if (value === undefined || value === null || value === "") return String(fallback || "").trim();
    if (typeof value === "object") return String(fallback || "").trim();
    return String(value).trim();
  }

  function boolValue(value, fallback) {
    if (typeof value === "boolean") return value;
    var normalized = text(value).toLowerCase();
    if (["1", "true", "si", "yes", "on"].indexOf(normalized) !== -1) return true;
    if (["0", "false", "no", "off"].indexOf(normalized) !== -1) return false;
    return fallback;
  }

  function intValue(value, fallback) {
    var parsed = parseInt(text(value), 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
  }

  function isDesktopHost() {
    var ua = String(window.navigator.userAgent || "").toLowerCase();
    var platform = String(window.navigator.platform || "").toLowerCase();
    var mobile = /android|iphone|ipad|ipod|mobile|tablet|silk|kindle/.test(ua);
    var ipadDesktopMode = platform.indexOf("mac") !== -1 && Number(window.navigator.maxTouchPoints || 0) > 1;
    return !mobile && !ipadDesktopMode;
  }

  function targetUrl(input) {
    try {
      var raw = typeof input === "string" ? input : input.url;
      return new URL(raw, window.location.origin);
    } catch (error) {
      return null;
    }
  }

  function isTargetRequest(input, init) {
    var url = targetUrl(input);
    var method = String((init && init.method) || (input && input.method) || "GET").toUpperCase();
    return Boolean(url && url.pathname === TARGET_PATH && method === "POST");
  }

  function jsonResponse(data) {
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  function startSigner() {
    var iframe = document.createElement("iframe");
    iframe.style.display = "none";
    iframe.src = RESTART_PROTOCOL;
    document.body.appendChild(iframe);
    window.setTimeout(function () {
      iframe.remove();
    }, 2500);
  }

  function csrfToken() {
    var token = document.querySelector('meta[name="csrf-token"]');
    return token ? token.content || "" : "";
  }

  async function fetchJson(url, options, timeoutMs, sameOrigin) {
    var controller = new AbortController();
    var timer = window.setTimeout(function () {
      controller.abort();
    }, timeoutMs);
    var headers = new Headers((options && options.headers) || {});
    if (!headers.has("X-Requested-With")) headers.set("X-Requested-With", "XMLHttpRequest");
    if (sameOrigin && csrfToken() && !headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", csrfToken());

    try {
      var response = await originalFetch(url, Object.assign({}, options || {}, {
        signal: controller.signal,
        headers: headers,
      }));
      return await response.json();
    } catch (error) {
      return null;
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function ensureLocalSigner() {
    if (!isDesktopHost()) {
      return { ok: false, message: "Il controllo invio PEC richiede il PC dello studio." };
    }

    var pingUrl = LOCAL_BASE + "/ping?light=1";
    var ping = await fetchJson(pingUrl, {}, 2500, false);
    if (!ping || !ping.ok) {
      startSigner();
      for (var attempt = 0; attempt < 10; attempt += 1) {
        await sleep(900);
        ping = await fetchJson(pingUrl, {}, 2500, false);
        if (ping && ping.ok) break;
      }
    }

    if (!ping || !ping.ok) {
      return { ok: false, message: "Local Signer non rilevato. Avvia IUSENTRA Local Signer sul PC in uso e riprova." };
    }
    return null;
  }

  async function readBody(input, init) {
    if (init && typeof init.body === "string") return init.body;
    if (input && typeof input !== "string" && typeof input.clone === "function") {
      try {
        return await input.clone().text();
      } catch (error) {
        return "";
      }
    }
    return "";
  }

  async function savedPecPayload(payload) {
    var saved = await fetchJson("/impostazioni/pec/local-smtp-payload", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        indirizzo: payload.indirizzo,
        smtp_host: payload.smtp_host,
        smtp_port: payload.smtp_port,
        use_ssl: payload.use_ssl,
      }),
    }, 10000, true);

    if (!saved || !saved.ok || !saved.payload) {
      return {
        error: text(
          saved && saved.errore,
          "Password PEC non disponibile. Inseriscila nel campo Password PEC, poi ripeti la verifica. La password viene inviata solo al Local Signer sul PC in uso."
        ),
      };
    }

    return {
      payload: Object.assign({}, payload, saved.payload, {
        indirizzo: text(payload.indirizzo, saved.payload.indirizzo),
        username: text(payload.indirizzo, text(saved.payload.username, saved.payload.indirizzo)),
        password: text(saved.payload.password),
        smtp_host: text(payload.smtp_host, saved.payload.smtp_host),
        smtp_port: intValue(payload.smtp_port, intValue(saved.payload.smtp_port, 465)),
        use_ssl: boolValue(payload.use_ssl, boolValue(saved.payload.use_ssl, true)),
      }),
    };
  }

  async function runLocalPecCheck(input, init) {
    var serviceError = await ensureLocalSigner();
    if (serviceError) return serviceError;

    var raw = await readBody(input, init);
    var values = {};
    try {
      values = raw ? JSON.parse(raw) : {};
    } catch (error) {
      values = {};
    }

    var payload = {
      indirizzo: text(values.indirizzo),
      username: text(values.indirizzo, values.username),
      password: text(values.password),
      smtp_host: text(values.smtp_host),
      smtp_port: intValue(values.smtp_port, 465),
      use_ssl: boolValue(values.use_ssl, true),
    };

    if (!payload.password) {
      var saved = await savedPecPayload(payload);
      if (saved.error) return { ok: false, message: saved.error };
      payload = saved.payload;
    }

    if (!payload.password) {
      return {
        ok: false,
        message: "Password PEC non disponibile. Inseriscila nel campo Password PEC, poi ripeti la verifica. La password viene inviata solo al Local Signer sul PC in uso.",
      };
    }

    var result = await fetchJson(LOCAL_BASE + "/pec/smtp/test", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    }, 35000, false);

    if (!result) {
      return { ok: false, message: "Local Signer non rilevato. Avvia IUSENTRA Local Signer sul PC in uso e riprova." };
    }

    return {
      ok: Boolean(result.ok),
      message: text(result.messaggio || result.message, result.ok ? "Connessione SMTP PEC riuscita." : "Verifica invio PEC non completata."),
    };
  }

  window.fetch = function (input, init) {
    if (!isTargetRequest(input, init)) {
      return originalFetch(input, init);
    }
    return runLocalPecCheck(input, init).then(jsonResponse);
  };
})();
