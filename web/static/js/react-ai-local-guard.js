(function () {
  'use strict';

  if (window.__iusentraReactAiLocalGuard) return;
  window.__iusentraReactAiLocalGuard = true;

  const originalFetch = window.fetch.bind(window);
  const DEFAULT_LOCAL_SIGNER = 'http://127.0.0.1:27272';
  const RESTART_PROTOCOL = 'iusentra-local-signer://restart';

  function config() {
    const monitor = document.getElementById('iusentra-local-signer-monitor');
    return {
      baseUrl: (monitor && monitor.dataset.localSignerUrl) || DEFAULT_LOCAL_SIGNER,
      restartProtocol: RESTART_PROTOCOL,
    };
  }

  function jsonResponse(payload, status) {
    return new Response(JSON.stringify(payload), {
      status: status || 200,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });
  }

  function record(value) {
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  }

  function text(value) {
    return typeof value === 'string' ? value.trim() : '';
  }

  function profileLabel(value) {
    const profile = text(value).toLowerCase();
    if (profile === 'strong') return 'PC adatto a modelli completi';
    if (profile === 'medium') return 'PC adatto a modelli medi';
    if (profile === 'weak') return 'PC da usare con modelli leggeri';
    return 'PC da verificare';
  }

  function numberLabel(value, suffix) {
    const amount = Number(value);
    if (!Number.isFinite(amount) || amount <= 0) return '';
    return (amount >= 10 ? String(Math.round(amount)) : amount.toFixed(1)) + ' ' + suffix;
  }

  function modelLabel(value) {
    const raw = text(value);
    const normalized = raw.toLowerCase();
    if (!normalized) return 'automatico';
    if (normalized === 'embeddinggemma' || normalized === 'embeddinggemma:latest') return 'EmbeddingGemma';
    if (normalized === 'embeddinggemma:300m') return 'EmbeddingGemma 300M';
    if (normalized === 'gemini-embedding-001') return 'Gemini Embedding';
    if (normalized === 'gemini-embedding-2') return 'Gemini Embedding 2';
    if (normalized === 'qwen3.5:0.8b') return 'Qwen 3.5 minimo';
    if (normalized === 'qwen3.5:2b') return 'Qwen 3.5 leggero';
    if (normalized === 'qwen3.5:9b') return 'Qwen 3.5 avanzato';
    if (normalized === 'gemma3:1b') return 'Gemma 3 veloce';
    if (normalized === 'gemma3:4b') return 'Gemma 3 completo';
    if (normalized === 'qwen2.5:0.5b') return 'Qwen leggero';
    if (normalized === 'nomic-embed-text') return 'Nomic Embed';
    return raw;
  }

  function describe(payload) {
    const source = record(payload);
    const runtime = record(source.runtime);
    const models = record(source.resolved_models);
    const status = text(runtime.status).toLowerCase();
    const ready = source.runtime_online === true || ['ready', 'ok', 'running', 'available'].includes(status);
    const pc = [
      profileLabel(runtime.hardware_profile),
      numberLabel(runtime.ram_gb, 'GB RAM'),
      numberLabel(runtime.disk_free_gb, 'GB liberi'),
    ].filter(Boolean).join(', ');
    const chat = modelLabel(models.chat);
    const embed = modelLabel(models.embed);
    if (ready) {
      return {
        ok: true,
        message: 'AI locale pronta. Risposte: ' + chat + '. Ricerca documenti: ' + embed + '. ' + pc,
        status_payload: source,
      };
    }
    return {
      ok: false,
      message: 'Ollama non risulta pronto su questo PC. Usa Prepara AI locale: IUSENTRA controlla il computer, installa quanto manca e sceglie i modelli adatti. ' + pc,
      status_payload: source,
    };
  }

  function localAiDefaults(force) {
    return {
      enabled: true,
      base_url: 'http://127.0.0.1:11434/api',
      auto_bootstrap: true,
      chat_model: '',
      embed_model: '',
      keep_alive: '10m',
      auto_index_documents: true,
      force: Boolean(force),
    };
  }

  function requestStart(protocolUrl) {
    if (!protocolUrl) return;
    const frame = document.createElement('iframe');
    frame.style.display = 'none';
    frame.src = protocolUrl;
    document.body.appendChild(frame);
    window.setTimeout(function () { frame.remove(); }, 1500);
  }

  async function pingLocalSigner(baseUrl) {
    const response = await originalFetch(baseUrl + '/ping', { mode: 'cors' });
    if (!response.ok) return false;
    const payload = await response.json().catch(function () { return {}; });
    return payload.ok !== false;
  }

  async function ensureLocalSigner() {
    const cfg = config();
    try {
      if (await pingLocalSigner(cfg.baseUrl)) return cfg;
    } catch (_) {
      requestStart(cfg.restartProtocol);
    }
    for (const wait of [500, 900, 1400, 2000, 2600]) {
      await new Promise(function (resolve) { window.setTimeout(resolve, wait); });
      try {
        if (await pingLocalSigner(cfg.baseUrl)) return cfg;
      } catch (_) {
        // Continue while the local service starts.
      }
    }
    return null;
  }

  async function fetchLocalStatus() {
    const cfg = await ensureLocalSigner();
    if (!cfg) {
      return {
        ok: false,
        message: 'IUSENTRA Local Signer non risponde su questo PC. Avvialo o installalo dalla sezione Firma Digitale, poi riprova.',
        status_payload: {},
      };
    }
    const response = await originalFetch(cfg.baseUrl + '/ai/status', { mode: 'cors' });
    const payload = await response.json().catch(function () { return {}; });
    return describe(payload);
  }

  async function prepareLocalAi(init) {
    const cfg = await ensureLocalSigner();
    if (!cfg) {
      return {
        ok: false,
        message: 'IUSENTRA Local Signer non risponde su questo PC. Avvialo o installalo dalla sezione Firma Digitale, poi riprova.',
        status_payload: {},
      };
    }
    let force = false;
    try {
      const body = init && init.body ? JSON.parse(String(init.body)) : {};
      force = Boolean(body.force);
    } catch (_) {
      force = false;
    }
    const response = await originalFetch(cfg.baseUrl + '/ai/bootstrap', {
      method: 'POST',
      mode: 'cors',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(localAiDefaults(force)),
    });
    const payload = await response.json().catch(function () { return {}; });
    return describe(payload.status_payload || payload.result || payload);
  }

  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : input && input.url;
    if (typeof url === 'string' && url.includes('/api/v1/ui/impostazioni/ai/status')) {
      return fetchLocalStatus().then(function (payload) { return jsonResponse(payload); });
    }
    if (typeof url === 'string' && url.includes('/api/v1/ui/impostazioni/ai/bootstrap')) {
      return prepareLocalAi(init || {}).then(function (payload) { return jsonResponse(payload); });
    }
    return originalFetch(input, init);
  };

  function injectAiHelp() {
    const path = window.location.pathname;
    const tab = new URLSearchParams(window.location.search).get('tab');
    if (!path.includes('/impostazioni') || tab !== 'ai') return;
    const panels = Array.from(document.querySelectorAll('.iu-settings-actions-panel'));
    const panel = panels.find(function (node) {
      return node.textContent && node.textContent.toLowerCase().includes('ai locale');
    });
    if (!panel || panel.querySelector('[data-ai-local-guard-help]')) return;
    const note = document.createElement('div');
    note.setAttribute('data-ai-local-guard-help', '1');
    note.className = 'iu-settings-ai-local-note';
    note.innerHTML = [
      '<strong>Preparazione automatica sul PC</strong>',
      '<span>Se Ollama o i modelli mancano, usa Prepara AI locale: IUSENTRA controlla il computer, sceglie i modelli adatti e scarica quanto serve.</span>',
    ].join('');
    panel.insertBefore(note, panel.children[1] || null);
  }

  function replaceVisibleText() {
    const replacements = new Map([
      ['Assistente sul PC dello studio e ricerca nei documenti.', 'Assistente sul PC: prepara Ollama, sceglie i modelli e cerca nei documenti.'],
      ['Verifica AI locale', 'Verifica PC e modelli'],
      ['Prepara motore locale', 'Prepara AI locale'],
      ['Stato corrente:', 'Stato:'],
    ]);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        const parent = node.parentElement;
        if (!parent || ['SCRIPT', 'STYLE'].includes(parent.tagName)) return NodeFilter.FILTER_REJECT;
        const value = node.nodeValue || '';
        for (const key of replacements.keys()) {
          if (value.includes(key)) return NodeFilter.FILTER_ACCEPT;
        }
        return NodeFilter.FILTER_REJECT;
      },
    });
    const nodes = [];
    let current = walker.nextNode();
    while (current) {
      nodes.push(current);
      current = walker.nextNode();
    }
    nodes.forEach(function (node) {
      let value = node.nodeValue || '';
      replacements.forEach(function (next, previous) {
        value = value.split(previous).join(next);
      });
      node.nodeValue = value;
    });
  }

  function injectStyle() {
    if (document.getElementById('iusentra-react-ai-local-guard-style')) return;
    const style = document.createElement('style');
    style.id = 'iusentra-react-ai-local-guard-style';
    style.textContent = '.iu-settings-ai-local-note{display:grid;gap:4px;padding:10px;border:1px solid rgba(37,99,235,.14);border-radius:10px;background:#eff6ff}.iu-settings-ai-local-note strong{font-size:13px;font-weight:900;color:#172554}.iu-settings-ai-local-note span{font-size:12px;line-height:1.4;color:#475569;font-weight:700}';
    document.head.appendChild(style);
  }

  document.addEventListener('DOMContentLoaded', function () {
    injectStyle();
    replaceVisibleText();
    injectAiHelp();
    const observer = new MutationObserver(function () {
      replaceVisibleText();
      injectAiHelp();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  });
}());
